# Contributing

Thanks for your interest! Issues and pull requests are welcome. The UI, prompts and analysis are in Spanish; code, issues and PRs can be in English or Spanish.

## Setup

```bash
cp .env.example .env            # set ANTHROPIC_API_KEY, DB_PASSWORD, SECRET_KEY (≥ 32 chars)
docker compose up --build       # full stack on http://localhost:3000

# backend
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt

# frontend
cd frontend && npm ci
```

## Before opening a PR

All of these must pass:

```bash
cd backend && pytest -q          # no network; the LLM is faked (FakeLLMClient)
cd frontend && npm test          # vitest
cd frontend && npm run check:types && npm run lint && npm run build
scripts/test-rls.sh              # only if you touched the DB, sessions or background tasks (needs Docker)
```

## Ground rules

- **Tests first.** New behaviour or bug fixes come with a test that fails without the change. Tests never hit the network or a real LLM.
- **Do not hand-write API types.** Change the Pydantic schema in `backend/api/v1/schemas.py`, then run `npm run gen:types` and commit `frontend/lib/types.generated.ts` ([ADR-0004](docs/adr/0004-tipos-frontend-desde-openapi.md)).
- **Money is MXN** in the database; the FX rate used is stored with each evaluation ([ADR-0005](docs/adr/0005-tc-persistido-con-evaluacion.md)).
- **Verdicts are literal values:** `viable`, `viable_con_ajustes`, `no_viable`. Do not translate or reformat them.
- **LLM access goes through `langchain-anthropic`** with structured output ([ADR-0007](docs/adr/0007-langchain-anthropic-obligatorio.md)).
- **Database access respects Row-Level Security.** Never interpolate values into SQL; use bound parameters ([ADR-0008](docs/adr/0008-rls-efectivo-con-force.md)).
- **Prompts** live in `backend/agents/prompts/*.md` and can be edited without touching Python.
- A change that alters a contract or a cross-cutting decision needs a new ADR in [`docs/adr/`](docs/adr/).

## Commits and PRs

- [Conventional commits](https://www.conventionalcommits.org/) with a scope: `feat(agents): ...`, `fix(api): ...`, `docs: ...`.
- Small, focused PRs. Describe what changed and how you verified it.
- Never commit secrets or `.env` files.

## Security issues

Please do not open public issues for vulnerabilities. See [SECURITY.md](SECURITY.md).
