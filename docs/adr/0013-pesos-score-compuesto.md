# 0013 — Pesos del score compuesto

**Estado:** aceptado
**Fecha:** 2026-05-23

## Contexto

El score final de una evaluación es un promedio ponderado de los 4 agentes. Los pesos reflejan la confiabilidad y criticidad de cada dimensión de análisis.

## Decisión

| Agente | Peso |
|--------|------|
| Financiero | 0.35 |
| Mercado | 0.25 |
| Riesgo | 0.20 |
| Estrategia | 0.20 |

Constantes nombradas en `calculations/scoring.py`, no valores mágicos en el pipeline.

## Justificación

- Financiero (0.35): único agente con matemática auditable (margen, ROI, punto de equilibrio).
- Mercado (0.25): valida si la demanda real sostiene los números financieros.
- Riesgo (0.20): penaliza escenarios viable-en-papel pero frágiles.
- Estrategia (0.20): operacionaliza, pero depende de los otros tres.

## Consecuencias

- Positivo: pesos explícitos y justificados.
- Positivo: centralizados en un solo módulo.
- Negativo: requiere ADR nueva si se modifican los pesos.
