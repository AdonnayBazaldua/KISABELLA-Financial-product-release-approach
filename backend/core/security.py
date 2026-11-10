"""Middleware de seguridad: IP whitelist + security headers.

Nginx aplica IP whitelist primero (entrypoint renderea allow desde ALLOWED_IPS).
Este middleware es defensa-en-profundidad — si Nginx falla o se accede al
backend directamente (puerto 8000), aún rechaza IPs no autorizadas.

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
    """Extrae la IP real del cliente.

    Detrás de Nginx, real IP viene en X-Forwarded-For (primer hop) o X-Real-IP.
    Sin Nginx (acceso directo en dev), usa request.client.host.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return ""


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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Aplica headers de seguridad a TODA respuesta."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._secure = _build_secure_headers()

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        # secure 0.3: .headers() es método, retorna dict
        for header_name, header_value in self._secure.headers().items():
            response.headers[header_name] = header_value
        return response
