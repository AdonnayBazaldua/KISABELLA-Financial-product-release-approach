# 0017 — Chat agent = texto libre, sin structured output

**Estado:** aceptado
**Fecha:** 2026-05-29

## Contexto

El pipeline de evaluación usa `with_structured_output(PydanticSchema)` para obtener outputs
validados con fields específicos (score, veredicto_corto, etc.). El chat de seguimiento
requiere un enfoque diferente.

## Decisión

`LLMClient.stream_text()` retorna `AsyncGenerator[str, None]` — texto libre token a token.
Sin `with_structured_output`, sin Pydantic schema de respuesta.
Temperature 0.4 (vs 0.2 para agentes de evaluación).
El "schema" del output es el system prompt + reglas en `agents/prompts/chat.md`.

## Por qué

- Streaming token-por-token (`llm.astream()`) es incompatible con function-calling structured output —
  Anthropic no soporta ambas cosas simultáneamente.
- Q&A conversacional requiere prosa libre, tablas markdown y respuestas contextuales;
  no hay shape Pydantic que modele eso.
- Temperature 0.4: más creativo que los agentes (0.2) pero aún determinista para análisis.

## Consecuencias

- No hay validación automática del output por Pydantic — el quality gate es el system prompt.
- Si el LLM ignora las reglas del prompt (longitud, idioma), no hay enforcement automático.
- Extensiones futuras (citar fuentes, output estructurado parcial) requerirían ADR nuevo.
