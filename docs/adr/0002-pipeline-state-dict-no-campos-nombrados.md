# 0002 — PipelineState con dict, no campos nombrados por agente

**Estado:** aceptado
**Fecha:** 2026-05-23

## Contexto

El estado del pipeline necesita almacenar resultados de N agentes. Opciones: un campo por agente (`financiero_result`, `mercado_result`, ...) o un dict genérico.

## Decisión

`PipelineState.agent_results: dict[str, AgentResult | AgentError]`. Sin campos nombrados por agente.

## Consecuencias

- Positivo: agregar un agente = 1 línea en el registry, sin tocar PipelineState.
- Positivo: lógica de fan-in genérica (iterar dict).
- Negativo: sin autocompletado por nombre de agente (mitigado con constantes en el registry).

## Alternativas consideradas

- Campos nombrados: descartado porque cada agente nuevo requiere modificar PipelineState, tests, y serialización.
