"""Middleware de seguridad: IP whitelist + security headers.

La whitelist (ALLOWED_IPS) rechaza con 403 cualquier IP no listada; vacía = sin restricción.

Headers de seguridad via la lib `secure`:
- Strict-Transport-Security (HSTS)
- X-Frame-Options (clickjacking)
- X-Content-Type-Options (MIME sniffing)
- Content-Security-Policy (XSS mitigation)
- Referrer-Policy
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

import secure as secure_lib


def _build_secure_headers() -> secure_lib.Secure:
    """Configuración estricta de security headers (secure 0.3 API)."""
    return secure_lib.Secure(
        hsts=secure_lib.StrictTransportSecurity()
        .max_age(63072000)  # 2 años
        .include_subdomains()
        .preload(),
        xfo=secure_lib.XFrameOptions().deny(),
        content=secure_lib.XContentTypeOptions(),  # default = nosniff
        csp=secure_lib.ContentSecurityPolicy()
        .default_src("'self'")
        .frame_ancestors("'none'"),
        referrer=secure_lib.ReferrerPolicy().strict_origin_when_cross_origin(),
    )


def _client_ip(request: Request) -> str:
    """IP del extremo TCP. Los encabezados X-Forwarded-For / X-Real-IP NO se leen aquí:
    cualquiera puede falsificarlos. Detrás de un reverse proxy, uvicorn reescribe
    request.client solo para proxies de confianza (--forwarded-allow-ips / FORWARDED_ALLOW_IPS).
    """
    return request.client.host if request.client else ""


def _parse_allowed(allowed_csv: str) -> set[str]:
    return {ip.strip() for ip in allowed_csv.split(",") if ip.strip()}


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """Rechaza IPs no whitelisted con 403. /health excluido."""

    HEALTH_PATHS = {"/health", "/healthz", "/api/health"}

    def __init__(self, app: ASGIApp, allowed_ips: str) -> None:
        super().__init__(app)
        self._allowed = _parse_allowed(allowed_ips)

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.HEALTH_PATHS:
            return await call_next(request)

        if not self._allowed:
            return await call_next(request)

        client = _client_ip(request)
        if client not in self._allowed:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "IP no autorizada",
                    "code": "IP_NOT_WHITELISTED",
                },
            )
        return await call_next(request)


# Swagger UI / ReDoc cargan JS y CSS desde un CDN y usan un script inline.
_DOCS_PATHS = {"/docs", "/redoc"}
_DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly; "
    "worker-src blob:; frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Aplica headers de seguridad a TODA respuesta (CSP relajado solo en la documentación)."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._secure = _build_secure_headers()

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        # secure 0.3: .headers() es método, retorna dict
        for header_name, header_value in self._secure.headers().items():
            response.headers[header_name] = header_value
        if request.url.path in _DOCS_PATHS:
            response.headers["Content-Security-Policy"] = _DOCS_CSP
        return response
