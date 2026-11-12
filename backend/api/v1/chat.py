# backend/api/v1/chat.py
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from agents.chat import process_chat_turn
from agents.chat_processing import extract_markdown, get_stream_queue
from agents.llm_client import LLMClient, get_llm_client
from api.v1.chat_schemas import AttachmentDTO, ChatMessageCreated, ChatMessageDTO
from core.config import Settings, get_settings
from db.models import ChatAttachment, ChatMessage, Evaluation
from api.v1.evaluations import get_background_session_factory
from db.session import get_db
from services.upload_service import FileTooLargeError, MimeNotAllowedError, save_upload

router = APIRouter(prefix="/api/v1", tags=["chat"])

async def _has_streaming_turn(db: AsyncSession, eval_id: uuid.UUID) -> bool:
    """True si ya hay un mensaje del asistente en streaming para la evaluación."""
    result = await db.execute(
        select(ChatMessage.id)
        .where(ChatMessage.evaluation_id == eval_id)
        .where(ChatMessage.role == "assistant")
        .where(ChatMessage.status == "streaming")
        .limit(1)
    )
    return result.first() is not None


@router.post(
    "/evaluations/{eval_id}/chat/messages",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ChatMessageCreated,
)
async def post_chat_message(
    eval_id: uuid.UUID,
    background: BackgroundTasks,
    content: str = Form(..., min_length=1, max_length=4000),
    files: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
    session_factory=Depends(get_background_session_factory),
    settings: Settings = Depends(get_settings),
) -> ChatMessageCreated:
    """Crea un turno de chat para una evaluación completada.

    Devuelve 202 inmediatamente. El procesamiento LLM corre en BackgroundTask.
    El frontend hace polling o se suscribe al SSE stream para obtener tokens.
    """
    max_files = settings.max_files_per_message
    max_file_bytes = settings.max_file_size_bytes

    # --- Verificar que la evaluación existe y está completa ---
    # session.get() uses the identity map and avoids postgresql.UUID type
    # re-processing issues with SQLite in tests.
    evaluation = await db.get(Evaluation, eval_id)
    if evaluation is None or evaluation.status != "complete":
        raise HTTPException(
            status_code=404,
            detail="Evaluación no encontrada o no completada",
        )

    # --- Verificar límite de mensajes ---
    count_result = await db.execute(
        select(func.count())
        .select_from(ChatMessage)
        .where(ChatMessage.evaluation_id == eval_id)
    )
    msg_count = count_result.scalar_one()
    if msg_count >= settings.max_messages_per_conversation:
        raise HTTPException(
            status_code=429,
            detail="Límite de mensajes alcanzado para esta evaluación",
        )

    # --- Verificar que no haya un turno activo en streaming ---
    if await _has_streaming_turn(db, eval_id):
        raise HTTPException(status_code=409, detail="Ya hay un turno en proceso")

    # --- Validar cantidad de archivos ---
    if len(files) > max_files:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo {max_files} archivos por mensaje",
        )

    # --- Insertar mensaje del usuario ---
    user_msg = ChatMessage()
    user_msg.id = uuid.uuid4()
    user_msg.evaluation_id = eval_id
    user_msg.role = "user"
    user_msg.content = content
    user_msg.status = "complete"
    user_msg.created_at = datetime.now(timezone.utc)
    user_msg.updated_at = datetime.now(timezone.utc)
    db.add(user_msg)
    await db.flush()

    # --- Procesar archivos adjuntos ---
    for f in files:
        # ponytail: lee el archivo completo y luego valida; tope real = client_max_body_size del proxy
        raw = await f.read()
        try:
            uploaded = await save_upload(
                data=raw,
                filename=f.filename or "archivo",
                declared_mime=f.content_type or "application/octet-stream",
                eval_id=eval_id,
                message_id=user_msg.id,
                upload_root=Path(settings.upload_root),
                max_bytes=max_file_bytes,
            )
        except (MimeNotAllowedError, FileTooLargeError) as e:
            raise HTTPException(status_code=400, detail=str(e))

        markdown = await extract_markdown(
            uploaded.storage_path,
            uploaded.mime_type,
            timeout_s=settings.markitdown_timeout_s,
        )

        att = ChatAttachment()
        att.id = uuid.uuid4()
        att.message_id = user_msg.id
        att.evaluation_id = eval_id
        att.original_name = f.filename or "archivo"
        att.mime_type = uploaded.mime_type
        att.size_bytes = uploaded.size_bytes
        att.sha256 = uploaded.sha256
        att.storage_path = uploaded.storage_path
        att.markdown_extracted = markdown
        att.created_at = datetime.now(timezone.utc)
        db.add(att)

    # --- Insertar placeholder del mensaje del asistente ---
    asst_msg = ChatMessage()
    asst_msg.id = uuid.uuid4()
    asst_msg.evaluation_id = eval_id
    asst_msg.role = "assistant"
    asst_msg.content = ""
    asst_msg.status = "streaming"
    asst_msg.created_at = datetime.now(timezone.utc)
    asst_msg.updated_at = datetime.now(timezone.utc)
    db.add(asst_msg)
    await db.flush()

    # El task abre otra sesión: lo flusheado debe estar commiteado y visible para ella.
    await db.commit()
    background.add_task(
        process_chat_turn,
        evaluation_id=eval_id,
        user_msg_id=user_msg.id,
        assistant_msg_id=asst_msg.id,
        session_factory=session_factory,
        llm=llm,
    )

    return ChatMessageCreated(message_id=asst_msg.id)


@router.get("/evaluations/{eval_id}/chat/messages/{message_id}/stream")
async def stream_chat_message(
    eval_id: uuid.UUID,
    message_id: uuid.UUID,
    session_factory=Depends(get_background_session_factory),
):
    """SSE stream de tokens para un mensaje de asistente en status=streaming.

    El generador corre cuando la sesión del request ya se cerró, así que abre
    sesiones propias y cortas: no retiene una conexión del pool durante el stream.
    """

    async def _load() -> ChatMessage | None:
        async with session_factory() as session:
            result = await session.execute(
                select(ChatMessage)
                .where(ChatMessage.id == message_id)
                .where(ChatMessage.evaluation_id == eval_id)
            )
            return result.scalar_one_or_none()

    def _final_event(msg: ChatMessage | None) -> dict:
        if msg is None:
            return _event("error", error="Mensaje no encontrado", code="NOT_FOUND")
        if msg.status == "error":
            return _event("error", error=msg.error_msg or "Error desconocido", code="LLM_ERROR")
        return _event("complete", message_id=str(message_id), content=msg.content)

    async def event_generator():
        msg = await _load()
        if msg is None or msg.status != "streaming":
            yield _final_event(msg)
            return

        q = get_stream_queue(str(message_id))
        if q is None:
            # El turno pudo terminar entre la lectura y aquí; si sigue "streaming", no hay cola (otro worker/reinicio).
            msg = await _load()
            if msg is not None and msg.status == "streaming":
                yield _event("error", error="Stream no disponible", code="STREAM_UNAVAILABLE")
            else:
                yield _final_event(msg)
            return

        yield _event("status", status="streaming")
        while True:
            try:
                token = await asyncio.wait_for(q.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "keepalive"}
                continue
            if token is None:  # fin del stream: releer el estado final persistido
                yield _final_event(await _load())
                return
            yield _event("token", token=token)

    return EventSourceResponse(event_generator())


def _event(name: str, **data) -> dict:
    return {"event": name, "data": json.dumps(data)}


@router.get(
    "/evaluations/{eval_id}/chat/messages",
    response_model=list[ChatMessageDTO],
)
async def list_chat_messages(
    eval_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessageDTO]:
    """Lista todos los mensajes de chat de una evaluación, ordenados por creación."""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.evaluation_id == eval_id)
        .options(selectinload(ChatMessage.attachments))
        .order_by(ChatMessage.created_at)
        .limit(200)
    )
    messages = list(result.scalars().all())
    return [
        ChatMessageDTO(
            id=m.id,
            role=m.role,
            content=m.content,
            status=m.status,
            error_msg=m.error_msg,
            created_at=m.created_at,
            attachments=[
                AttachmentDTO(
                    id=a.id,
                    original_name=a.original_name,
                    mime_type=a.mime_type,
                    size_bytes=a.size_bytes,
                )
                for a in m.attachments
            ],
        )
        for m in messages
    ]
