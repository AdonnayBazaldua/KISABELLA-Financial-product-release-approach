# CAPI kisabella — CLAUDE.md

> Documento de instrucciones para Claude Code. Define stack, convenciones, arquitectura, ADRs y reglas no negociables del proyecto.

---

## Qué es este proyecto

Herramienta interna de toma de decisiones financieras para evaluar la viabilidad de ideas de productos físicos (importación / distribución / reventa) en México. Pipeline LangGraph multi-agente sobre Claude API que entrega veredicto + scorecard + análisis extenso por agente.

**Usuarios:** 2-3 personas internas. Sin auth de usuarios — acceso por IP whitelist en Nginx.
**Idioma del sistema:** Español. UI, prompts, análisis, mensajes de error, documentación.
**Dominio de negocio:** ver `CONTEXT.md` (single source of truth del glosario y de los 11 costos).

---

## Estado del proyecto

- Sprint 1 fue **descartado** tras auditoría (2026-05-23) por 8 P0 + 22 P1 concentrados en 4 capas.
- En curso: **rebuild híbrido** — reescribir capas rotas, conservar lo que funciona.
- Auditoría completa: `.claude/audits/CODEBASE_AUDIT_2026-05-23.md` (gitignored).

### Borrado en el rebuild
- `backend/agents/*` — patrón frágil, sin paralelización
- `backend/api/evaluations.py` — pipeline en-request, sin BackgroundTask
- `backend/db/database.py` — RLS con SQL injection + bypass del owner
- `backend/main.py` — middleware mal configurado
- `backend/tests/*` — esqueléticos, no cubrían el path crítico

### Conservado y parcheado
- `backend/db/models.py` — schema OK
- `backend/db/migrations/` — extender con RLS efectivo
- `backend/core/config.py` — pequeños ajustes
- `frontend/` entero — 8-10 patches puntuales
- `docker-compose.yml`, `docker/nginx/`, `Dockerfile`s
- `CONTEXT.md` — dominio bien pensado

---

## Stack (locked)

| Capa | Tecnología | Notas |
|------|-----------|-------|
| Frontend | Next.js 14 App Router + TypeScript + Tailwind + shadcn/ui | `next.config.mjs` (NO `.ts` — Next 14 no lo soporta) |
| Backend | FastAPI + Python 3.12 + uvicorn | Async end-to-end. Sin gevent. |
| ORM | SQLAlchemy 2.x async + Alembic | Migraciones versionadas. NO migraciones ad-hoc en `.sql`. |
| Base de datos | PostgreSQL 16 con RLS efectivo (FORCE + rol no-owner) | Ver ADR-008 abajo. |
| LLM | Anthropic Claude vía **`langchain-anthropic`** | Modelo: `claude-sonnet-4-6`. SDK `anthropic` directo PROHIBIDO. ADR-007. |
| Validación LLM output | `ChatAnthropic.with_structured_output(PydanticModel)` | No parsing de fences. No `json.loads` ad-hoc. |
| Búsqueda web | Tavily API | Solo desde Agente Mercado. Cache 24h. Sprint 6. |
| Tipo de cambio | API Banxico (USD/MXN) | Header `Bmx-Token` requerido. Cache 1h. Fallback a último valor en DB. |
| Tareas async | `fastapi.BackgroundTasks` | Endpoint POST devuelve 202. Frontend hace polling. ADR-006. |
| Tipos compartidos | `openapi-typescript` codegen | Frontend NO tipa a mano lo que el backend ya tipa con Pydantic. ADR-004. |
| Despliegue | Docker Compose en VPS IONOS.mx ($8-12/mes, 2 vCPU + 4GB) | ADR-009. |
| Reverse proxy | Nginx con HTTPS Let's Encrypt + IP whitelist + rate limiting | ADR-010. |
| CI/CD | git push → webhook → `docker compose up -d --build` | Solo branch `main`. |

---

## Estructura del proyecto (target post-rebuild)

```
capi-kisabella/
├── frontend/
│   ├── app/
│   │   ├── dashboard/
│   │   ├── evaluations/
│   │   │   ├── new/
│   │   │   ├── [id]/
│   │   │   └── compare/                # Sprint 4
│   │   ├── error.tsx                   # Boundary global (español)
│   │   ├── not-found.tsx               # 404 (español)
│   │   ├── loading.tsx
│   │   └── layout.tsx
│   ├── components/
│   │   ├── ui/                         # primitivos: Button, Badge, Card, Tabs
│   │   ├── evaluation-form.tsx         # react-hook-form + zod
│   │   └── financial-result.tsx
│   └── lib/
│       ├── api.ts                      # split internal/public URL
│       ├── types.generated.ts          # from /openapi.json — NUNCA editar a mano
│       ├── verdicts.ts                 # VERDICT_LABELS/COLORS centralizados
│       └── utils.ts                    # cn()
├── backend/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── contracts.py                # AgentResult, EvaluationInputs, FinalVerdict, PipelineState (Pydantic)
│   │   ├── llm_client.py               # LLMClient + FakeLLMClient
│   │   ├── base.py                     # build_agent() factory + tipo AgentFn
│   │   ├── prompts/                    # Templates .md editables sin recompilar
│   │   │   ├── financial.md
│   │   │   ├── market.md
│   │   │   ├── risk.md
│   │   │   ├── strategy.md
│   │   │   └── orchestrator.md
│   │   ├── tools/
│   │   │   ├── tavily.py               # search_web(query) con cache 24h
│   │   │   └── banxico.py              # get_usd_mxn() con cache 1h
│   │   ├── calculations/
│   │   │   ├── financial.py            # margen, ROI, equilibrio, sensibilidad TC (puro)
│   │   │   └── scoring.py              # weighted_score()
│   │   ├── financial.py                # AgentFn = build_agent(...)
│   │   ├── market.py
│   │   ├── risk.py
│   │   ├── strategy.py
│   │   ├── orchestrator.py             # firma distinta (recibe 4 AgentResult)
│   │   └── pipeline.py                 # build_pipeline() + run_evaluation()
│   ├── services/
│   │   └── evaluation_service.py       # capa entre HTTP y pipeline (extracción de evaluations.py)
│   ├── api/
│   │   ├── evaluations.py              # POST 202 + GET polling + GET detail + GET list
│   │   ├── chat.py                     # Sprint 5
│   │   └── exchange_rate.py            # GET /tc — wrapper de tools.banxico
│   ├── db/
│   │   ├── session.py                  # async_sessionmaker + get_db() con RLS bindparam
│   │   ├── models.py
│   │   └── migrations/                 # Alembic versions/
│   ├── core/
│   │   ├── config.py                   # pydantic-settings, valida en startup
│   │   └── security.py                 # secure headers + IP whitelist middleware
│   ├── tests/
│   │   ├── conftest.py                 # fake_session, FakeLLMClient, FakeToolRegistry
│   │   ├── test_pipeline.py            # E2E con todo mockeado
│   │   ├── test_agents/*               # 1 archivo por agente
│   │   ├── test_calculations/*         # tests puros sin LLM
│   │   └── test_api/*                  # endpoints HTTP
│   └── main.py
├── docker/
│   └── nginx/
│       ├── nginx.conf                  # template
│       └── entrypoint.sh               # renderea whitelist desde ALLOWED_IPS
├── docs/
│   ├── adr/                            # ADRs vivos, ver lista abajo
│   └── status/                         # weekly notes YYYY-WW.md
├── docker-compose.yml
├── .env.example
├── CLAUDE.md                           # este archivo
└── CONTEXT.md                          # dominio
```

---

## Convenciones (no negociables)

### Dinero y unidades
- Todos los costos se almacenan en **MXN** en DB. Los inputs en USD se convierten al TC del momento.
- El **TC USD/MXN se persiste** junto con la evaluación (`exchange_rate_used` + `exchange_rate_at`). Análisis histórico se reproduce con ese TC, NO con el actual. ADR-005.
- TC se obtiene de Banxico. Fallback: último TC válido en DB + flag `tc_stale=true`. Nunca usar el TC del payload del usuario como valor primario.

### Agentes y veredictos
- Cada agente especialista devuelve `AgentResult` (Pydantic, validado por `with_structured_output`):
  ```python
  class AgentResult(BaseModel):
      score: int = Field(ge=0, le=100)
      veredicto_corto: str
      analisis_extenso: str = Field(min_length=300, max_length=500)  # palabras, aproximado
      hallazgos_clave: list[str] = Field(min_length=1)
      recomendaciones: list[str] = Field(min_length=1)
  ```
- Veredictos finales: literalmente `"viable"` | `"viable_con_ajustes"` | `"no_viable"`. NO traducir, NO mayúsculas, NO espacios.
- Análisis extenso: 300-500 palabras en español. Tono profesional, no técnico.
- Score compuesto final = promedio ponderado: **Financiero 0.35, Mercado 0.25, Riesgo 0.20, Estrategia 0.20**. Centralizado en `calculations/scoring.py`.
- Orquestador **no tiene score propio**. Sintetiza y emite veredicto + justificación.

### Degradación graceful
- ≥3 de 4 agentes OK → veredicto normal del orquestador.
- exactamente 2 OK → veredicto = `viable_con_ajustes`, `requires_human_review=true`, `confidence=low`.
- ≤1 OK → veredicto = `no_viable`, justificación = "Datos insuficientes: N de 4 agentes fallaron", `requires_human_review=true`.

### Pipeline async
- POST `/api/evaluations` devuelve **202 Accepted** con `{evaluation_id, status:"pending"}`. NO bloquea esperando agentes.
- BackgroundTask ejecuta el pipeline. Estados: `pending → queued → running → complete | error`.
- Frontend hace polling cada 2s sobre `GET /api/evaluations/{id}` hasta `complete` o `error`.
- Sub-estado por agente expuesto en el polling: `pending | running | ok | failed | degraded`.
- Watchdog cada 60s: evaluaciones con `status=running` y `started_at < now - 5min` → marcar `status=error, error_code=ORPHANED`.
- Re-evaluar = nueva evaluación (UUID nuevo). Anteriores son inmutables (audit trail).
- Idempotency: hash(user_id + payload) en ventana 30s → 409 si duplicado simultáneo.

### Timeouts y retries
- LLM call individual: timeout 60s, retry 3x exponencial (1s, 2s, 4s) en RateLimit/Timeout/5xx, NO en ValidationError.
- Pipeline global: timeout 90s vía `asyncio.wait_for`.
- Tavily: timeout 15s, si falla → procede sin búsqueda web, flag `warn_no_web=true`.
- Banxico: timeout 5s, retry 1x, fallback a DB.
- Hard cap por evaluación: **50k tokens input + 6 LLM calls totales** (evita runaway).

### LLM
- **Solo `langchain-anthropic`**. Importar `from anthropic import Anthropic` directamente está **prohibido**. ADR-007.
- Output structured **siempre** via `ChatAnthropic.with_structured_output(PydanticSchema, method="function_calling")`.
- Temperature default 0.2 para outputs estructurados (no 1.0).
- Prompt caching ON (`cache_control={"type":"ephemeral"}`) en bloques system. Ahorra ~90% en lectura.
- Prompts viven en `agents/prompts/*.md` — editables sin recompilar Python.

### Tools (Tavily / Banxico)
- Llamadas **directas** desde el agente antes del LLM call. NO `ChatAnthropic.bind_tools()`. Razones: determinístico, cache controlado, prompts más cortos.
- Cache en memoria (no Redis aún): Tavily 24h por hash(query), Banxico 1h.

### Seguridad — reglas no negociables
- **RLS efectivo** (no solo declarado): rol `capi_app` NO-owner + `ALTER TABLE ... FORCE ROW LEVEL SECURITY` + policies con `USING` y `WITH CHECK`. ADR-008.
- `SET LOCAL app.user_id` se setea con **`text("SET LOCAL app.user_id = :uid").bindparams(uid=...)`**. F-string **prohibido**.
- Security headers en Nginx Y en FastAPI (`secure.Secure()` con HSTS, CSP, XFO explícitos).
- IP whitelist en Nginx — `ALLOWED_IPS` del `.env` se renderea por entrypoint script.
- HTTPS obligatorio. HTTP redirige a HTTPS. Let's Encrypt con auto-renewal 30d antes de expiry.
- Rate limiting: 20 req/min por IP en Nginx.
- Secrets exclusivamente en `.env`. NUNCA en código, NUNCA en git. `.env.example` documenta sin valores.
- Postgres NO expone puerto fuera de la red Docker interna.

### Tests
- **Verify flows always** (memoria persistente): `pytest`, `npm run build`, `docker compose config` verde antes de declarar trabajo completo.
- Cobertura mínima `backend/agents/`: 70%. PR no mergea bajo este umbral.
- `FakeLLMClient` y `FakeToolRegistry` en `conftest.py`. Cero red en CI.
- Path crítico (`POST /evaluations`) tiene tests E2E. Sprint 1 NO los tenía.

### Frontend
- Server Components para data fetching. Client Components solo cuando hace falta interactividad.
- `cache: 'no-store'` o `export const dynamic = 'force-dynamic'` en listados que cambian.
- URL del backend: separar `API_URL_INTERNAL` (Server Components, `http://backend:8000`) de `NEXT_PUBLIC_API_URL` (browser, dominio público).
- Forms con `react-hook-form` + `zod`. NO `useState` por campo en forms con >5 inputs.
- Componentes UI primitivos en `components/ui/` (Button, Badge, Card, Tabs). NO copiar Tailwind clases.
- Validar responses runtime con zod cuando vienen de network. TypeScript solo no alcanza.
- Tipos generados con `openapi-typescript` desde `/openapi.json`. Script: `npm run gen:types`. ADR-004.

### Logging
- `structlog` con formato JSON. Campos obligatorios: `evaluation_id`, `agent_name`, `correlation_id`, `duration_ms`.
- NUNCA loguear API keys, payloads de PII completos, ni tokens de Banxico.
- Tokens consumidos por LLM call → loguear como `tokens_input`, `tokens_output`, `cost_usd`.

---

## Comandos clave

```bash
# Desarrollo local — backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
uvicorn main:app --reload --port 8000

# Desarrollo local — frontend
cd frontend
npm install
npm run gen:types          # codegen desde backend OpenAPI
npm run dev                # :3000

# Tests
cd backend && pytest -q
cd frontend && npm run build && npm run lint

# Docker (staging/prod)
docker compose up -d
docker compose logs -f backend
docker compose build backend
docker compose exec db psql -U capi_app capi_kisabella

# Alembic
cd backend
alembic revision --autogenerate -m "descripción"
alembic upgrade head
alembic downgrade -1

# Deploy
git push origin main       # webhook → docker compose up -d --build
```

---

## Variables de entorno

`.env` está gitignored. `.env.example` documenta sin valores.

```
# Anthropic
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6

# External APIs
TAVILY_API_KEY=
BANXICO_TOKEN=

# Database
DB_PASSWORD=
DATABASE_URL=postgresql+asyncpg://capi_app:${DB_PASSWORD}@db:5432/capi_kisabella

# Security
SECRET_KEY=              # ≥32 chars, validado en startup
ALLOWED_IPS=             # CSV: "192.168.x.x,x.x.x.x"

# Frontend (build-time)
NEXT_PUBLIC_API_URL=     # dominio público (https://capi.tudominio.mx/api)
API_URL_INTERNAL=        # red Docker interna (http://backend:8000)

# Observabilidad
LOG_LEVEL=INFO
SENTRY_DSN=              # opcional
```

`backend/core/config.py` con `pydantic-settings` valida que todas estén presentes al startup. Falta = crash inmediato.

---

## ADRs (decisiones locked)

Las ADRs viven en `docs/adr/`. Aquí están las locked decisions hasta hoy:

| ID | Decisión | Por qué |
|----|----------|---------|
| ADR-001 | Agentes especialistas son funciones puras `AgentFn = async (inputs, llm, tools) → AgentResult`. NO clases, NO herencia. | Composability con LangGraph; testeable con `FakeLLMClient`. |
| ADR-002 | `PipelineState.agent_results: dict[str, AgentResult \| AgentError]`. Nunca campos por agente nombrados. | Sumar agente = 1 línea en registry. |
| ADR-003 | Outputs LLM validados con Pydantic en `LLMClient.request_structured()`. No `json.loads` ad-hoc en agentes. | Una sola superficie de validación. |
| ADR-004 | Tipos frontend generados desde `/openapi.json` con `openapi-typescript`. NUNCA a mano. | Drift backend/frontend imposible. |
| ADR-005 | TC se persiste con `exchange_rate_used` y `exchange_rate_at`. Histórico se reproduce con ese TC. | Análisis comparables a través del tiempo. |
| ADR-006 | Pipeline ejecuta en `BackgroundTask`. POST `/api/evaluations` devuelve 202. Frontend hace polling. | Nginx timeout 60s no aplica; UX no se cuelga. |
| ADR-007 | Stack LLM = `langchain-anthropic` + `with_structured_output`. SDK `anthropic` directo prohibido. | Output validado, retry integrado, tool calling nativo. |
| ADR-008 | RLS efectivo: rol `capi_app` no-owner + `FORCE RLS` + policies `USING` + `WITH CHECK`. `bindparams` siempre. | Defensa-en-profundidad real. |
| ADR-009 | Deploy en IONOS VPS $8-12/mes (2 vCPU, 4GB). Todo en una caja. | TCO ~$100/año, IP whitelist nativa, sin vendor lock-in. |
| ADR-010 | Nginx renderea IP whitelist desde `ALLOWED_IPS` con entrypoint script. HTTPS Let's Encrypt + HSTS + rate limit 20/min. | Configuración versionada, no hardcoded. |
| ADR-011 | Tools (Tavily, Banxico) se llaman desde el agente directo, no via `bind_tools`. Cache en memoria. | Determinístico, control de cache, prompts más cortos. |
| ADR-012 | Tests: cobertura ≥70% en `backend/agents/`. `FakeLLMClient` obligatorio. Cero red en CI. | Path crítico cubierto antes de merge. |

Una ADR nueva por **cualquier** decisión que afecte 2+ sprints o cambie un contrato. Sin ADR no merge.

---

## Agent skills (Claude Code)

Skills de Matt Pocock instaladas en `.claude/skills/` (gitignored):
- `improve-codebase-architecture` — deepening opportunities + deletion test
- `diagnose` — disciplina para bugs duros (loop, repro, hipótesis, fix, post-mortem)
- `caveman` — modo ultra-compreso (solo si el usuario lo invoca)
- `setup-matt-pocock-skills` — configuración del repo

Agency-agents en `.claude/agents/` (gitignored, 175 disponibles vía `subagent_type`).

### Issue tracker
GitHub Issues en `AdonnayBazaldua/CAPI-KISABELLA` vía `gh` CLI. Labels canónicas: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`.

### Política de artefactos de Claude
TODOS los archivos generados por Claude (skills, agentes, planes, audits, ADRs en draft) se mantienen **gitignored hasta el commit final** del proyecto cuando el usuario decida liberarlos. Convención durable.

---

## Arquitectura de agentes

Ver detalle en `docs/adr/ADR-001.md` y `backend/agents/*`. Resumen:

```
POST /api/evaluations (HTTP 202)
        │
        ▼
  EvaluationService.create() → INSERT row + BackgroundTask
        │
        ▼ (async)
  Pipeline LangGraph
        │
        ├─ fan-out paralelo (asyncio.gather)
        │   ├─ financiero  (calc puro + LLM)
        │   ├─ mercado     (Tavily + LLM)
        │   ├─ riesgo      (LLM)
        │   └─ estrategia  (LLM)
        │
        ├─ fan-in: espera SIEMPRE los 4 (no aborta si falla 1)
        │
        ▼
  orquestador (sintetiza 4 AgentResult → FinalVerdict)
        │
        ▼
  UPDATE evaluations SET status='complete', persist full report
        │
        ▼
  Frontend polling detecta status=complete → render scorecard
```

---

## Roadmap (actualizado post-rebuild)

| Fase | Duración | Entrega | Bloquea |
|------|----------|---------|---------|
| **Fase 0** | ~5 días | Saneamiento: rebuild capas rotas + cierre P0/P1 críticos. Agente Financiero nuevo bajo arquitectura final. | Sprint 2 |
| **Sprint 2** | ~1 semana | Agentes Mercado + Riesgo + Estrategia (registry-driven). Tests con `FakeLLMClient`. | Sprint 3 |
| **Sprint 3** | ~5 días | Orquestador real + veredicto + scorecard visual frontend. Degradación graceful. | Sprint 4 |
| **Sprint 4** | ~3 días | Comparativa lado a lado de 2-3 evaluaciones. UI primitivos consolidados. | Sprint 5 |
| **Sprint 5** | ~1 semana | Chat de seguimiento (SSE) + uploads + processing. | Sprint 6 |
| **Sprint 6** | ~3 días | Tavily producción + Banxico cache + observabilidad (structlog + Prometheus) + hardening pre-launch. | Producción |

**Anti-scope-creep** (no entra mid-sprint):
- Auth de usuarios (IP whitelist basta para 2-3 users).
- Búsqueda Tavily real en Sprint 2 (mockeada hasta Sprint 6).
- Streaming SSE antes de Sprint 5.
- OCR / RAG / vector search.
- Dashboards Grafana antes de Sprint 6.

---

## Skill prefs y workflow

- **brainstorming** antes de crear cualquier feature nueva (skill superpowers).
- **test-driven-development** para todo código en `backend/agents/` y `backend/services/`.
- **verification-before-completion** antes de cada commit: `pytest` + `npm run build` + `docker compose config`.
- **using-git-worktrees** si el feature necesita isolation del workspace principal.
- ADR escrita ANTES de implementar si la decisión afecta 2+ sprints.

---

## Trazabilidad

- GitHub Issues como SSOT. 1 issue por feature.
- Conventional commits con scope: `feat(agents):`, `fix(api):`, `chore(db):`, `refactor(frontend):`.
- Weekly status note en `docs/status/YYYY-WW.md`: entregado, blockers, próximo foco, riesgos activos.
- Branch protection en `main`: PR obligatorio + CI verde + coverage gate.
- ADRs en `docs/adr/` — vivas, revisar al cierre de cada sprint.

---

_Última actualización: 2026-05-23 (post-auditoría, decisión de rebuild híbrido)._
