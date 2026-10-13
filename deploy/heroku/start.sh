#!/usr/bin/env bash
# Heroku web dyno: the API and the Next.js server on localhost, and Caddy in front on $PORT.
#
# If any of the three stops, the others are stopped too and the dyno exits, so Heroku restarts it.
# Heroku's SIGTERM at shutdown is passed on to all three.
set -euo pipefail

: "${PORT:?Heroku sets PORT}"

# Heroku's router appends the address it saw the visitor connect from to X-Forwarded-For, and
# Caddy passes the header on unchanged. The API reads the last address not in this list, so a
# visitor cannot pick their own address (it is used for the rate limit). Caddy calls the API from
# 127.0.0.1; the private ranges cover Heroku's own hops.
FORWARDED_ALLOW_IPS="${ADVISOR_FORWARDED_ALLOW_IPS:-127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16}"

cd /app/api
uvicorn app.main:create_app --factory \
  --host 127.0.0.1 --port 8000 \
  --proxy-headers --forwarded-allow-ips="$FORWARDED_ALLOW_IPS" \
  --workers "${ADVISOR_WORKERS:-2}" \
  --no-access-log &

(cd /app/web && HOSTNAME=127.0.0.1 PORT=3000 exec node server.js) &

# Wait until both answer before opening $PORT, so the first visitors after a restart are not
# turned away. Heroku needs $PORT within 60 seconds, so give up waiting after 40.
python - <<'PYTHON' || echo "start.sh: the API or the web server is slow to start; opening the port anyway" >&2
import time
import urllib.request

deadline = time.monotonic() + 40
for url in ("http://127.0.0.1:8000/api/health", "http://127.0.0.1:3000/privacy"):
    while True:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    break
        except OSError:
            pass
        if time.monotonic() > deadline:
            raise SystemExit(1)
        time.sleep(0.5)
PYTHON

caddy run --config /app/deploy/heroku/Caddyfile --adapter caddyfile &

stop_all() {
  trap - TERM INT
  kill -TERM $(jobs -p) 2>/dev/null || true
}
trap stop_all TERM INT

status=0
wait -n || status=$?
echo "start.sh: a process exited (status $status); stopping the dyno" >&2
stop_all
wait || true
exit "$status"
