# backend/agents/chat.py
"""Proceso de un turno de chat: carga contexto, llama LLM en streaming,
persiste tokens y marca el mensaje como complete/error.

ADR-006: Se ejecuta desde BackgroundTask — no bloquea el request.
ADR-007: LLM via LLMClient (langchain-anthropic), nunca SDK Anthropic directo.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agents.chat_processing import (
    build_history_messages,
    build_system_blocks,
    cleanup_stream_queue,
    create_stream_queue,
)
from agents.llm_client import LLMClient
from db.models import ChatAttachment, ChatMessage, Evaluation


async def process_chat_turn(
    *,
    evaluation_id: uuid.UUID,
    user_msg_id: uuid.UUID,
    assistant_msg_id: uuid.UUID,
    session: AsyncSession,
    llm: LLMClient,
    temperature: float = 0.4,
    max_tokens: int = 2_000,
) -> None:
    """Ejecuta un turno completo de chat y persiste el resultado.

    Crea una asyncio.Queue para SSE mientras corre y la limpia siempre
    en el bloque finally, independientemente de si hay error.

    Args:
        evaluation_id: UUID de la evaluación padre.
        user_msg_id: UUID del ChatMessage de rol 'user' ya persistido.
        assistant_msg_id: UUID del ChatMessage de rol 'assistant' (status='streaming').
        session: AsyncSession abierta por el caller (BackgroundTask o test).
        llm: LLMClient — AnthropicLLMClient en prod, FakeLLMClient en tests.
        temperature: Temperatura para el modelo. Default 0.4 (ADR-007).
        max_tokens: Máximo de tokens de salida.
    """
    q = create_stream_queue(str(assistant_msg_id))
    full_content = ""

    try:
        # --- Cargar evaluación con sus relaciones ---
        evaluation = await session.get(
            Evaluation,
            evaluation_id,
            options=[
                selectinload(Evaluation.inputs),
                selectinload(Evaluation.agent_results),
            ],
        )
        if evaluation is None:
            raise ValueError(f"Evaluación {evaluation_id} no encontrada")

        # --- Cargar historial previo (excluir turno actual) ---
        hist_result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.evaluation_id == evaluation_id)
            .where(ChatMessage.id.notin_([user_msg_id, assistant_msg_id]))
            .where(ChatMessage.status == "complete")
            .order_by(ChatMessage.created_at)
        )
        history = list(hist_result.scalars().all())

        # --- Cargar mensaje del usuario ---
        user_result = await session.execute(
            select(ChatMessage).where(ChatMessage.id == user_msg_id)
        )
        user_msg = user_result.scalar_one_or_none()
        if user_msg is None:
            raise ValueError(f"Mensaje {user_msg_id} no encontrado")

        # --- Cargar attachments del mensaje del usuario ---
        att_result = await session.execute(
            select(ChatAttachment).where(ChatAttachment.message_id == user_msg_id)
        )
        attachments = list(att_result.scalars().all())

        # --- Construir prompt ---
        system_blocks = build_system_blocks(evaluation)
        history_msgs = build_history_messages(history)

        # Turno actual del usuario
        user_content: list = [{"type": "text", "text": user_msg.content}]
        for att in attachments:
            if att.markdown_extracted:
                user_content.append({
                    "type": "text",
                    "text": f"\n\n[Archivo: {att.original_name}]\n{att.markdown_extracted}",
                })
            elif att.mime_type.startswith("image/"):
                import base64
                from pathlib import Path as _Path
                try:
                    img_bytes = _Path(att.storage_path).read_bytes()
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                f"data:{att.mime_type};base64,"
                                f"{base64.b64encode(img_bytes).decode()}"
                            )
                        },
                    })
                except Exception:
                    pass  # archivo faltante — ignorar silenciosamente

        current_user_msg = HumanMessage(content=user_content)
        all_messages = [*system_blocks, *history_msgs, current_user_msg]

        # --- Streaming de tokens ---
        char_count = 0
        async for token in llm.stream_text(
            all_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            full_content += token
            await q.put(token)
            char_count += len(token)

            # Flush periódico cada ~50 caracteres para que el SSE tenga datos recientes
            if char_count >= 50:
                char_count = 0
                try:
                    flush_result = await session.execute(
                        select(ChatMessage).where(ChatMessage.id == assistant_msg_id)
                    )
                    asst_flush = flush_result.scalar_one_or_none()
                    if asst_flush is not None:
                        asst_flush.content = full_content
                        asst_flush.updated_at = datetime.now(timezone.utc)
                        await session.flush()
                except Exception:
                    pass  # Non-fatal — final commit will persist the full content

        # --- Escritura final ---
        final_result = await session.execute(
            select(ChatMessage).where(ChatMessage.id == assistant_msg_id)
        )
        asst_final = final_result.scalar_one_or_none()
        if asst_final is not None:
            asst_final.content = full_content
            asst_final.status = "complete"
            asst_final.updated_at = datetime.now(timezone.utc)
            await session.commit()

    except Exception as exc:
        # Marcar el mensaje como error en DB
        try:
            await session.rollback()
            err_result = await session.execute(
                select(ChatMessage).where(ChatMessage.id == assistant_msg_id)
            )
            asst_err = err_result.scalar_one_or_none()
            if asst_err is not None:
                asst_err.status = "error"
                asst_err.error_msg = str(exc)[:500]
                asst_err.updated_at = datetime.now(timezone.utc)
                await session.commit()
        except Exception:
            pass  # no re-raise: evitar crash del BackgroundTask

    finally:
        # Siempre emitir sentinel y limpiar la queue para cerrar el SSE
        await q.put(None)
        cleanup_stream_queue(str(assistant_msg_id))
