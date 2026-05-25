#!/bin/sh
set -e

WHITELIST_FILE="/etc/nginx/snippets/ip_whitelist.conf"
mkdir -p /etc/nginx/snippets

# Genera directivas allow/deny desde ALLOWED_IPS (CSV).
# Si ALLOWED_IPS está vacío, permite todo (modo desarrollo).
if [ -z "$ALLOWED_IPS" ]; then
  echo "# ALLOWED_IPS no definido — acceso abierto (solo desarrollo)" > "$WHITELIST_FILE"
else
  echo "# Generado por entrypoint.sh desde ALLOWED_IPS" > "$WHITELIST_FILE"
  IFS=','
  for ip in $ALLOWED_IPS; do
    ip=$(echo "$ip" | xargs)
    if [ -n "$ip" ]; then
      echo "allow $ip;" >> "$WHITELIST_FILE"
    fi
  done
  echo "deny all;" >> "$WHITELIST_FILE"
fi

echo "[entrypoint] IP whitelist generada:"
cat "$WHITELIST_FILE"

exec nginx -g "daemon off;"
