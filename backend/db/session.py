"""Async sessionmaker + dependency injection para FastAPI.

ADR-008: setea `app.user_id` via bindparams (NUNCA f-string) al inicio
de cada transacción. RLS efectivo depende de este flag.

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

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


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
            _engine, expire_on_commit=False, class_=AsyncSession
        )
    return _session_maker


async def get_db() -> AsyncIterator[AsyncSession]:
    """Async dependency para FastAPI.

    Setea `app.user_id` por sesión via bindparams (RLS context).
    Hace commit al cerrar OK, rollback en excepción.
    """
    maker = _ensure_engine()
    settings = get_settings()

    async with maker() as session:
        # set_config(name, value, is_local=true) → scope transaccional.
        # bindparams obligatorio (ADR-008) — f-string sería SQL injection.
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": settings.app_user_id},
        )
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
