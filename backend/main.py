"""FastAPI app entrypoint para CAPI-KISABELLA.

Lifespan:
- Startup: valida settings, configura structlog, lanza watchdogs.
- Shutdown: dispose_engine() limpia pool de conexiones.

Middleware (orden importa — el último add_middleware es el primero en ejecutarse):
1. SecurityHeadersMiddleware
2. IPWhitelistMiddleware
3. CORSMiddleware
4. CorrelationIdMiddleware (inyecta correlation_id en contexto structlog)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from api.v1.chat import router as chat_router
from api.v1.evaluations import router as evaluations_router
from api.v1.exchange_rate import router as tc_router
from core.config import get_settings
from core.security import IPWhitelistMiddleware, SecurityHeadersMiddleware
from db.session import dispose_engine


def _configure_structlog(log_level: str) -> None:
    """Configura structlog una sola vez al startup."""
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if log_level == "DEBUG":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Inyecta correlation_id en el contexto de structlog por cada request."""

    async def dispatch(self, request: Request, call_next):
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=str(uuid.uuid4()),
            path=request.url.path,
        )
        response = await call_next(request)
        return response


async def _chat_orphan_watchdog() -> None:
    """Marca mensajes de chat atascados como error cada 60s."""
    from sqlalchemy import text as sql_text

    from db.session import _ensure_engine

    log = structlog.get_logger()
    while True:
        await asyncio.sleep(60)
        try:
            settings = get_settings()
            maker = _ensure_engine()
            async with maker() as session:
                await session.execute(
                    sql_text("SELECT set_config('app.user_id', :uid, true)").bindparams(
                        uid=settings.app_user_id
                    )
                )
                await session.execute(
                    sql_text("""
                    UPDATE chat_messages
                    SET status = 'error',
                        error_msg = 'Tiempo de espera agotado (watchdog)',
                        updated_at = NOW()
                    WHERE role = 'assistant'
                      AND status = 'streaming'
                      AND created_at < NOW() - INTERVAL '3 minutes'
                """)
                )
                await session.commit()
        except Exception as exc:
            log.warning("chat_watchdog_error", error=str(exc))


async def _eval_orphan_watchdog() -> None:
    """Marca evaluaciones atascadas en status=running como error cada 60s."""
    from sqlalchemy import text as sql_text

    from db.session import _ensure_engine

    log = structlog.get_logger()
    while True:
        await asyncio.sleep(60)
        try:
            settings = get_settings()
            maker = _ensure_engine()
            async with maker() as session:
                await session.execute(
                    sql_text("SELECT set_config('app.user_id', :uid, true)").bindparams(
                        uid=settings.app_user_id
                    )
                )
                result = await session.execute(
                    sql_text("""
                    UPDATE evaluations
                    SET status = 'error',
                        error_message = 'ORPHANED',
                        updated_at = NOW()
                    WHERE status = 'running'
                      AND updated_at < NOW() - INTERVAL '5 minutes'
                    RETURNING id
                """)
                )
                count = len(result.fetchall())
                await session.commit()
                if count:
                    log.warning("orphaned_evaluations_marked", count=count)
        except Exception as exc:
            log.warning("eval_watchdog_error", error=str(exc))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    _configure_structlog(settings.log_level)
    log = structlog.get_logger()
    log.info("app_startup", version=_app.version)
    asyncio.create_task(_chat_orphan_watchdog())
    asyncio.create_task(_eval_orphan_watchdog())
    yield
    await dispose_engine()
    log.info("app_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="CAPI-KISABELLA",
        description="Evaluador de viabilidad de productos físicos (multi-agente LLM)",
        version="0.1.0-rebuild",
        lifespan=lifespan,
    )

    # Orden: el ÚLTIMO add_middleware es el PRIMERO en ejecutarse.
    # Queremos: CORS → IP whitelist → security headers → correlation_id → app
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(IPWhitelistMiddleware, allowed_ips=settings.allowed_ips)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-Id"],
    )

    @app.get("/health", tags=["meta"])
    async def health():
        return {"status": "ok", "version": app.version}

    app.include_router(evaluations_router)
    app.include_router(chat_router)
    app.include_router(tc_router)

    return app


app = create_app()
