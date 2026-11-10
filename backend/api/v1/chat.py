# backend/api/v1/chat.py
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

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
from agents.chat_processing import get_stream_queue
from agents.llm_client import LLMClient, get_llm_client
from api.v1.chat_schemas import AttachmentDTO, ChatMessageCreated, ChatMessageDTO
from core.config import get_settings
from db.models import ChatAttachment, ChatMessage, Evaluation
from api.v1.evaluations import get_background_session_factory
from db.session import get_db
from services.upload_service import FileTooLargeError, MimeNotAllowedError, save_upload

router = APIRouter(prefix="/api/v1", tags=["chat"])

# Sentinel defaults — no llaman a get_settings() en import time.
# Tests pueden monkeypatch antes de la primera request.
# Los valores reales se leen desde settings en la primera request via _resolve_limits().
MAX_MESSAGES: int = 60
MAX_FILES: int = 3
MAX_FILE_BYTES: int = 5 * 1024 * 1024


def _resolve_limits() -> None:
    """Lee settings una vez y actualiza los módule-level limits.

    Idempotente: si los valores ya fueron sobrescritos por monkeypatch en tests,
    no los pisa (solo corre si MAX_MESSAGES sigue siendo el sentinel 60 Y
    get_settings está disponible).
    """
    global MAX_MESSAGES, MAX_FILES, MAX_FILE_BYTES
    try:
        s = get_settings()
        MAX_MESSAGES = s.max_messages_per_conversation
        MAX_FILES = s.max_files_per_message
        MAX_FILE_BYTES = s.max_file_size_bytes
    except Exception:
        pass  # En tests sin .env válido usamos los valores sentinel


async def _check_streaming_turn(db: AsyncSession, eval_id: uuid.UUID) -> bool:
    """Returns True if there is already an active streaming assistant message.

    SQLite does not support WITH FOR UPDATE SKIP LOCKED; falls back to a
    plain SELECT in that case (acceptable for a 2-3 user internal tool).
    """
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.evaluation_id == eval_id)
        .where(ChatMessage.role == "assistant")
        .where(ChatMessage.status == "streaming")
    )
    try:
        stmt_locked = stmt.with_for_update(skip_locked=True)
        result = await db.execute(stmt_locked)
    except Exception:
        # SQLite or other backends that don't support SKIP LOCKED
        result = await db.execute(stmt)

    return result.scalar_one_or_none() is not None


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
) -> ChatMessageCreated:
    """Crea un turno de chat para una evaluación completada.

    Devuelve 202 inmediatamente. El procesamiento LLM corre en BackgroundTask.
    El frontend hace polling o se suscribe al SSE stream para obtener tokens.
    """
    _resolve_limits()

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
    if msg_count >= MAX_MESSAGES:
        raise HTTPException(
            status_code=429,
            detail="Límite de mensajes alcanzado para esta evaluación",
        )

    # --- Verificar que no haya un turno activo en streaming ---
    if await _check_streaming_turn(db, eval_id):
        raise HTTPException(status_code=409, detail="Ya hay un turno en proceso")

    # --- Validar cantidad de archivos ---
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo {MAX_FILES} archivos por mensaje",
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
    total_bytes = 0
    MAX_TOTAL_BYTES = MAX_FILES * MAX_FILE_BYTES  # 15MB total (3 × 5MB)
    for f in files:
        raw = await f.read()
        if len(raw) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Archivo '{f.filename}' excede 5MB",
            )
        total_bytes += len(raw)
        if total_bytes > MAX_TOTAL_BYTES:
            raise HTTPException(
                status_code=400,
                detail="Tamaño total de archivos excede 15MB",
            )
        try:
            uploaded = await save_upload(
                data=raw,
                filename=f.filename or "archivo",
                declared_mime=f.content_type or "application/octet-stream",
                eval_id=eval_id,
                message_id=user_msg.id,
            )
        except MimeNotAllowedError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except FileTooLargeError as e:
            raise HTTPException(status_code=400, detail=str(e))

        from agents.chat_processing import extract_markdown

        try:
            _markitdown_timeout = get_settings().markitdown_timeout_s
        except Exception:
            _markitdown_timeout = 20

        markdown = await extract_markdown(
            uploaded.storage_path,
            uploaded.mime_type,
            timeout_s=_markitdown_timeout,
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
    db: AsyncSession = Depends(get_db),
):
    """SSE stream de tokens para un mensaje de asistente en status=streaming."""

    async def event_generator():
        msg_result = await db.execute(
            select(ChatMessage).where(ChatMessage.id == message_id)
        )
        msg = msg_result.scalar_one_or_none()
        if msg is None:
            yield {
                "event": "error",
                "data": json.dumps({"error": "Mensaje no encontrado", "code": "NOT_FOUND"}),
            }
            return

        if msg.status == "complete":
            yield {
                "event": "complete",
                "data": json.dumps({"message_id": str(message_id), "content": msg.content}),
            }
            return

        if msg.status == "error":
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": msg.error_msg or "Error desconocido", "code": "LLM_ERROR"}
                ),
            }
            return

        q = get_stream_queue(str(message_id))
        if q is None:
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": "Stream no disponible", "code": "STREAM_UNAVAILABLE"}
                ),
            }
            return

        yield {"event": "status", "data": json.dumps({"status": "streaming"})}

        while True:
            try:
                token = await asyncio.wait_for(q.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "keepalive"}
                continue

            if token is None:
                # Señal de fin de stream — refrescar y emitir complete o error
                await db.refresh(msg)
                if msg.status == "error":
                    yield {
                        "event": "error",
                        "data": json.dumps(
                            {"error": msg.error_msg or "Error", "code": "LLM_ERROR"}
                        ),
                    }
                else:
                    yield {
                        "event": "complete",
                        "data": json.dumps(
                            {"message_id": str(message_id), "content": msg.content}
                        ),
                    }
                break

            yield {"event": "token", "data": json.dumps({"token": token})}

    return EventSourceResponse(event_generator())


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
