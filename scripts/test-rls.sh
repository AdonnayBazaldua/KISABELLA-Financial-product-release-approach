#!/bin/sh
# Test de RLS contra Postgres real y desechable. Uso: scripts/test-rls.sh
set -e
cd "$(dirname "$0")/.."
NAME=kisabella-rls-test; PORT=55432
docker rm -f $NAME >/dev/null 2>&1 || true
trap 'docker rm -f $NAME >/dev/null 2>&1' EXIT
docker run -d --name $NAME -p $PORT:5432 \
  -e POSTGRES_USER=kisabella -e POSTGRES_PASSWORD=pw -e POSTGRES_DB=kisabella -e APP_DB_PASSWORD=pw \
  -v "$PWD/docker/db/init-roles.sh:/docker-entrypoint-initdb.d/init-roles.sh:ro" postgres:16-alpine >/dev/null
until docker exec $NAME pg_isready -U kisabella -d kisabella -h 127.0.0.1 >/dev/null 2>&1; do sleep 1; done
sleep 2 # el init-script reinicia el server tras crear la DB
cd backend
TEST_PG_OWNER_URL=postgresql://kisabella:pw@localhost:$PORT/kisabella \
TEST_PG_APP_URL=postgresql://kisabella_app:pw@localhost:$PORT/kisabella \
  ${PYTHON:-.venv/bin/python} -m pytest -q tests/integration/test_rls_real_pg.py
