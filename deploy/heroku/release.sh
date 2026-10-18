#!/usr/bin/env bash
# Heroku release phase: runs once before each new release goes live. If it fails, the release is
# stopped and the previous one keeps running.
#
# 1. Migrate the database (Heroku Postgres) to this release's schema.
# 2. Import the course catalog and every program package not in the database yet, as the
#    Docker Compose set-up does on start. Optional: a failed import does not stop the release. Changed data for programs already imported is imported
#    by hand (docs/operations.md, "Heroku").
set -euo pipefail
cd /app/api

# Stop here, listing every missing config var (such as ADVISOR_SECRET_KEY or the SMTP settings).
python -m app.cli check-settings

alembic upgrade head

# Course data is optional: admins can add courses and programs in the admin page, by hand or from a
# spreadsheet. This import adds what the image holds (sealed, ADR 0008, opened with ADVISOR_DATA_KEY)
# and never stops the start: without the key, or if the import fails, the database keeps what it has.
if [ "${ADVISOR_AUTO_IMPORT:-true}" = "true" ]; then
  if [ -z "${ADVISOR_DATA_KEY:-}" ]; then
    echo "ADVISOR_DATA_KEY is not set: no course data was imported. Admins can add it in the admin page." >&2
  else
    accept=""
    if [ "${ADVISOR_AUTO_IMPORT_ACCEPT_WARNINGS:-false}" = "true" ]; then accept="--accept-warnings"; fi
    # shellcheck disable=SC2086  # $accept is one flag or nothing
    python -m app.cli import-all --only-new $accept --actor heroku-release \
      || echo "The course data import did not finish (see above); starting with the data the database has." >&2
  fi
fi
