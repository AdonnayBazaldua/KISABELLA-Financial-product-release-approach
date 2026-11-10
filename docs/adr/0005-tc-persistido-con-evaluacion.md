# 0005 — TC persistido junto con la evaluación

**Estado:** aceptado
**Fecha:** 2026-05-23

## Contexto

El tipo de cambio USD/MXN fluctúa diariamente. Si una evaluación se revisa semanas después, necesitamos reproducir los cálculos con el TC que se usó originalmente, no el actual.

## Decisión

Cada evaluación persiste `exchange_rate_used` (valor numérico) y `exchange_rate_at` (timestamp de obtención). Análisis histórico siempre usa el TC persistido, nunca el actual.

## Consecuencias

- Positivo: evaluaciones comparables a través del tiempo.
- Positivo: análisis reproducible sin dependencia de API externa.
- Negativo: dos campos extra por evaluación (~16 bytes).

## Alternativas consideradas

- Usar TC actual siempre: descartado porque invalida comparaciones históricas.
- Tabla separada de TC históricos: innecesario para el volumen esperado (~50 evals/mes).

## Actualización (2026-11-10): procedencia del TC

El TC llega prellenado desde Banxico pero el usuario puede editarlo (sus costos en MXN ya se convirtieron con él). El backend lo compara con Banxico (±0.5 %) y etiqueta su procedencia en la evaluación: `banxico`, `fallback_db` (Banxico caído, último valor en memoria) o `user_provided` (difiere o no hay ningún valor). Cualquier caso distinto de `banxico` agrega el flag `warn_fx`. Banxico caído nunca rompe el pipeline.
