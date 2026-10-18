#!/bin/sh
# Start-up for the API container: migrate the database, import the course catalog and
# every program not imported yet (all of them on first start; optional), then serve. Runs as the
# unprivileged "app" user. Changed data for programs already imported is imported by hand:
#   docker compose exec api python -m app.cli import-all
set -eu

# Missing settings (such as ADVISOR_SECRET_KEY or the mail server) are reported once, in plain
# words, rather than retried below as if the database were not ready.
python -m app.cli check-settings

attempt=1
until alembic upgrade head; do
  if [ "$attempt" -ge 10 ]; then
    echo "The database is not reachable; giving up." >&2
    exit 1
  fi
  echo "Waiting for the database (attempt $attempt)..." >&2
  attempt=$((attempt + 1))
  sleep 3
done

# Course data is optional: admins can add courses and programs in the admin page, by hand or from a
# spreadsheet. This import adds what the image holds (sealed, ADR 0008, opened with ADVISOR_DATA_KEY)
# and never stops the start: without the key, or if the import fails, the database keeps what it has.
if [ "${ADVISOR_AUTO_IMPORT:-false}" = "true" ]; then
  if [ -z "${ADVISOR_DATA_KEY:-}" ]; then
    echo "ADVISOR_DATA_KEY is not set: no course data was imported. Admins can add it in the admin page." >&2
  else
    accept=""
    if [ "${ADVISOR_AUTO_IMPORT_ACCEPT_WARNINGS:-false}" = "true" ]; then accept="--accept-warnings"; fi
    # shellcheck disable=SC2086  # $accept is one flag or nothing
    python -m app.cli import-all --only-new $accept --actor auto-import \
      || echo "The course data import did not finish (see above); starting with the data the database has." >&2
  fi
fi

# The API is only reachable through the reverse proxy on the internal Docker network,
# so forwarded client addresses from it are trusted (used for rate limiting).
exec uvicorn app.main:create_app --factory \
  --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips="*" \
  --workers "${ADVISOR_WORKERS:-2}" \
  --no-access-log
