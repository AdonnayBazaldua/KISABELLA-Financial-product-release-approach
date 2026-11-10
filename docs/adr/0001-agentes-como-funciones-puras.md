# 0001 — Agentes como funciones puras (AgentFn)

**Estado:** aceptado
**Fecha:** 2026-05-23

## Contexto

Necesitamos componer agentes especialistas en un pipeline paralelo (LangGraph). El Sprint 1 usaba clases con herencia que acoplaban estado, hacían difícil el testing, y no permitían composición flexible.

## Decisión

Cada agente es una función pura con firma:

```python
AgentFn = Callable[[EvaluationInputs, LLMClient, ToolRegistry], Awaitable[AgentResult]]
```

Se construyen con `build_agent()` factory. No hay clases, no hay herencia, no hay estado mutable.

## Consecuencias

- Positivo: composability directa con LangGraph nodes.
- Positivo: testeable inyectando `FakeLLMClient` sin monkeypatching.
- Positivo: agregar un agente nuevo = 1 línea en el registry.
- Negativo: no hay lifecycle hooks (pre/post) — si se necesitan, van en el pipeline, no en el agente.

## Alternativas consideradas

- Clases con herencia (Sprint 1): descartado por acoplamiento y dificultad de test.
- Protocol/ABC: más estructura de la necesaria para 4 agentes.
