#!/bin/sh
# Start-up for the API container: migrate the database, import the course catalog and
# every program not imported yet (all of them on first start), then serve. Runs as the
# unprivileged "app" user. Changed data for programs already imported is imported by hand:
#   docker compose exec api python -m app.cli import-all
set -eu

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

if [ "${ADVISOR_AUTO_IMPORT:-false}" = "true" ]; then
  if [ "${ADVISOR_AUTO_IMPORT_ACCEPT_WARNINGS:-false}" = "true" ]; then
    python -m app.cli import-all --only-new --accept-warnings --actor auto-import
  else
    python -m app.cli import-all --only-new --actor auto-import
  fi
fi

# The API is only reachable through the reverse proxy on the internal Docker network,
# so forwarded client addresses from it are trusted (used for rate limiting).
exec uvicorn app.main:create_app --factory \
  --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips="*" \
  --workers "${ADVISOR_WORKERS:-2}" \
  --no-access-log
