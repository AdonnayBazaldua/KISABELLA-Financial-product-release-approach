# 0015 — Streaming chat = SSE + DB como source of truth

**Estado:** aceptado
**Fecha:** 2026-05-29

## Contexto

El chat de seguimiento requiere respuestas token-por-token. Necesitamos decidir
cómo entregar el stream al frontend y cómo garantizar persistencia si el cliente desconecta.

## Decisión

Tokens emitidos vía SSE desde una `asyncio.Queue` en memoria mientras el BackgroundTask corre.
Tokens también persistidos en DB de forma periódica (flush cada ~50 chars).
Si el cliente reconecta después de que el turn completó, lee directamente desde DB.

## Por qué

- Sin Redis ni state externo (coherente con ADR-009).
- BackgroundTask completa aunque nadie escuche el SSE — resultado persiste siempre.
- Reconexión robusta: si el cliente llega tarde, el SSE endpoint lee DB y emite `complete` inmediato.
- Queue en memoria es transitoria: solo existe mientras el background task está vivo.

## Consecuencias

- Si el proceso se reinicia durante un turno activo, el cliente SSE recibe `STREAM_UNAVAILABLE`.
  El orphan watchdog (60s) marcará el mensaje como `error` en 3 minutos.
- Sin cache de tokens: si el SSE client desconecta y el task sigue corriendo, los tokens
  se acumulan en la queue (cap: 2000) antes de que el cliente reconecte.
