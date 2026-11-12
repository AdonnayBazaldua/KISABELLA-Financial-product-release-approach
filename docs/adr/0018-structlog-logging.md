# 0018 — structlog como sistema de logging

**Fecha:** 2026-05-30
**Estado:** aceptado

## Contexto

El proyecto necesita logging estructurado con campos consistentes para observabilidad en producción. Python `logging` estándar no garantiza formato JSON ni campos obligatorios por call.

## Decisión

Usar `structlog>=24.0` como librería de logging.

- **JSON renderer** en producción (`LOG_LEVEL != "DEBUG"`).
- **ConsoleRenderer** en desarrollo para legibilidad.
- **Campos obligatorios** por LLM call: `schema`, `tokens_estimated`, `calls_used`.
- **Campos obligatorios** por agente: `agent_name`, `evaluation_id`, `duration_ms`.
- **`correlation_id`** inyectado por `CorrelationIdMiddleware` en cada request HTTP.
- Configuración única en `_configure_structlog()` llamada desde el lifespan.
- NUNCA loguear API keys, contenido de prompts ni PII.

## Consecuencias

+ Logs JSON en producción son parseables por cualquier agregador (Datadog, Loki, etc.).
+ `correlation_id` permite trazar un request completo sin pasar el ID manualmente.
- Token counts son estimaciones (`(len(system) + len(user)) // 4`), no valores exactos de la API.
