"""Async sessionmaker + dependency injection para FastAPI.

ADR-008: `app.user_id` se fija con bindparams (NUNCA f-string) al inicio de
CADA transacción, mediante un listener after_begin en la clase de sesión. Así cualquier
sesión (request, BackgroundTask, watchdog, stream) tiene contexto RLS y un
commit/rollback intermedio no lo pierde (set_config es transaccional).

Patrón de uso:
    from fastapi import Depends
    from db.session import get_db

    @router.get("/evaluations")
    async def list_evals(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Evaluation))
        return result.scalars().all()

Lifecycle:
- engine se inicializa lazy en el primer get_db().
- dispose_engine() se llama en el lifespan shutdown de FastAPI.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from sqlalchemy.orm import Session

from core.config import get_settings

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


class _RLSSession(Session):
    """Sesión sync interna de AsyncSession; existe solo para colgarle el listener."""


@event.listens_for(_RLSSession, "after_begin")
def _set_rls_user(_session, _transaction, conn) -> None:
    """Fija el usuario de RLS para la transacción que empieza."""
    conn.execute(
        text("SELECT set_config('app.user_id', :uid, true)"),
        {"uid": get_settings().app_user_id},
    )


def _ensure_engine() -> async_sessionmaker[AsyncSession]:
    """Lazy init del engine + sessionmaker. Idempotente."""
    global _engine, _session_maker
    if _session_maker is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            # Echo solo en DEBUG para no inundar logs
            echo=(settings.log_level == "DEBUG"),
        )
        _session_maker = async_sessionmaker(
            _engine,
            expire_on_commit=False,
            class_=AsyncSession,
            sync_session_class=_RLSSession,
        )
    return _session_maker


async def get_db() -> AsyncIterator[AsyncSession]:
    """Async dependency para FastAPI. Commit al cerrar OK, rollback en excepción."""
    async with _ensure_engine()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Cierra el pool de conexiones. Llamar en lifespan shutdown."""
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_maker = None
