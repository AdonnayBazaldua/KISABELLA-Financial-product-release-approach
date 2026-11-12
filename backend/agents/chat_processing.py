# backend/agents/chat_processing.py
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

if TYPE_CHECKING:
    from db.models import ChatMessage, Evaluation

IMAGE_MIMES: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/webp"})

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "chat.md"

# Stream queues: message_id (str) → asyncio.Queue[str | None]
_stream_queues: dict[str, asyncio.Queue] = {}

# Markitdown instance (None if not installed)
try:
    from markitdown import MarkItDown
    _markitdown = MarkItDown()
except Exception:
    _markitdown = None  # type: ignore


def create_stream_queue(message_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=2000)
    _stream_queues[message_id] = q
    return q


def get_stream_queue(message_id: str) -> asyncio.Queue | None:
    return _stream_queues.get(message_id)


def cleanup_stream_queue(message_id: str) -> None:
    _stream_queues.pop(message_id, None)


def build_system_blocks(evaluation: Any) -> list[SystemMessage]:
    """Prompt del sistema + contexto de la evaluación.

    Ambos son idénticos en todos los turnos de una conversación, así que se marcan para
    prompt caching. cache_control va en el bloque de contenido: en additional_kwargs
    langchain-anthropic lo descarta. Un solo breakpoint al final cachea todo el prefijo.
    """
    inp = getattr(evaluation, "inputs", None)
    agent_sections = "".join(
        f"\n## {ar.agent_name.capitalize()}\n{ar.analisis_extenso or ''}\n"
        for ar in (getattr(evaluation, "agent_results", None) or [])
    )
    context_text = (
        f"# Evaluación: {inp.product_name if inp else evaluation.name}\n"
        f"Veredicto: {evaluation.final_verdict} (score: {evaluation.final_score}/100)\n\n"
        f"## Resumen\n{evaluation.final_summary or ''}\n"
        f"{agent_sections}"
        f"\n## Datos originales\n"
        f"Precio objetivo: ${inp.target_price if inp else 'N/A'} MXN\n"
        f"Unidades/mes estimadas: {inp.estimated_units_month if inp else 'N/A'}\n"
    )
    return [
        SystemMessage(content=_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")),
        SystemMessage(
            content=[
                {"type": "text", "text": context_text, "cache_control": {"type": "ephemeral"}}
            ]
        ),
    ]


def build_history_messages(messages: list[Any]) -> list[Any]:
    result = []
    for m in messages:
        if getattr(m, "status", "complete") != "complete":
            continue
        if m.role == "user":
            result.append(HumanMessage(content=m.content))
        else:
            result.append(AIMessage(content=m.content))
    return result


async def extract_markdown(path: str, mime_type: str, timeout_s: int = 20) -> str | None:
    if mime_type in IMAGE_MIMES:
        return None
    if _markitdown is None:
        return None
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_markitdown.convert, path), timeout=float(timeout_s)
        )
        return result.text_content or None
    except Exception:
        return None
