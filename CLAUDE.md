# CAPI kisabella — CLAUDE.md

## Qué es este proyecto
Herramienta interna de toma de decisiones financieras y empresariales. Evalúa ideas de productos físicos (importación/distribución/reventa) mediante un pipeline multi-agente (LangGraph + Claude API) que analiza viabilidad de inversión y retorno.

**Usuarios:** 2-3 personas internas. Sin roles complejos. Acceso restringido por IP.
**Idioma del sistema:** Español (UI, análisis de agentes, reportes).

---

## Stack

| Capa | Tecnología |
|------|-----------|
| Frontend | Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui |
| Backend | FastAPI (Python 3.12), LangGraph, LangChain |
| Base de datos | PostgreSQL 16 con Row Level Security |
| LLM | Claude API — `claude-sonnet-4-6` |
| Búsqueda web (agentes) | Tavily API |
| Tipo de cambio | API Banxico (tiempo real, USD/MXN) |
| Despliegue | Docker Compose en VPS IONOS.mx |
| Reverse proxy | Nginx con HTTPS (Let's Encrypt) |
| CI/CD | git push → webhook → `docker compose up -d` |

---

## Estructura del proyecto

```
capi-kisabella/
├── frontend/
│   ├── app/                  # Next.js App Router
│   │   ├── dashboard/        # Lista de evaluaciones
│   │   ├── evaluations/
│   │   │   ├── new/          # Formulario nueva evaluación
│   │   │   ├── [id]/         # Detalle + chat
│   │   │   └── compare/      # Comparativa lado a lado
│   │   └── layout.tsx
│   ├── components/
│   └── lib/
├── backend/
│   ├── agents/
│   │   ├── financial.py      # Agente Financiero
│   │   ├── market.py         # Agente de Mercado
│   │   ├── risk.py           # Agente de Riesgo
│   │   ├── strategy.py       # Agente de Estrategia Comercial
│   │   ├── orchestrator.py   # Agente Orquestador
│   │   └── pipeline.py       # Grafo LangGraph
│   ├── api/
│   │   ├── evaluations.py
│   │   ├── chat.py
│   │   └── exchange_rate.py
│   ├── db/
│   │   ├── models.py
│   │   └── migrations/
│   ├── core/
│   │   ├── config.py         # Settings desde .env
│   │   └── security.py
│   └── main.py
├── docker/
│   ├── nginx/
│   │   └── nginx.conf
│   └── docker-compose.yml
└── docs/
    ├── superpowers/specs/
    └── adr/
```

---

## Comandos clave

```bash
# Desarrollo local
cd frontend && npm run dev           # frontend en :3000
cd backend && uvicorn main:app --reload  # backend en :8000

# Docker (producción / staging)
docker compose up -d                 # levantar todo
docker compose logs -f backend       # ver logs de agentes
docker compose build backend         # rebuild tras cambios Python
docker compose exec db psql -U capi  # consola PostgreSQL

# Deploy en VPS
git push origin main                 # dispara webhook automático
```

---

## Variables de entorno

Nunca commitear `.env`. El archivo `.env.example` documenta las variables requeridas:

```
ANTHROPIC_API_KEY=
TAVILY_API_KEY=
BANXICO_TOKEN=
DATABASE_URL=postgresql://capi:password@db:5432/capi_kisabella
SECRET_KEY=
ALLOWED_IPS=192.168.x.x,x.x.x.x
```

---

## Convenciones

- Todos los costos se almacenan en **MXN**. Los costos en USD se convierten al TC vigente en el momento de la evaluación y ese TC se persiste junto a los datos.
- Los análisis de agentes tienen entre **300 y 500 palabras** cada uno, siempre en español.
- Los veredictos usan exactamente estos valores: `viable` | `viable_con_ajustes` | `no_viable`.
- Los scores son enteros de **0 a 100**. El score final es promedio ponderado de los 4 agentes especialistas.
- El orquestador NO tiene score propio — sintetiza y decide.
- Nunca exponer el puerto de PostgreSQL fuera de la red Docker interna.

---

## Agent skills

Las skills de ingeniería de Matt Pocock están configuradas para este repo. Cada una sabe dónde buscar contexto:

### Issue tracker

Los issues viven como **GitHub Issues** en `AdonnayBazaldua/CAPI-KISABELLA` (se usa el CLI `gh`). Ver `docs/agents/issue-tracker.md`.

### Triage labels

Vocabulario canónico de 5 roles sin renombrar: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. Ver `docs/agents/triage-labels.md`.

### Domain docs

Layout **single-context**: un único `CONTEXT.md` en root + `docs/adr/`. Las skills leen el glosario del dominio (Evaluación, Veredicto, Score, los 11 costos, los 5 agentes). Ver `docs/agents/domain.md`.

---

## Arquitectura de agentes

Pipeline LangGraph de 5 nodos. Agentes 1-4 corren en **paralelo** (asyncio). El orquestador espera a los 4 antes de consolidar.

```
nodo_input → [financiero ‖ mercado ‖ riesgo ‖ estrategia] → orquestador → END
```

Cada agente devuelve:
```json
{
  "score": 0-100,
  "veredicto_corto": "string",
  "analisis_extenso": "300-500 palabras",
  "hallazgos_clave": ["..."],
  "recomendaciones": ["..."]
}
```

---

## Seguridad — reglas no negociables

- RLS habilitado en todas las tablas con datos de usuario.
- Security headers en Nginx Y en FastAPI (`secure.py`).
- IP whitelist en Nginx — solo IPs del equipo tienen acceso.
- Secrets exclusivamente en `.env`, nunca en código ni en git.
- HTTPS obligatorio. HTTP redirige a HTTPS.
- Rate limiting: 20 req/min por IP en Nginx.

---

## Roadmap de sprints (MVP iterativo)

| Sprint | Entrega |
|--------|---------|
| 1 | Formulario + Agente Financiero + UI básica |
| 2 | Agentes Mercado + Riesgo + Estrategia |
| 3 | Agente Orquestador + Veredicto + Scorecard visual |
| 4 | Historial + Comparativa de evaluaciones |
| 5 | Chat de seguimiento + carga de archivos adjuntos |
| 6 | Búsqueda web (Tavily) + TC en tiempo real (Banxico) |
