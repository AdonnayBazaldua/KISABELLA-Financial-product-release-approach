# 0006 — Pipeline async con BackgroundTask, endpoint 202

**Estado:** aceptado
**Fecha:** 2026-05-23

## Contexto

El pipeline ejecuta 4 agentes LLM en paralelo (~30-60s). El Sprint 1 ejecutaba el pipeline dentro del request handler, causando timeouts de Nginx (60s default) y UX congelada.

## Decisión

POST `/api/evaluations` devuelve HTTP 202 Accepted inmediatamente con `{evaluation_id, status:"pending"}`. El pipeline corre en `BackgroundTask` de FastAPI. Frontend hace polling cada 2s sobre GET `/api/evaluations/{id}`.

## Consecuencias

- Positivo: sin timeout de Nginx ni UX congelada.
- Positivo: el frontend muestra progreso por agente (sub-estados).
- Negativo: complejidad de polling y estados transitorios.
- Negativo: necesita watchdog para evaluaciones huérfanas (status=running >5min).

## Alternativas consideradas

- SSE/WebSocket: programado para Sprint 5, overkill para Fase 0.
- Celery/RQ: infraestructura extra innecesaria para 2-3 usuarios.
