#!/usr/bin/env bash
# Daily PostgreSQL backup for Member Admin.
#
#   ./scripts/backup.sh                 # run once
#   crontab -e  ->  30 3 * * * /path/to/member-admin/scripts/backup.sh >> /var/log/member-admin-backup.log 2>&1
#
# Keeps the last KEEP_DAYS days of compressed dumps in BACKUP_DIR.
# Copy BACKUP_DIR to another machine / cloud storage too: a backup on the same VPS
# does not survive losing the VPS.
set -euo pipefail

cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

BACKUP_DIR="${BACKUP_DIR:-$PWD/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

file="$BACKUP_DIR/member_admin_$(date +%Y%m%d_%H%M%S).sql.gz"
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner | gzip -9 > "$file.tmp"
mv "$file.tmp" "$file"
chmod 600 "$file"

# sanity check: the dump must not be empty
if [ "$(gzip -cd "$file" | head -c 1000 | wc -c)" -lt 100 ]; then
    echo "$(date) backup looks empty: $file" >&2
    exit 1
fi

find "$BACKUP_DIR" -name 'member_admin_*.sql.gz' -mtime +"$KEEP_DAYS" -delete
echo "$(date) backup ok: $file ($(du -h "$file" | cut -f1))"
