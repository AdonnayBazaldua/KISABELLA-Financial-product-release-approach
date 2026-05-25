"""FastAPI app entrypoint para CAPI-KISABELLA.

Lifespan:
- Startup: valida settings (crash si falta required), no carga DB lazy.
- Shutdown: dispose_engine() limpia pool de conexiones.

Middleware (orden importa):
1. SecurityHeadersMiddleware — headers en TODA respuesta (incluido errors)
2. IPWhitelistMiddleware     — defensa-en-profundidad (Nginx es primera capa)
3. CORSMiddleware            — orígenes estrictos desde settings

Endpoints:
- GET /health — liveness probe (público, sin IP check)
- /api/v1/* — TODO endpoints (en T0.11 se suma /evaluations)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.security import IPWhitelistMiddleware, SecurityHeadersMiddleware
from db.session import dispose_engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: fuerza validación de settings ahora (no en primer request)
    get_settings()
    yield
    # Shutdown
    await dispose_engine()


def create_app() -> FastAPI:
    """Factory pattern — facilita testing con settings overrideables."""
    settings = get_settings()

    app = FastAPI(
        title="CAPI-KISABELLA",
        description="Evaluador de viabilidad de productos físicos (multi-agente LLM)",
        version="0.1.0-rebuild",
        lifespan=lifespan,
    )

    # Orden de middleware: el ÚLTIMO add_middleware es el PRIMERO en ejecutarse.
    # Queremos: CORS → IP whitelist → security headers → app
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(IPWhitelistMiddleware, allowed_ips=settings.allowed_ips)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.next_public_api_url],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-Id"],
    )

    @app.get("/health", tags=["meta"])
    async def health():
        return {"status": "ok", "version": app.version}

    return app


app = create_app()
