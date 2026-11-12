#!/usr/bin/env bash
# Genera frontend/lib/types.generated.ts desde el OpenAPI del backend (sin servidor ni red).
# Uso: scripts/gen-types.sh          -> regenera
#      scripts/gen-types.sh --check  -> falla si el archivo commiteado esta desactualizado
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
py="${PYTHON:-$root/backend/.venv/bin/python}"
[ -x "$py" ] || py=python3

(cd "$root/backend" && \
  ANTHROPIC_API_KEY=x DB_PASSWORD=x SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx \
  DATABASE_URL=postgresql+asyncpg://x:x@localhost/x \
  "$py" -c "import json; from main import create_app; print(json.dumps(create_app().openapi()))" \
  > "$tmp/openapi.json")

out="$root/frontend/lib/types.generated.ts"
target="$out"; [ "${1:-}" = "--check" ] && target="$tmp/types.generated.ts"
(cd "$root/frontend" && npx --no-install openapi-typescript "$tmp/openapi.json" -o "$target" >/dev/null)

if [ "${1:-}" = "--check" ]; then
  diff -q "$out" "$target" >/dev/null || { echo "types.generated.ts desactualizado: corre scripts/gen-types.sh" >&2; exit 1; }
  echo "types OK"
fi
