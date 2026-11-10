# 0003 — Validación LLM output centralizada en LLMClient

**Estado:** aceptado
**Fecha:** 2026-05-23

## Contexto

Los agentes del Sprint 1 parseaban JSON de LLM con `json.loads` ad-hoc, resultando en múltiples superficies de error y validación inconsistente.

## Decisión

Todo output de LLM se valida con Pydantic en `LLMClient.request_structured()` usando `ChatAnthropic.with_structured_output(schema)`. No existe `json.loads` ad-hoc en código de agentes.

## Consecuencias

- Positivo: una sola superficie de validación, error handling uniforme.
- Positivo: el LLM genera output conforme al schema o falla con error claro.
- Negativo: dependencia fuerte en `langchain-anthropic` para structured output.

## Alternativas consideradas

- `json.loads` + validación manual: descartado por duplicación y fragilidad.
- Instructor library: agrega dependencia sin ventaja sobre `with_structured_output` nativo.
