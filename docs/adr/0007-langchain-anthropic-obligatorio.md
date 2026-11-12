# 0007 — langchain-anthropic como único SDK LLM

**Estado:** aceptado
**Fecha:** 2026-05-23

## Contexto

Necesitamos output estructurado (Pydantic), retries integrados, y prompt caching. El SDK `anthropic` directo requiere implementar todo esto manualmente.

## Decisión

Stack LLM = `langchain-anthropic` + `ChatAnthropic.with_structured_output()`. Importar `from anthropic import Anthropic` directamente está prohibido en el codebase.

## Consecuencias

- Positivo: output validado contra Pydantic schema nativamente.
- Positivo: retry en rate-limit integrado.
- Positivo: prompt caching con `cache_control` nativo.
- Negativo: dependencia en langchain ecosystem (versión pinned).
- Negativo: overhead de abstracción (~50ms por call, negligible vs 10-30s LLM).

## Alternativas consideradas

- SDK `anthropic` directo: más control pero requiere implementar validación, retries, y caching manualmente.
- LiteLLM: agrega indirección sin ventaja para un solo proveedor.
