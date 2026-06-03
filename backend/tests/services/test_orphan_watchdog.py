"""Tests del orphan watchdog de evaluaciones.

Verifica la lógica SQL: evaluaciones con status='running' y updated_at > 5 minutos
se marcan como error='ORPHANED'. Evaluaciones recientes o con otro status no se tocan.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text as sql_text

from db.models import Evaluation, AppUser


async def _run_watchdog_sql(session) -> int:
    """Ejecuta el mismo SQL que _eval_orphan_watchdog en main.py."""
    result = await session.execute(
        sql_text("""
            UPDATE evaluations
            SET status = 'error',
                error_message = 'ORPHANED',
                updated_at = :now
            WHERE status = 'running'
              AND updated_at < :cutoff
        """).bindparams(
            now=datetime.now(timezone.utc),
            cutoff=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
    )
    await session.commit()
    return result.rowcount


@pytest.mark.asyncio
async def test_orphan_eval_gets_marked_error(fake_session):
    """Evaluación con status=running y updated_at > 5min se marca error=ORPHANED."""
    eval_id = uuid.uuid4()
    user_id = uuid.uuid4()
    old_time = datetime.now(timezone.utc) - timedelta(minutes=10)

    # Create the user first
    user = AppUser(id=user_id, username="testuser")
    fake_session.add(user)
    await fake_session.flush()

    ev = Evaluation(
        id=eval_id,
        created_by=user_id,
        name="Test Huérfana",
        status="running",
        updated_at=old_time,
    )
    fake_session.add(ev)
    await fake_session.flush()

    count = await _run_watchdog_sql(fake_session)

    assert count == 1
    # Refresh from database after commit
    await fake_session.refresh(ev)
    assert ev.status == "error"
    assert ev.error_message == "ORPHANED"


@pytest.mark.asyncio
async def test_recent_running_eval_not_marked(fake_session):
    """Evaluación running reciente (< 5min) NO se toca."""
    eval_id = uuid.uuid4()
    user_id = uuid.uuid4()
    recent_time = datetime.now(timezone.utc) - timedelta(minutes=1)

    # Create the user first
    user = AppUser(id=user_id, username="testuser2")
    fake_session.add(user)
    await fake_session.flush()

    ev = Evaluation(
        id=eval_id,
        created_by=user_id,
        name="Recent Running",
        status="running",
        updated_at=recent_time,
    )
    fake_session.add(ev)
    await fake_session.flush()

    count = await _run_watchdog_sql(fake_session)

    assert count == 0
    refreshed = await fake_session.get(Evaluation, eval_id)
    assert refreshed.status == "running"


@pytest.mark.asyncio
async def test_complete_eval_not_affected(fake_session):
    """Evaluación complete no se toca aunque tenga updated_at antiguo."""
    eval_id = uuid.uuid4()
    user_id = uuid.uuid4()
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)

    # Create the user first
    user = AppUser(id=user_id, username="testuser3")
    fake_session.add(user)
    await fake_session.flush()

    ev = Evaluation(
        id=eval_id,
        created_by=user_id,
        name="Done Eval",
        status="complete",
        updated_at=old_time,
    )
    fake_session.add(ev)
    await fake_session.flush()

    count = await _run_watchdog_sql(fake_session)

    assert count == 0
    refreshed = await fake_session.get(Evaluation, eval_id)
    assert refreshed.status == "complete"
