#!/bin/sh
# Smoke: docker compose desde cero → /health, DB+migraciones+RLS vía API, frontend. Uso: scripts/smoke.sh
# Usa un env temporal (ENV_FILE); no toca tu .env. Para el compose normal que tengas arriba antes de correrlo.
set -e
cd "$(dirname "$0")/.."
export ENV_FILE="$(mktemp)" COMPOSE_PROJECT_NAME=kisabella-smoke
trap 'docker compose --env-file "$ENV_FILE" down -v >/dev/null 2>&1; rm -f "$ENV_FILE"' EXIT
printf 'ANTHROPIC_API_KEY=sk-ant-smoke\nDB_PASSWORD=smoke\n' > "$ENV_FILE"
C="docker compose --env-file $ENV_FILE"
$C config -q
$C up -d --build --wait --wait-timeout 300
curl -fsS localhost:8000/health
test "$(curl -fsS localhost:8000/api/v1/evaluations)" = "[]"
curl -fsS -o /dev/null localhost:3000/dashboard
echo "SMOKE OK"
