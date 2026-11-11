#!/usr/bin/env bash
# Restore a backup made by backup.sh.  THIS REPLACES ALL CURRENT DATA.
#
#   ./scripts/restore.sh backups/member_admin_20261111_033000.sql.gz
set -euo pipefail

[ $# -eq 1 ] || { echo "usage: $0 <backup.sql.gz>"; exit 1; }
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

read -r -p "Replace ALL data in '$POSTGRES_DB' with $1 ? Type YES: " ok
[ "$ok" = "YES" ] || { echo "cancelled"; exit 1; }

docker compose stop api
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\" WITH (FORCE)" \
    -c "CREATE DATABASE \"$POSTGRES_DB\" OWNER \"$POSTGRES_USER\""
gzip -cd "$1" | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -q > /dev/null
docker compose start api
echo "restored $1"
