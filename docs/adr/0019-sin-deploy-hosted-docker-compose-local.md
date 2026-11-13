# 0019 — Sin deploy hosted: Docker Compose local con API key propia

**Estado:** aceptado
**Fecha:** 2026-11-09
**Reemplaza a:** ADR-0009

## Contexto

El proyecto pasa a ser open source. Un deploy público compartido implicaría que
cualquiera que lo use consuma la API key de Anthropic del mantenedor, y la app
no tiene autenticación de usuarios (el acceso se limitaba por IP, ADR-0010).
El backend Python tampoco encaja gratis en plataformas serverless: usa
BackgroundTasks, colas SSE en memoria y un pool de Postgres persistente.

## Decisión

No hay deploy hosted oficial. El repo se entrega listo para correr en la
máquina de quien lo clona con `docker compose up --build`, usando **su propia**
`ANTHROPIC_API_KEY`:

- Las migraciones corren al arrancar el backend (`alembic upgrade head`) como
  rol dueño; la app se conecta como `kisabella_app` sin privilegios (ADR-0008).
- `ANTHROPIC_API_KEY`, `DB_PASSWORD` y `APP_DB_PASSWORD` son obligatorias: sin ellas
  `docker compose` falla en vez de arrancar a medias.
- Los puertos se publican solo en `127.0.0.1`.
- `ALLOWED_IPS` vacío permite todas las IPs (necesario tras el gateway de
  Docker); quien lo exponga a internet debe poner un reverse proxy y definirlo
  (el repo no incluye configuración de proxy; ver nota en ADR-0010).

## Consecuencias

- Positivo: cero costo de hosting y cero riesgo sobre la key del mantenedor.
- Positivo: el repo se verifica de punta a punta con `scripts/smoke.sh`.
- Negativo: sin demo en vivo; el README debe compensarlo con capturas.
- Negativo: un solo worker de backend (colas SSE y cachés en memoria).

## Alternativas consideradas

- VPS con acceso público: expone la key del mantenedor y exige auth de usuarios.
- Vercel (frontend) + backend en Railway/Render: coste recurrente y fragmenta el
  despliegue.
- Paquete en GitHub Packages: aplazado; la imagen Docker es construible hoy con
  `docker compose build` y no aporta nada mientras no haya registro público.
