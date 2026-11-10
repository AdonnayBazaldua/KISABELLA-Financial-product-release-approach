# 0011 — Tools (Tavily/Banxico) llamados directo, no via bind_tools

**Estado:** aceptado
**Fecha:** 2026-05-23

## Contexto

LangChain ofrece `ChatAnthropic.bind_tools()` para que el LLM decida cuándo llamar herramientas. Para nuestro caso, las llamadas son determinísticas: Mercado siempre busca en Tavily, el pipeline siempre obtiene TC de Banxico.

## Decisión

Las herramientas (Tavily, Banxico) se llaman directamente desde el agente antes del LLM call. No se usa `bind_tools()`. El resultado se inyecta en el prompt como contexto.

## Consecuencias

- Positivo: determinístico — siempre se llama, sin dependencia de que el LLM "decida".
- Positivo: cache controlado (24h Tavily, 1h Banxico).
- Positivo: prompts más cortos (sin tool definitions en el system prompt).
- Negativo: menos flexible si se quisiera que el LLM decida cuándo buscar.

## Alternativas consideradas

- `bind_tools()`: no-determinístico, agrega tokens al prompt, y complica el cache.
- Tool calling condicional: complejidad innecesaria para herramientas fijas por agente.
