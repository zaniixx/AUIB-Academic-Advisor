#!/bin/sh
# Restore a backup made by backup-db.sh into the running database. This replaces
# the current data. Run from the repository root:  sh scripts/restore-db.sh backups/<file>.dump
set -eu

if [ $# -ne 1 ] || [ ! -f "$1" ]; then
  echo "Usage: sh scripts/restore-db.sh backups/advisor-<date>.dump" >&2
  exit 1
fi
docker compose exec -T db pg_restore -U advisor -d advisor --clean --if-exists --no-owner < "$1"
docker compose restart api
echo "Restored $1 and restarted the API."
