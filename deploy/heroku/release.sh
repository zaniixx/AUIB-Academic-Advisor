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

alembic upgrade head

if [ "${ADVISOR_AUTO_IMPORT:-true}" = "true" ]; then
  if [ "${ADVISOR_AUTO_IMPORT_ACCEPT_WARNINGS:-false}" = "true" ]; then
    python -m app.cli import-all --only-new --accept-warnings --actor heroku-release
  else
    python -m app.cli import-all --only-new --actor heroku-release
  fi
fi
