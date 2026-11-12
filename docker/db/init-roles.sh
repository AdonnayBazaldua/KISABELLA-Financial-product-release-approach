#!/bin/sh
# Corre una sola vez al crear el volumen de Postgres.
# POSTGRES_USER (dueño, hace DDL) != kisabella_app (la app; NO dueño → RLS aplica, ADR-008).
set -e
psql -v ON_ERROR_STOP=1 -v pw="$APP_DB_PASSWORD" -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
CREATE ROLE kisabella_app LOGIN PASSWORD :'pw' NOSUPERUSER NOBYPASSRLS;
GRANT CONNECT ON DATABASE kisabella TO kisabella_app;
GRANT USAGE ON SCHEMA public TO kisabella_app;
ALTER DEFAULT PRIVILEGES GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO kisabella_app;
SQL
