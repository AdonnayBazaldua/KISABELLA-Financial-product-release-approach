# 0010 — Nginx con IP whitelist dinámica + HTTPS

**Estado:** aceptado
**Fecha:** 2026-05-23

## Contexto

La aplicación es interna (2-3 usuarios). Necesitamos restringir acceso por IP sin hardcodear IPs en archivos versionados, y HTTPS obligatorio para proteger tokens en tránsito.

## Decisión

- `ALLOWED_IPS` en `.env` (CSV de IPs).
- `docker/nginx/entrypoint.sh` renderea directivas `allow/deny` desde la env var al startup.
- HTTPS vía Let's Encrypt con auto-renewal. HTTP redirige a HTTPS.
- Rate limiting: 20 req/min por IP.
- HSTS con max-age 2 años.

## Consecuencias

- Positivo: configuración versionada sin secrets en git.
- Positivo: cambiar IPs = editar `.env` + restart nginx, sin rebuild.
- Positivo: defensa en profundidad (Nginx + middleware FastAPI).
- Negativo: IPs dinámicas requieren actualización manual del `.env`.

## Alternativas consideradas

- Cloudflare Access: agrega dependencia externa y costo.
- VPN (WireGuard): complejidad de setup para 2-3 usuarios.
- Solo middleware FastAPI: sin Nginx se pierde rate limiting eficiente y TLS termination.
