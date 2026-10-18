#!/usr/bin/env bash
# Heroku release phase: runs once before each new release goes live. If it fails, the release is
# stopped and the previous one keeps running.
#
# 1. Migrate the database (Heroku Postgres) to this release's schema.
# 2. Import the course catalog and every program package not in the database yet, as the
#    Docker Compose set-up does on start. Changed data for programs already imported is imported
#    by hand (docs/operations.md, "Heroku").
set -euo pipefail
cd /app/api

# Stop here, listing every missing config var (such as ADVISOR_SECRET_KEY or the SMTP settings).
python -m app.cli check-settings

alembic upgrade head

# The image holds the course data sealed (ADR 0008): the import opens it with the ADVISOR_DATA_KEY
# config var into a temporary folder. Without the key the database keeps what it already has.
if [ "${ADVISOR_AUTO_IMPORT:-true}" = "true" ] && [ -z "${ADVISOR_DATA_KEY:-}" ]; then
  echo "ADVISOR_DATA_KEY is not set, so the course data was not imported (docs/operations.md, Heroku)." >&2
elif [ "${ADVISOR_AUTO_IMPORT:-true}" = "true" ]; then
  if [ "${ADVISOR_AUTO_IMPORT_ACCEPT_WARNINGS:-false}" = "true" ]; then
    python -m app.cli import-all --only-new --accept-warnings --actor heroku-release
  else
    python -m app.cli import-all --only-new --actor heroku-release
  fi
fi
