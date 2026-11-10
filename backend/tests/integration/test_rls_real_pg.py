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
        "SECRET_KEY": "x" * 32,
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
