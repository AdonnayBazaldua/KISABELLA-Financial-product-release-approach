# CAPI-KISABELLA — Audit del Sistema (post-Sprint 3)

> Fecha: 2026-05-27 | Branch: chore/rebuild-fase-0 | Tests: 226 | Coverage agents/: 97%

---

## Mapa de Componentes

### BACKEND — `backend/`

#### Capa: Agentes (`agents/`)

| Archivo | Estado | Cobertura | Descripcion |
|---------|--------|-----------|-------------|
| `contracts.py` | COMPLETO | 100% | EvaluationInputs, AgentResult, AgentError, FinalVerdict, OrchestratorSynthesis, PipelineState, TCMetadata. Literales de dominio. LangGraph reducers. |
| `base.py` | COMPLETO | 98% | Factory `build_agent()`: compone prompt + calc_fn + score_fn. `load_prompt()` parsea .md. `AgentFn` type. |
| `llm_client.py` | COMPLETO | 98% | `LLMClient` Protocol, `AnthropicLLMClient` (real, con tenacity retry), `FakeLLMClient` (test double FIFO), `BudgetedLLMClient` (6 calls / 20k tokens cap). |
| `financial.py` | COMPLETO | 100% | `financial_agent = build_agent(calc_fn=calculate_financials, score_fn=_score_override)`. Score deterministico. |
| `market.py` | COMPLETO | 100% | `market_agent = build_agent(calc_fn=calculate_market)`. Score del LLM. |
| `risk.py` | COMPLETO | 100% | `risk_agent = build_agent(calc_fn=calculate_risk)`. Score del LLM. |
| `strategy.py` | COMPLETO | 100% | `strategy_agent = build_agent()`. Sin calc_fn, puro LLM. |
| `orchestrator.py` | COMPLETO | 95% | Async `synthesize_verdict(state, llm)`. LLM genera justificacion rica (>=3 OK). Fallback mecanico. Score/veredicto siempre deterministicos. |
| `pipeline.py` | COMPLETO | 98% | LangGraph DAG: fan-out 4 agentes -> fan-in orquestador. `BudgetedLLMClient` wraps LLM. 90s timeout por agente. |

#### Capa: Calculos (`agents/calculations/`)

| Archivo | Estado | Cobertura | Descripcion |
|---------|--------|-----------|-------------|
| `financial.py` | COMPLETO | 97% | Margen bruto/neto, ROI, break-even, payback, sensibilidad TC. Score deterministico 0-100. |
| `market.py` | COMPLETO | 98% | Ratio competitividad precio, margen vs sector, volume tier. Umbrales editables. |
| `risk.py` | COMPLETO | 93% | Exposicion TC %, concentracion costos, margen seguridad TC (binary search), risk flags. |
| `scoring.py` | COMPLETO | 96% | Pesos: Fin 0.35, Merc 0.25, Riesgo 0.20, Estr 0.20. Degradacion graceful. `verdict_from_score`. |

#### Capa: Prompts (`agents/prompts/`)

| Archivo | Estado | Descripcion |
|---------|--------|-------------|
| `financial.md` | COMPLETO | Analista financiero. Recibe FinancialCalcs pre-calculados. |
| `market.md` | COMPLETO | Analista de mercado. Recibe MarketCalcs (ratio, margin_vs_sector, volume_tier). |
| `risk.md` | COMPLETO | Analista de riesgo. Recibe RiskCalcs (tc_exposure, concentration, safety, flags). |
| `strategy.md` | COMPLETO | Consultor estrategia. Sin calc_fn, contexto enriquecido. |
| `orchestrator.md` | COMPLETO | Sintetizador ejecutivo. Recibe 4 analisis + score + veredicto. |

#### Capa: API (`api/`)

| Archivo | Estado | Cobertura | Descripcion |
|---------|--------|-----------|-------------|
| `v1/evaluations.py` | COMPLETO | 100% | POST 202 + GET polling + GET list. Idempotency 409. BackgroundTask. |
| `v1/schemas.py` | COMPLETO | 100% | Request/Response Pydantic: CreateEvaluationRequest, EvaluationDetail, EvaluationSummary, AgentResultDTO. |
| `exchange_rate.py` | STUB | 0% | Placeholder para Sprint 6 (Banxico real). Solo estructura. |

#### Capa: Services (`services/`)

| Archivo | Estado | Cobertura | Descripcion |
|---------|--------|-----------|-------------|
| `evaluation_service.py` | COMPLETO | 69% | Orquesta DB + pipeline. create() con idempotency hash 30s. run_pipeline() con BackgroundTask. Persiste warn_flags + requires_human_review. |

**Nota:** 69% cobertura porque `run_pipeline()` y `_persist_results()` requieren DB real para test completo. Los paths criticos (create, get_detail, list) estan cubiertos. Sprint 6 agrega tests de integracion.

#### Capa: DB (`db/`)

| Archivo | Estado | Cobertura | Descripcion |
|---------|--------|-----------|-------------|
| `models.py` | COMPLETO | 100% | AppUser, Evaluation (con warn_flags, requires_human_review, idempotency_hash), EvaluationInput, AgentResult, ChatMessage. |
| `session.py` | COMPLETO | 100% | Async sessionmaker + RLS bindparams. `get_db()` dependency. |
| `migrations/env.py` | COMPLETO | N/A | Alembic async con asyncpg. |
| `migrations/versions/001_initial_schema.py` | COMPLETO | N/A | Schema completo: 5 tablas + RLS FORCE + policies + trigger. |

#### Capa: Core (`core/`)

| Archivo | Estado | Cobertura | Descripcion |
|---------|--------|-----------|-------------|
| `config.py` | COMPLETO | 100% | pydantic-settings. Valida al startup. SecretStr para keys. |
| `security.py` | COMPLETO | 100% | Secure headers middleware + IP whitelist. |

#### Capa: Entrypoint

| Archivo | Estado | Cobertura | Descripcion |
|---------|--------|-----------|-------------|
| `main.py` | COMPLETO | 100% | FastAPI app con lifespan, CORS, security middleware, router mount. |

---

### FRONTEND — `frontend/`

| Archivo | Estado | Descripcion |
|---------|--------|-------------|
| `app/layout.tsx` | COMPLETO | Layout global. |
| `app/page.tsx` | COMPLETO | Home redirect. |
| `app/dashboard/page.tsx` | COMPLETO | Lista de evaluaciones. |
| `app/evaluations/new/page.tsx` | COMPLETO | Formulario de creacion (react-hook-form + zod). |
| `app/evaluations/[id]/page.tsx` | COMPLETO | Detalle con Scorecard. Server Component fetch. |
| `app/error.tsx` | COMPLETO | Error boundary global (espanol). |
| `app/not-found.tsx` | COMPLETO | 404 (espanol). |
| `app/loading.tsx` | COMPLETO | Loading state global. |
| `components/scorecard.tsx` | COMPLETO | SVG gauge, badge veredicto, 4 agent cards (Progress + Collapsible), warn banner, loading/error states. |
| `components/evaluation-form.tsx` | COMPLETO | 11 campos de costos + producto + precio + volumen. |
| `components/cost-section.tsx` | COMPLETO | Seccion colapsable de costos en el form. |
| `components/ui/badge.tsx` | COMPLETO | shadcn/ui Badge con 6 variantes. |
| `components/ui/button.tsx` | COMPLETO | shadcn/ui Button. |
| `components/ui/card.tsx` | COMPLETO | shadcn/ui Card + CardHeader + CardContent + CardTitle. |
| `lib/api.ts` | COMPLETO | Cliente HTTP con URL split (internal/public). |
| `lib/types.ts` | COMPLETO | Tipos manuales (TODO: codegen con openapi-typescript). |
| `lib/verdicts.ts` | COMPLETO | VERDICT_LABELS/COLORS centralizados. |
| `lib/utils.ts` | COMPLETO | cn() utility. |

---

### INFRA

| Archivo | Estado | Descripcion |
|---------|--------|-------------|
| `docker-compose.yml` | COMPLETO | 4 servicios: nginx, frontend, backend, db. Alembic para migrations. |
| `docker/nginx/nginx.conf` | COMPLETO | HTTPS Let's Encrypt, IP whitelist, rate limit 20/min, proxy pass. |
| `docker/nginx/entrypoint.sh` | COMPLETO | Renderiza IP whitelist desde ALLOWED_IPS. |
| `frontend/Dockerfile` | COMPLETO | Multi-stage: builder + runner standalone. |
| `backend/Dockerfile` | COMPLETO | Python 3.12 con uvicorn. |
| `alembic.ini` | COMPLETO | Config Alembic apuntando a db/migrations. |

---

## Tests: 226 totales

| Modulo | Tests | Descripcion |
|--------|-------|-------------|
| `tests/agents/test_contracts.py` | 38 | Validacion de todos los Pydantic models |
| `tests/agents/test_llm_client.py` | ~20 | AnthropicLLMClient + FakeLLMClient |
| `tests/agents/test_base.py` | ~12 | build_agent, load_prompt, render_user, calc/score injection |
| `tests/agents/test_calculations_financial.py` | ~15 | Calculos financieros puros |
| `tests/agents/test_calculations_market.py` | 10 | Calculos mercado puros |
| `tests/agents/test_calculations_risk.py` | 9 | Calculos riesgo puros |
| `tests/agents/test_calculations_scoring.py` | ~10 | Pesos, degradacion, verdict_from_score |
| `tests/agents/test_orchestrator.py` | 9 | Async orchestrator LLM + fallback + degradation |
| `tests/agents/test_pipeline.py` | ~8 | Pipeline E2E con FakeLLMClient |
| `tests/agents/test_budgeted_llm.py` | 5 | BudgetedLLMClient caps |
| `tests/agents/test_market.py` | 5 | Agente mercado con FakeLLMClient |
| `tests/agents/test_risk.py` | 5 | Agente riesgo con FakeLLMClient |
| `tests/agents/test_strategy.py` | 6 | Agente estrategia con FakeLLMClient |
| `tests/golden/test_golden_set.py` | 5 | 5 escenarios regression E2E |
| `tests/api/test_evaluations.py` | ~20 | Endpoints HTTP |
| `tests/services/` | 5 | Idempotency + warn_flags |
| `tests/core/test_config.py` | ~10 | Settings validation |
| `tests/db/test_session.py` | ~5 | Session + RLS |
| `tests/test_main.py` | ~5 | App startup |

---

## Lo que falta (por sprint)

### Sprint 4 (~3 dias) — Comparativa lado a lado
- **Backend:** endpoint GET /api/v1/evaluations/compare?ids=uuid1,uuid2,uuid3
- **Frontend:** pagina `app/evaluations/compare/page.tsx` con tabla comparativa
- **UI:** consolidar primitivos restantes si hay gaps

### Sprint 5 (~1 semana) — Chat de seguimiento
- **Backend:** endpoint SSE para chat con contexto de evaluacion
- **Backend:** upload de archivos adjuntos (PDF, imagenes)
- **Frontend:** componente de chat con streaming
- **DB:** tabla chat_messages ya existe (preparada desde 001)

### Sprint 6 (~3 dias) — Hardening pre-produccion
- **Tavily:** search_web(query) con cache 24h en agente Mercado
- **Banxico:** get_usd_mxn() con cache 1h + fallback DB
- **Observabilidad:** structlog JSON + Prometheus metrics
- **Watchdog:** evaluaciones huerfanas (running > 5min -> error)
- **Prompt caching:** cache_control en system blocks
- **Tipos frontend:** codegen con openapi-typescript (reemplazar lib/types.ts manual)
- **Tests integracion:** evaluation_service con DB real (cubrir el 69% -> 85%+)

---

## Riesgos activos

1. **`lib/types.ts` manual** — puede desyncearse del backend. Codegen (Sprint 6) lo resuelve.
2. **`evaluation_service.py` 69% coverage** — paths de DB no testeados sin postgres. Sprint 6 agrega integracion.
3. **`exchange_rate.py` 0% coverage** — es un stub. Sprint 6 lo implementa.
4. **LLM real no testeado** — todo corre con FakeLLMClient. Primera prueba real sera con ANTHROPIC_API_KEY en staging.
5. **Frontend sin test framework** — no hay Jest/Vitest configurado. Verificacion es `npm run build` + visual manual.

---

## Metricas clave

| Metrica | Valor |
|---------|-------|
| Tests totales | 226 |
| Coverage agents/ | 97% |
| Coverage total | ~85% |
| Commits en branch | 25 |
| Archivos backend | 30 (.py) |
| Archivos frontend | 19 (.tsx/.ts) |
| Dependencias nuevas Sprint 2-3 | 0 |
| LLM calls por evaluacion | 5 (4 agentes + 1 orquestador) |
| Token cap por evaluacion | 20,000 input |
