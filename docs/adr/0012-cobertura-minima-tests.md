# 0012 — Cobertura mínima 70% en agents + FakeLLMClient obligatorio

**Estado:** aceptado
**Fecha:** 2026-05-23

## Contexto

El Sprint 1 tenía tests esqueléticos que no cubrían el path crítico (POST /evaluations). Regresiones se detectaban en producción.

## Decisión

- Cobertura mínima `backend/agents/`: 70%. PR no mergea por debajo.
- `FakeLLMClient` en `conftest.py` obligatorio para tests de agentes.
- Cero llamadas de red en CI (Tavily, Banxico, Anthropic todos mockeados).
- Path crítico (POST → pipeline → complete) tiene test E2E.

## Consecuencias

- Positivo: regresiones detectadas antes de merge.
- Positivo: CI rápido y determinístico (sin red).
- Positivo: `FakeLLMClient` permite testear lógica de agentes sin costo.
- Negativo: overhead de mantener mocks actualizados al cambiar schemas.

## Alternativas consideradas

- Tests con LLM real: no-determinísticos, lentos, costosos, imposibles en CI.
- Sin coverage gate: riesgo de regresión al umbral del Sprint 1.
