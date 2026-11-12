# Architecture Decision Records (ADRs)

Este directorio guarda decisiones arquitectónicas significativas tomadas durante el desarrollo de Kisabella Financial Product Release.

## Índice

| ADR | Decisión | Estado |
|---|---|---|
| [0001](0001-agentes-como-funciones-puras.md) | Agentes como funciones puras (AgentFn) | aceptado |
| [0002](0002-pipeline-state-dict-no-campos-nombrados.md) | PipelineState con dict, no campos nombrados por agente | aceptado |
| [0003](0003-validacion-llm-output-centralizada.md) | Validación LLM output centralizada en LLMClient | aceptado |
| [0004](0004-tipos-frontend-desde-openapi.md) | Tipos frontend generados desde OpenAPI | aceptado |
| [0005](0005-tc-persistido-con-evaluacion.md) | TC persistido junto con la evaluación | aceptado |
| [0006](0006-pipeline-async-backgroundtask-202.md) | Pipeline async con BackgroundTask, endpoint 202 | aceptado |
| [0007](0007-langchain-anthropic-obligatorio.md) | langchain-anthropic como único SDK LLM | aceptado |
| [0008](0008-rls-efectivo-con-force.md) | RLS efectivo con FORCE y rol no-owner | aceptado |
| [0009](0009-deploy-ionos-vps.md) | Deploy en VPS IONOS | reemplazado por ADR-0019 |
| [0010](0010-nginx-ip-whitelist-https.md) | Nginx con IP whitelist dinámica + HTTPS | retirado (ver nota) |
| [0011](0011-tools-directos-no-bind-tools.md) | Tools (Tavily/Banxico) llamados directo, no via bind_tools | aceptado |
| [0012](0012-cobertura-minima-tests.md) | Cobertura mínima 70% en agents + FakeLLMClient obligatorio | aceptado |
| [0013](0013-pesos-score-compuesto.md) | Pesos del score compuesto | aceptado |
| [0014](0014-storage-uploads-filesystem-db.md) | Storage de uploads = filesystem + metadata en DB | aceptado |
| [0015](0015-streaming-chat-sse-db-source-of-truth.md) | Streaming chat = SSE + DB como source of truth | aceptado |
| [0016](0016-markitdown-extraccion-documentos.md) | Markitdown para extracción documento → markdown | aceptado |
| [0017](0017-chat-agent-texto-libre.md) | Chat agent = texto libre, sin structured output | aceptado |
| [0018](0018-structlog-logging.md) | structlog como sistema de logging | aceptado |
| [0019](0019-sin-deploy-hosted-docker-compose-local.md) | Sin deploy hosted: Docker Compose local con API key propia | aceptado |

## Convención

`NNNN-titulo-en-kebab-case.md`, número secuencial de 4 dígitos. Una ADR nueva por cualquier decisión que afecte a 2+ sprints o cambie un contrato; una ADR reemplazada no se borra: pasa a `reemplazado por ADR-XXXX`.

## Plantilla mínima

```markdown
# NNNN — Título del ADR

**Estado:** propuesto | aceptado | reemplazado por ADR-XXXX | obsoleto
**Fecha:** YYYY-MM-DD

## Contexto

Qué fuerza nos llevó a tomar esta decisión.

## Decisión

Qué decidimos hacer.

## Consecuencias

Qué cambia (positivo y negativo) por haber tomado esta decisión.

## Alternativas consideradas

Qué otras opciones evaluamos y por qué no las elegimos.
```
