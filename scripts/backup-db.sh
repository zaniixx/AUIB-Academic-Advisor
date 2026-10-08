#!/bin/sh
# Back up the database to backups/advisor-<date>.dump (PostgreSQL custom format).
# Run from the repository root on the server:  sh scripts/backup-db.sh
# Optional: encrypt the file before it leaves the server, e.g.
#   gpg --symmetric --cipher-algo AES256 backups/advisor-<date>.dump
set -eu

mkdir -p backups
file="backups/advisor-$(date +%Y%m%d-%H%M%S).dump"
docker compose exec -T db pg_dump -U advisor -d advisor --format=custom > "$file"
echo "Wrote $file ($(wc -c < "$file") bytes)"
