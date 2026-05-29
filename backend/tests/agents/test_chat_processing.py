# backend/tests/agents/test_chat_processing.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agents.chat_processing import (
    build_system_blocks,
    build_history_messages,
    extract_markdown,
    create_stream_queue,
    get_stream_queue,
    cleanup_stream_queue,
)
from db.models import ChatMessage, Evaluation, EvaluationInput, AgentResult


def _make_evaluation() -> Evaluation:
    ev = Evaluation()
    ev.id = uuid.uuid4()
    ev.name = "Test Producto"
    ev.final_verdict = "viable"
    ev.final_score = 78
    ev.final_summary = "Producto con buenas perspectivas de mercado."
    ev.status = "complete"
    ev.created_by = uuid.UUID("00000000-0000-0000-0000-000000000001")
    ev.warn_flags = []
    ev.requires_human_review = False
    ev.created_at = datetime.now(timezone.utc)
    ev.updated_at = datetime.now(timezone.utc)
    inp = EvaluationInput()
    inp.id = uuid.uuid4()
    inp.evaluation_id = ev.id
    inp.product_name = "Test Producto"
    inp.target_price = 500
    inp.estimated_units_month = 100
    inp.cost_purchase = 100
    inp.cost_freight = 20
    inp.cost_customs = 10
    inp.cost_storage = 5
    inp.cost_logistics_vehicle = 5
    inp.cost_logistics_viaticos = 0
    inp.cost_logistics_personnel = 0
    inp.cost_shrinkage_pct = 2
    inp.cost_commission_pct = 5
    inp.cost_marketing = 10
    inp.cost_overhead = 10
    ev.inputs = inp
    ev.agent_results = []
    ev.chat_messages = []
    return ev


def _make_chat_msg(role: str, content: str) -> ChatMessage:
    m = ChatMessage()
    m.id = uuid.uuid4()
    m.role = role
    m.content = content
    m.status = "complete"
    m.created_at = datetime.now(timezone.utc)
    m.updated_at = datetime.now(timezone.utc)
    return m


def test_build_system_blocks_returns_two_blocks():
    ev = _make_evaluation()
    blocks = build_system_blocks(ev)
    assert len(blocks) == 2


def test_build_system_blocks_first_block_has_system_prompt():
    ev = _make_evaluation()
    blocks = build_system_blocks(ev)
    # first block should contain the system prompt text
    content = blocks[0].content if isinstance(blocks[0].content, str) else str(blocks[0].content)
    assert "asesor financiero" in content.lower()


def test_build_system_blocks_second_block_has_eval_context():
    ev = _make_evaluation()
    blocks = build_system_blocks(ev)
    content = blocks[1].content if isinstance(blocks[1].content, str) else str(blocks[1].content)
    assert "Test Producto" in content
    assert "viable" in content


def test_build_history_messages_empty():
    msgs = build_history_messages([])
    assert msgs == []


def test_build_history_messages_creates_human_and_ai():
    from langchain_core.messages import HumanMessage, AIMessage
    chat_msgs = [
        _make_chat_msg("user", "¿Cuál es el margen?"),
        _make_chat_msg("assistant", "El margen es del 40%."),
    ]
    result = build_history_messages(chat_msgs)
    assert len(result) == 2
    assert isinstance(result[0], HumanMessage)
    assert isinstance(result[1], AIMessage)
    assert result[0].content == "¿Cuál es el margen?"


def test_build_history_messages_skips_streaming():
    chat_msgs = [
        _make_chat_msg("user", "hola"),
        _make_chat_msg("assistant", ""),
    ]
    chat_msgs[1].status = "streaming"
    result = build_history_messages(chat_msgs)
    assert len(result) == 1  # only the user message


def test_stream_queue_create_and_get():
    msg_id = str(uuid.uuid4())
    q = create_stream_queue(msg_id)
    assert get_stream_queue(msg_id) is q


def test_stream_queue_cleanup():
    msg_id = str(uuid.uuid4())
    create_stream_queue(msg_id)
    cleanup_stream_queue(msg_id)
    assert get_stream_queue(msg_id) is None


@pytest.mark.asyncio
async def test_extract_markdown_image_returns_none():
    result = await extract_markdown("/fake/img.jpg", "image/jpeg", timeout_s=5)
    assert result is None


@pytest.mark.asyncio
async def test_extract_markdown_document(tmp_path, fake_markitdown, monkeypatch):
    import agents.chat_processing as cp
    monkeypatch.setattr(cp, "_markitdown", fake_markitdown)

    path = str(tmp_path / "doc.pdf")
    Path(path).write_bytes(b"fake pdf")
    fake_markitdown.register(path, "# Tabla\n| A | B |\n|---|---|\n| 1 | 2 |")

    result = await extract_markdown(path, "application/pdf", timeout_s=5)
    assert result is not None
    assert "Tabla" in result
