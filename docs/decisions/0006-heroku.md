# 0006. Hosting on Heroku

Date: 2026-10-13. Status: accepted.

## Context

The app will be hosted on Heroku. Heroku routes web traffic to one process type per app (`web`) and
gives it a port in `$PORT`; it terminates HTTPS at its router; it provides PostgreSQL as an add-on that
sets `DATABASE_URL`. The app is three services (Caddy, the Next.js web server and the API) designed
to run with Docker Compose ([ADR 0001](0001-stack-and-deployment.md)), and Heroku's container stack
can build and run Docker images.

## Decision

- One image, `Dockerfile.heroku`, holds the API, the web server and Caddy. `deploy/heroku/start.sh`
  runs the API and the web server on 127.0.0.1 and Caddy on `$PORT`; if any of them stops, the dyno
  exits and Heroku restarts it. `heroku.yml` builds the image and runs `deploy/heroku/release.sh`
  (migrations, then importing new program packages) in Heroku's release phase.
- Caddy keeps the routing, the body limits and the headers of the Compose set-up
  (`deploy/heroku/Caddyfile`), and sends visitors who arrive over plain HTTP to HTTPS. Heroku's router
  provides HTTPS, including certificates for a custom domain.
- The API reads Heroku's `DATABASE_URL` when `ADVISOR_DATABASE_URL` is not set, names the driver and
  requires TLS to the database. The connection pool is configurable, because Heroku's smallest
  PostgreSQL plans allow 20 connections.
- For the rate limit, the API trusts only Caddy and private addresses, and takes the client address
  from the end of `X-Forwarded-For`, where Heroku's router appends the address it saw. A visitor who
  sends their own `X-Forwarded-For` cannot pick their address.

## Alternatives considered

- **Two Heroku apps** (API and web), with the web app forwarding `/api`: two dynos to pay for, two
  apps to keep in step, and the web server rather than Caddy in front of the API.
- **Heroku's Python and Node.js buildpacks** instead of Docker: the app would no longer run from the
  same images on Heroku, a laptop and an AUIB server.

## Consequences

- The Compose set-up is unchanged, so the app can still move to AUIB IT's servers with
  `docker compose` and a database backup (`heroku pg:backups:download` gives a standard dump).
- Three processes share one dyno's memory: about 400 MB of a Basic dyno's 512 MB with two API workers.
  `ADVISOR_WORKERS=1`, or a larger dyno, gives more room.
- More web dynos are possible, but the rate limit then counts per process per dyno (as with more
  workers under Compose).
- Heroku runs in US and EU regions. The database holds the course catalog, admin records and, while
  students are signed in, their AUIB email addresses ([ADR 0007](0007-sign-in-with-auib-email.md));
  students' courses, grades and plans never reach it ([ADR 0002](0002-stateless-guest-mode.md)).
