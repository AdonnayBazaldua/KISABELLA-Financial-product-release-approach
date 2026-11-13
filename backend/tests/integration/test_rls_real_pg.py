"""RLS efectivo contra Postgres REAL (ADR-008).

Skip salvo que existan TEST_PG_OWNER_URL y TEST_PG_APP_URL (formato asyncpg
sin "+driver": postgresql://user:pw@host:port/db). Corre con scripts/test-rls.sh.
"""

import os
import subprocess
import sys
import uuid

import asyncpg
import pytest

OWNER = os.getenv("TEST_PG_OWNER_URL")
APP = os.getenv("TEST_PG_APP_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not (OWNER and APP), reason="requiere Postgres real"),
]

U1 = "00000000-0000-0000-0000-000000000001"
U2 = str(uuid.uuid4())


@pytest.fixture(scope="module", autouse=True)
def migrated():
    env = {
        **os.environ,
        "DATABASE_URL": APP.replace("postgresql://", "postgresql+asyncpg://"),
        "MIGRATION_DATABASE_URL": OWNER.replace("postgresql://", "postgresql+asyncpg://"),
        "ANTHROPIC_API_KEY": "x",
    }
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)


async def _app_conn(uid):
    conn = await asyncpg.connect(APP)
    if uid:
        await conn.execute("SELECT set_config('app.user_id', $1, false)", uid)
    return conn


async def test_app_role_is_not_superuser_nor_owner():
    conn = await _app_conn(None)
    row = await conn.fetchrow(
        "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
    )
    owner = await conn.fetchval("SELECT tableowner FROM pg_tables WHERE tablename='evaluations'")
    assert not row["rolsuper"] and not row["rolbypassrls"]
    assert owner != (await conn.fetchval("SELECT current_user"))


async def test_rows_invisible_without_or_with_wrong_user():
    owner = await asyncpg.connect(OWNER)
    eid = await owner.fetchval(
        "INSERT INTO evaluations (created_by, name) VALUES ($1, 'rls') RETURNING id",
        uuid.UUID(U1),
    )
    for uid, expected in ((None, 0), (U2, 0), (U1, 1)):
        conn = await _app_conn(uid)
        n = await conn.fetchval("SELECT count(*) FROM evaluations WHERE id = $1", eid)
        assert n == expected, f"uid={uid}"


async def test_cannot_insert_row_for_another_user():
    conn = await _app_conn(U2)
    with pytest.raises(asyncpg.PostgresError):
        await conn.execute(
            "INSERT INTO evaluations (created_by, name) VALUES ($1, 'x')", uuid.UUID(U1)
        )


def _real_settings(monkeypatch):
    """Settings y engine reales contra el Postgres de prueba, con el rol NO-dueño."""
    from core.config import Settings
    import db.session as dbs

    monkeypatch.setenv("DATABASE_URL", APP.replace("postgresql://", "postgresql+asyncpg://"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("APP_USER_ID", U1)
    settings = Settings(_env_file=None)
    monkeypatch.setattr(dbs, "get_settings", lambda: settings)  # conftest parchea con un fake
    dbs._engine = dbs._session_maker = None
    return settings


async def _chat_turn(monkeypatch, llm):
    from agents.chat import process_chat_turn
    from api.v1.evaluations import get_background_session_factory
    import db.session as dbs

    _real_settings(monkeypatch)

    owner = await asyncpg.connect(OWNER)
    eid = await owner.fetchval(
        "INSERT INTO evaluations (created_by, name, status) VALUES ($1, 'chat', 'complete') RETURNING id",
        uuid.UUID(U1),
    )
    umsg, amsg = [
        await owner.fetchval(
            "INSERT INTO chat_messages (evaluation_id, role, content, status) "
            "VALUES ($1, $2, $3, $4) RETURNING id", eid, role, content, status)
        for role, content, status in (("user", "hola", "complete"), ("assistant", "", "streaming"))
    ]
    await process_chat_turn(
        evaluation_id=eid, user_msg_id=umsg, assistant_msg_id=amsg, llm=llm,
        session_factory=get_background_session_factory(),
    )
    row = await owner.fetchrow("SELECT status, content FROM chat_messages WHERE id = $1", amsg)
    await dbs.dispose_engine()
    return row


async def test_chat_turn_completes_under_rls_with_own_session(monkeypatch):
    """Bug: el BackgroundTask del chat usaba la sesión (cerrada, sin RLS) del request."""
    from agents.llm_client import FakeLLMClient

    llm = FakeLLMClient()
    llm.queue_stream(["resp ", "ok"])
    row = await _chat_turn(monkeypatch, llm)
    assert (row["status"], row["content"]) == ("complete", "resp ok")


async def test_chat_turn_error_is_persisted_under_rls(monkeypatch):
    """Tras el rollback del error se pierde el set_config transaccional: debe re-aplicarse."""
    from agents.llm_client import FakeLLMClient

    llm = FakeLLMClient()
    llm.queue_stream_error(RuntimeError("boom"))
    row = await _chat_turn(monkeypatch, llm)
    assert row["status"] == "error"


async def test_chat_stream_endpoint_reads_message_under_rls(monkeypatch):
    """Bug: el generador SSE usaba la sesión del request, ya cerrada y sin contexto RLS,
    y respondía "Mensaje no encontrado" aunque el mensaje existiera."""
    import httpx
    from fastapi import FastAPI

    import core.config as cc
    import db.session as dbs
    from api.v1.chat import router

    settings = _real_settings(monkeypatch)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[cc.get_settings] = lambda: settings

    owner = await asyncpg.connect(OWNER)
    eid = await owner.fetchval(
        "INSERT INTO evaluations (created_by, name, status) VALUES ($1, 'sse', 'complete') RETURNING id",
        uuid.UUID(U1),
    )
    mid = await owner.fetchval(
        "INSERT INTO chat_messages (evaluation_id, role, content, status) "
        "VALUES ($1, 'assistant', 'hola', 'complete') RETURNING id", eid)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(f"/api/v1/evaluations/{eid}/chat/messages/{mid}/stream")
    await dbs.dispose_engine()

    assert "event: complete" in r.text and "hola" in r.text


async def test_rls_context_survives_commit_in_same_session(monkeypatch):
    """set_config es transaccional: tras un commit la misma sesión debe seguir viendo sus filas."""
    import db.session as dbs
    from sqlalchemy import text

    _real_settings(monkeypatch)
    owner = await asyncpg.connect(OWNER)
    eid = await owner.fetchval(
        "INSERT INTO evaluations (created_by, name) VALUES ($1, 'tx') RETURNING id", uuid.UUID(U1)
    )
    async for session in dbs.get_db():
        q = text("SELECT count(*) FROM evaluations WHERE id = :id")
        assert (await session.execute(q, {"id": eid})).scalar_one() == 1
        await session.commit()
        assert (await session.execute(q, {"id": eid})).scalar_one() == 1
    await dbs.dispose_engine()
