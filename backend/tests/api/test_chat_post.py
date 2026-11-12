# backend/tests/api/test_chat_post.py
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from agents.llm_client import FakeLLMClient, get_llm_client
from api.v1.evaluations import get_background_session_factory
from api.v1.chat import get_settings, router as chat_router
from core.config import Settings
from db.models import ChatMessage, Evaluation, EvaluationInput
from db.session import get_db


def _make_app(session, **settings):
    app = FastAPI()
    app.include_router(chat_router)

    async def _override_db():
        yield session

    def _override_llm():
        return FakeLLMClient()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_background_session_factory] = lambda: (lambda: None)
    app.dependency_overrides[get_llm_client] = _override_llm
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        anthropic_api_key="x",
        database_url="postgresql+asyncpg://t:t@localhost/t",
        **settings,
    )
    return app


def _make_complete_eval() -> Evaluation:
    ev = Evaluation()
    ev.id = uuid.uuid4()
    ev.name = "Test Eval"
    ev.status = "complete"
    ev.final_verdict = "viable"
    ev.final_score = 80
    ev.final_summary = "OK"
    ev.created_by = uuid.UUID("00000000-0000-0000-0000-000000000001")
    ev.warn_flags = []
    ev.requires_human_review = False
    ev.created_at = datetime.now(timezone.utc)
    ev.updated_at = datetime.now(timezone.utc)
    inp = EvaluationInput()
    inp.id = uuid.uuid4()
    inp.evaluation_id = ev.id
    inp.product_name = "Test"
    inp.target_price = 300
    inp.estimated_units_month = 10
    inp.cost_purchase = 100
    inp.cost_freight = 10
    inp.cost_customs = 5
    inp.cost_storage = 2
    inp.cost_logistics_vehicle = 2
    inp.cost_logistics_viaticos = 0
    inp.cost_logistics_personnel = 0
    inp.cost_shrinkage_pct = 1
    inp.cost_commission_pct = 3
    inp.cost_marketing = 5
    inp.cost_overhead = 5
    ev.inputs = inp
    ev.agent_results = []
    ev.chat_messages = []
    return ev


@pytest.mark.asyncio
async def test_post_chat_message_returns_202(fake_session):
    ev = _make_complete_eval()
    fake_session.add(ev)
    await fake_session.commit()

    app = _make_app(fake_session)
    with patch("api.v1.chat.process_chat_turn", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/evaluations/{ev.id}/chat/messages",
                data={"content": "¿Cuál es el margen neto?"},
            )

    assert resp.status_code == 202
    body = resp.json()
    assert "message_id" in body
    assert body["status"] == "streaming"


@pytest.mark.asyncio
async def test_post_chat_background_task_gets_own_session_factory(fake_session):
    """El task corre tras cerrar la sesión del request (sin RLS): debe recibir una factory."""
    ev = _make_complete_eval()
    fake_session.add(ev)
    await fake_session.commit()

    app = _make_app(fake_session)
    with patch("api.v1.chat.process_chat_turn", new_callable=AsyncMock) as proc:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                f"/api/v1/evaluations/{ev.id}/chat/messages",
                data={"content": "hola"},
            )

    kwargs = proc.call_args.kwargs
    assert "session" not in kwargs
    assert callable(kwargs["session_factory"])


@pytest.mark.asyncio
async def test_post_chat_returns_404_for_pending_eval(fake_session):
    ev = _make_complete_eval()
    ev.status = "pending"
    fake_session.add(ev)
    await fake_session.commit()

    app = _make_app(fake_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/evaluations/{ev.id}/chat/messages",
            data={"content": "hola"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_chat_returns_429_at_message_limit(fake_session):

    ev = _make_complete_eval()
    fake_session.add(ev)
    await fake_session.commit()

    for i in range(2):
        m = ChatMessage()
        m.id = uuid.uuid4()
        m.evaluation_id = ev.id
        m.role = "user" if i % 2 == 0 else "assistant"
        m.content = f"msg {i}"
        m.status = "complete"
        m.created_at = datetime.now(timezone.utc)
        m.updated_at = datetime.now(timezone.utc)
        fake_session.add(m)
    await fake_session.commit()

    app = _make_app(fake_session, max_messages_per_conversation=2)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/evaluations/{ev.id}/chat/messages",
            data={"content": "nuevo mensaje"},
        )
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_list_chat_messages(fake_session):
    ev = _make_complete_eval()
    fake_session.add(ev)
    await fake_session.commit()

    for i in range(3):
        m = ChatMessage()
        m.id = uuid.uuid4()
        m.evaluation_id = ev.id
        m.role = "user" if i % 2 == 0 else "assistant"
        m.content = f"content {i}"
        m.status = "complete"
        m.created_at = datetime.now(timezone.utc)
        m.updated_at = datetime.now(timezone.utc)
        fake_session.add(m)
    await fake_session.commit()

    app = _make_app(fake_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/evaluations/{ev.id}/chat/messages")

    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.asyncio
async def test_post_chat_returns_409_with_active_streaming_turn(fake_session):
    ev = _make_complete_eval()
    fake_session.add(ev)

    # Active streaming assistant message
    streaming_msg = ChatMessage()
    streaming_msg.id = uuid.uuid4()
    streaming_msg.evaluation_id = ev.id
    streaming_msg.role = "assistant"
    streaming_msg.content = ""
    streaming_msg.status = "streaming"
    streaming_msg.created_at = datetime.now(timezone.utc)
    streaming_msg.updated_at = datetime.now(timezone.utc)
    fake_session.add(streaming_msg)
    await fake_session.commit()

    app = _make_app(fake_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/evaluations/{ev.id}/chat/messages",
            data={"content": "segunda pregunta"},
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_post_chat_returns_404_for_nonexistent_eval(fake_session):
    app = _make_app(fake_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/evaluations/{uuid.uuid4()}/chat/messages",
            data={"content": "hola"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_chat_returns_400_for_oversized_file(fake_session, tmp_path):

    ev = _make_complete_eval()
    fake_session.add(ev)
    await fake_session.commit()

    import io
    app = _make_app(fake_session, max_file_size_bytes=10, upload_root=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/evaluations/{ev.id}/chat/messages",
            data={"content": "con archivo"},
            files={"files": ("test.txt", io.BytesIO(b"x" * 20), "text/plain")},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_attachment_is_stored_under_configured_upload_root(fake_session, tmp_path):
    """Bug: los adjuntos caian en /tmp porque nadie leia UPLOAD_ROOT de settings."""
    import io

    ev = _make_complete_eval()
    fake_session.add(ev)
    await fake_session.commit()

    app = _make_app(fake_session, upload_root=str(tmp_path))
    with patch("api.v1.chat.process_chat_turn", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/v1/evaluations/{ev.id}/chat/messages",
                data={"content": "con archivo"},
                files={"files": ("nota.txt", io.BytesIO(b"hola"), "text/plain")},
            )
    assert resp.status_code == 202
    assert [p.name for p in tmp_path.rglob("*.txt")] != []
