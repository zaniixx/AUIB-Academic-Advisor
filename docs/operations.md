# Operations

Everything runs from `docker compose`. A server needs Docker with Compose, this repository and a `.env`
file. Moving to a new server needs the same three things plus a database backup, and takes well under
the two-hour portability target. The app also runs on Heroku; see [Heroku](#heroku).

## First deployment

1. Install Docker Engine with the Compose plugin.
2. Copy the repository to the server (for example `git clone`).
3. Create `.env` from `.env.example`:
   - `POSTGRES_PASSWORD`: `openssl rand -hex 32` (letters and digits only: the password is also part of
     the API's database address, where `/`, `@` or `:` would break it). PostgreSQL stores it when the
     database is first created; changing it later is a routine task below.
   - `ADVISOR_ADMIN_TOKEN`: `openssl rand -hex 32` (leave empty to switch the admin API off)
   - `ADVISOR_SECRET_KEY`: `openssl rand -hex 32`
   - The `ADVISOR_SMTP_*` settings of the mail server that sends sign-in codes (see
     [Mail for sign-in codes](#mail-for-sign-in-codes)). Without them and the secret key, the API
     refuses to start.
   - `SITE_ADDRESS`: the public domain name for automatic HTTPS, or `:80` for plain HTTP inside a
     trusted network. For HTTPS, ports 80 and 443 must reach the server and DNS must point to it.
4. Start: `docker compose up -d --build`
5. Check: `docker compose ps` shows every service as healthy, and `https://<domain>/api/ready` answers
   `{"status": "ready", ...}`. If the `api` container keeps restarting, `docker compose logs api` lists
   the settings that are missing (the API checks them with `python -m app.cli check-settings` before
   it starts).

On start the API applies database migrations and, with `ADVISOR_AUTO_IMPORT=true`, imports the course
catalog and every package in `data/programs/` that is not in the database yet (all of them on first
start, and new programs such as a minor after an update).

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | (required) | Database password |
| `ADVISOR_ADMIN_TOKEN` | empty | Admin API token, at least 32 characters; empty switches the admin API off |
| `SITE_ADDRESS` | `:80` | Domain for automatic HTTPS, or `:80` for HTTP |
| `HTTP_PORT`, `HTTPS_PORT` | `80`, `443` | Host ports the proxy listens on |
| `ADVISOR_AUTO_IMPORT` | `true` | On start, import program packages that are not in the database yet |
| `ADVISOR_AUTO_IMPORT_ACCEPT_WARNINGS` | `false` | Publish auto-imported packages that have validation warnings (never errors) |
| `ADVISOR_API_DOCS` | `false` | Serve interactive API documentation at `/api/docs` |
| `ADVISOR_RATE_LIMIT_PER_MINUTE` | `60` | Planning and sign-in requests per minute per client address |
| `ADVISOR_SECRET_KEY` | (required) | Keys the hashes of sign-in codes; at least 32 random characters. Changing it only stops codes already sent |
| `ADVISOR_ALLOWED_EMAIL_DOMAINS` | `["auib.edu.iq"]` | Email domains that may sign in, as a JSON list; only exact matches, not subdomains |
| `ADVISOR_MAIL_MODE` | `smtp` | `smtp` emails the codes. `log` writes them to the API log instead, for a trial on your own computer with `ADVISOR_ENVIRONMENT=development`; refused in production |
| `ADVISOR_SMTP_HOST`, `ADVISOR_SMTP_PORT` | (required), `587` | The mail server |
| `ADVISOR_SMTP_SECURITY` | `starttls` | `starttls` (port 587), `ssl` (port 465) or `none` |
| `ADVISOR_SMTP_USERNAME`, `ADVISOR_SMTP_PASSWORD` | empty | SMTP login; leave empty for a relay that does not need one |
| `ADVISOR_SMTP_FROM` | (required) | The sender, such as `AUIB Academic Advisor <advisor@auib.edu.iq>` |
| `ADVISOR_SESSION_DAYS` | `30` | Days a sign-in lasts |
| `ADVISOR_LOGIN_CODE_MINUTES` | `10` | Minutes a sign-in code works |
| `ADVISOR_MAX_ADMIN_REQUEST_BYTES` | `8000000` | Largest admin upload (a course list or term schedule); other requests stay at 512 KB |
| `ADVISOR_BACKUP_PASSPHRASE` | empty | Only for the backup commands, so they can run unattended; otherwise they ask for it |
| `ADVISOR_WORKERS` | `2` | API worker processes |
| `ADVISOR_DB_POOL_SIZE`, `ADVISOR_DB_MAX_OVERFLOW` | `5`, `10` | Database connections per API worker: kept open, and extra at busy moments |
| `ADVISOR_LOG_LEVEL` | `INFO` | API log level |
| `APP_VERSION` | `latest` | Image tag |

## Routine tasks

| Task | Command |
| --- | --- |
| Update to a new version | `git pull && docker compose up -d --build` (migrations run on start) |
| Import or re-import the catalog and program data | `docker compose exec api python -m app.cli import-all` |
| Validate the catalog and packages without importing | `docker compose exec api python -m app.cli validate` |
| Back up the database | `sh scripts/backup-db.sh` (writes `backups/advisor-<date>.dump`) |
| Restore a backup | `sh scripts/restore-db.sh backups/advisor-<date>.dump` |
| Take an encrypted backup | Admin page, Backup and restore tab; or `docker compose exec api python -m app.cli backup-export /tmp/advisor.aab` |
| Check an encrypted backup | `python -m app.cli backup-inspect FILE` (asks for the passphrase; shows the rows per table) |
| Restore an encrypted backup | See [Encrypted backups](#encrypted-backups) |
| Rotate the admin token | Edit `ADVISOR_ADMIN_TOKEN` in `.env`, then `docker compose up -d api` |
| Change the database password | Editing `.env` alone is not enough: PostgreSQL keeps the password it was created with, and the API is then refused (`password authentication failed for user "advisor"`). First `docker compose exec db psql -U advisor -c "ALTER USER advisor WITH PASSWORD '<new password>'"`, then set the same value as `POSTGRES_PASSWORD` in `.env` and run `docker compose up -d` |
| Sign every student out | `docker compose exec db psql -U advisor -c "delete from sessions"` |
| Sign one student out everywhere | `docker compose exec db psql -U advisor -c "delete from sessions where email = 'name@auib.edu.iq'"` |
| Check that codes can be sent | Sign in on the site with your own AUIB address; if mail fails, the API log says `Could not send a sign-in code` with the error type |
| Logs | `docker compose logs -f api` (JSON lines: method, path, status, duration, request ID) |
| Health | `/api/health` (process up), `/api/ready` (database and catalog loaded) |

Schedule `scripts/backup-db.sh` daily with cron and copy the files off the server. The database holds
only catalog data, admin records and sign-in sessions, so a lost database can also be rebuilt from
`data/catalog/` and `data/programs/` (students then sign in again). What only a backup brings back is the work done in the admin page: rule corrections,
courses and programs added or edited there, hidden courses and programs, term schedules, and the audit
log.

## Encrypted backups

An admin can download an encrypted backup from the admin page (Backup and restore tab) without server
access, and carry it off-site. It holds every table in the database (there is no student data) and is encrypted
with AES-256-GCM under a key derived from a passphrase with scrypt. The passphrase is never stored or
logged; without it the file cannot be read, and any change to the file is detected. The admin page can
create a random 43-character key; keep it in a password manager, apart from the file.

To restore one from the admin page, open Backup and restore, choose the file and enter its
passphrase or key, and check it: the page shows when it was made and how many courses, rules, programs
and schedules it holds next to what the system holds now. Nothing changes until you type RESTORE. Then:

- the current data is saved first and downloads as an encrypted backup with the same passphrase, so the
  restore can be undone by restoring that file;
- courses, rules, majors and minors, term schedules and the import history are replaced in one
  transaction, and every API worker picks up the restored catalog on its next request;
- the audit log is kept as it is (it is never rolled back) and records the restore.

To restore on the server instead, for example when moving to a new server (this restores the audit log
too):

```sh
docker compose cp advisor-backup.aab api:/tmp/advisor-backup.aab
docker compose exec -it api python -m app.cli backup-inspect /tmp/advisor-backup.aab
docker compose exec -it api python -m app.cli backup-restore /tmp/advisor-backup.aab --yes
```

Both commands ask for the passphrase (or read `ADVISOR_BACKUP_PASSPHRASE`). A restore replaces every
table in one transaction, so a wrong file changes nothing, and it is recorded in the audit log. A
backup restores only into the database schema version that made it: restore with the matching app
version, then update. The file format is described in `api/app/services/backup.py`.

## Moving to another server

1. On the old server: `sh scripts/backup-db.sh`.
2. On the new server: copy the repository, `.env` and the backup file.
3. `docker compose up -d --build`, then `sh scripts/restore-db.sh backups/<file>.dump`.
4. Point DNS at the new server. Caddy obtains a certificate on its own.

## Mail for sign-in codes

Students sign in with a code sent to their `@auib.edu.iq` address
([ADR 0007](decisions/0007-sign-in-with-auib-email.md)), so the app needs an SMTP server that may send
mail to AUIB mailboxes. Two ways:

- **AUIB's own mail system (preferred).** Ask AUIB IT for an SMTP relay or a mailbox the app may send
  from, such as `advisor@auib.edu.iq`. Addresses then never leave the university. With Microsoft 365
  this is `smtp.office365.com`, port 587, `starttls`, and the mailbox's user name and password (IT
  may need to allow SMTP sign-in for that mailbox); with Google Workspace, `smtp.gmail.com` and an app
  password, or IT's SMTP relay.
- **A sending service** such as Mailgun, Postmark, SendGrid or Brevo, each with a free tier that
  covers sign-in codes. Verify the sending domain with the service and add the SPF and DKIM records it
  gives you, or codes will land in junk mail. Use the service's SMTP host, port 587, `starttls`, and
  the SMTP user name and password (or API key) it shows.

Then set `ADVISOR_SMTP_HOST`, `ADVISOR_SMTP_PORT`, `ADVISOR_SMTP_SECURITY`, `ADVISOR_SMTP_USERNAME`,
`ADVISOR_SMTP_PASSWORD` and `ADVISOR_SMTP_FROM`, and sign in once with your own address to check. To try
the app on your own computer without a mail server, set `ADVISOR_ENVIRONMENT=development` and
`ADVISOR_MAIL_MODE=log`; codes then appear in `docker compose logs api`.

## Heroku

The app also runs on Heroku, as one container per app on Heroku's container stack
([ADR 0006](decisions/0006-heroku.md)). Heroku builds the image from the repository on each push, so
the Compose set-up above stays as it is.

| File | What it does |
| --- | --- |
| [heroku.yml](../heroku.yml) | Builds `Dockerfile.heroku`, runs `release.sh` in the release phase and `start.sh` in the web dyno |
| [Dockerfile.heroku](../Dockerfile.heroku) | One image with the API, the web server and Caddy |
| [deploy/heroku/start.sh](../deploy/heroku/start.sh) | Starts the API and the web server on 127.0.0.1 and Caddy on `$PORT`; if one stops, the dyno exits and Heroku restarts it |
| [deploy/heroku/release.sh](../deploy/heroku/release.sh) | Before each release goes live: database migrations, then the catalog and any new program packages |
| [deploy/heroku/Caddyfile](../deploy/heroku/Caddyfile) | The routing, body limits and headers of `deploy/Caddyfile`, plus a redirect from HTTP to HTTPS |
| [app.json](../app.json) | The add-on and config vars, for the "Deploy to Heroku" button and review apps |
| [.dockerignore](../.dockerignore) | What the build may see: never `sis_data/` or `.env` |

CI builds this image on every push, runs its release phase against PostgreSQL and smoke-tests the
running dyno as a non-root user, as Heroku runs it (the `heroku` job in `.github/workflows/ci.yml`).

### First deployment on Heroku

Heroku deploys automatically from the GitHub branch `Prod`, after CI has passed on it. Changes reach
`Prod` by a pull request from `main`, so they are reviewed and tested before students see them.

You need a Heroku account with billing set up (a Basic dyno and Heroku Postgres Essential cost a few
dollars a month). Everything is done in the browser; Heroku builds and runs the containers itself.

1. **Put the Heroku files on `Prod`.** On GitHub, open a pull request from `main` into `Prod` and
   merge it once its checks pass. Heroku reads `app.json` and `heroku.yml` from `Prod`.
2. **Create the app from `app.json`.** Open
   <https://www.heroku.com/deploy?template=https://github.com/zaniixx/AUIB-Academic-Advisor/tree/Prod>,
   choose an app name and the Europe or United States region, fill in the SMTP settings of the mail
   server (see [Mail for sign-in codes](#mail-for-sign-in-codes)) and press Deploy app. `app.json` gives
   the app the container stack (so Heroku builds `Dockerfile.heroku` as `heroku.yml` says), Heroku
   Postgres Essential 0 (which sets `DATABASE_URL`), a Basic web dyno and the config vars, including a
   freshly generated `ADVISOR_ADMIN_TOKEN` and `ADVISOR_SECRET_KEY`. The first build takes several minutes; then the release
   phase migrates the database and imports the catalog and every program package.
3. **Keep the admin token.** Settings tab, Reveal Config Vars: `ADVISOR_ADMIN_TOKEN` signs in to
   `/admin`.
4. **Connect GitHub.** Deploy tab, Deployment method GitHub: connect your GitHub account, find the
   repository and press Connect.
5. **Turn on automatic deploys.** In Automatic deploys, choose the branch `Prod`, tick "Wait for CI to
   pass before deploy" and press Enable Automatic Deploys. CI runs on every push to `Prod`
   (`.github/workflows/ci.yml`), and Heroku deploys only when every check has passed.
6. **Check it.** The Activity tab shows each build and release; a release must not say "failed".
   `https://<app>.herokuapp.com/api/ready` answers `{"status": "ready", ...}`. Open the site, sign in
   with your AUIB address and check that the code arrives.

**An app created before sign-in existed** has no secret key or SMTP settings. Add them in Settings,
Reveal Config Vars, before the sign-in change reaches `Prod`: `ADVISOR_SECRET_KEY` (64 random
characters, for example from `openssl rand -hex 32` or a password manager), `ADVISOR_MAIL_MODE=smtp`
and the `ADVISOR_SMTP_*` settings. Without them the release phase stops with "Set ADVISOR_SECRET_KEY
…", and the previous release keeps running.

From then on, every merge into `Prod` deploys by itself. To go back to the previous release, use
Roll back on the Activity tab (it does not undo database migrations).

With the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli), step 2 can be done by hand
instead: `heroku create <app> --stack container --region eu`, `heroku addons:create
heroku-postgresql:essential-0`, and the config vars from `app.json` with `heroku config:set`
(`ADVISOR_ADMIN_TOKEN` and `ADVISOR_SECRET_KEY` from `openssl rand -hex 32`, the SMTP settings;
`ADVISOR_DB_POOL_SIZE=3`,
`ADVISOR_DB_MAX_OVERFLOW=2`, `ADVISOR_AUTO_IMPORT_ACCEPT_WARNINGS=true`). An app's stack can only
be set this way or through `app.json`; the dashboard does not offer it.

A custom domain such as `advisor.auib.edu.iq`:

```sh
heroku domains:add advisor.auib.edu.iq -a auib-advisor   # prints the DNS target for a CNAME record
heroku certs:auto:enable -a auib-advisor                 # Heroku obtains and renews the certificate
```

### Config vars on Heroku

Heroku Postgres sets `DATABASE_URL`; the API turns it into its own form and requires TLS to the
database (`ADVISOR_DATABASE_URL`, when set, wins). The image sets `ADVISOR_ENVIRONMENT=production`
and `ADVISOR_API_DOCS=false`. The other variables in [Configuration](#configuration) work as config
vars too, apart from `POSTGRES_PASSWORD`, `SITE_ADDRESS`, `HTTP_PORT`, `HTTPS_PORT` and `APP_VERSION`,
which only the Compose set-up uses. Heroku-specific ones:

| Variable | Default | Meaning |
| --- | --- | --- |
| `ADVISOR_WORKERS` | `2` | API worker processes. Two fit a 512 MB Basic dyno with the web server and Caddy (about 400 MB in all); use `1` if Heroku logs memory errors (R14) |
| `ADVISOR_DB_POOL_SIZE`, `ADVISOR_DB_MAX_OVERFLOW` | `5`, `10` | Connections per API worker, kept open and extra at busy moments. Heroku Postgres Essential allows 20 in all, so use `3` and `2` |
| `ADVISOR_FORWARDED_ALLOW_IPS` | loopback and private ranges | Proxies whose `X-Forwarded-For` the API trusts; the client address is the last one not in this list |

### Routine tasks on Heroku

| Task | Command (add `-a <app>`) |
| --- | --- |
| Update to a new version | Merge a pull request from `main` into `Prod`: CI, then build, release phase (migrations and new packages) and restart |
| Import changed catalog or program data | `heroku run python -m app.cli import-all --accept-warnings` |
| Validate the catalog and packages | `heroku run python -m app.cli validate` |
| Back up the database | `heroku pg:backups:schedule DATABASE_URL --at "02:00 Asia/Baghdad"` once; `heroku pg:backups:capture` for one now |
| Download a backup (a standard `pg_dump` file) | `heroku pg:backups:download` |
| Restore a backup | `heroku pg:backups:restore <backup-id> DATABASE_URL` |
| Take or restore an encrypted backup | Admin page, Backup and restore tab, as in [Encrypted backups](#encrypted-backups) |
| Rotate the admin token | `heroku config:set ADVISOR_ADMIN_TOKEN=<new token>` (restarts the dyno) |
| Change the mail settings | Settings tab, Reveal Config Vars, or `heroku config:set ADVISOR_SMTP_HOST=...` |
| Sign every student out | `heroku pg:psql -c "delete from sessions"` |
| Logs | `heroku logs --tail` (the API's JSON lines, Caddy's access log and Heroku's router log) |
| Roll back a release | `heroku rollback`. It does not undo database migrations; restore a backup if one must go |

`scripts/backup-db.sh` and `scripts/restore-db.sh` are for the Compose set-up; Heroku's backups replace
them. To move from Heroku to a server, download a backup and restore it with `scripts/restore-db.sh`.

### What to know about Heroku

- **How a request travels.** Heroku's router (HTTPS) → the dyno's Caddy on `$PORT` → `/api/*` to the
  API on 127.0.0.1:8000, everything else to the web server on 127.0.0.1:3000.
- **Client addresses.** Heroku's router appends the address it saw to `X-Forwarded-For` and Caddy
  passes the header on unchanged; the API counts the last address not in `ADVISOR_FORWARDED_ALLOW_IPS`
  for the rate limit, so a visitor cannot choose their own.
- **Restarts.** Heroku restarts each dyno about once a day. Nothing is lost: students' data is in their
  browsers and everything else is in Heroku Postgres. The dyno's file system is temporary.
- **Region.** The database holds catalog data, admin records and the AUIB email addresses of
  signed-in students, never students' courses or grades. Choose `--region eu` or `us` when the app is created.
- **Size.** One Basic dyno plans a degree in tens of milliseconds. For registration week, a larger dyno
  with more `ADVISOR_WORKERS`, or more dynos, adds capacity (see [Scaling notes](#scaling-notes)).

## Scaling notes

One small server (2 vCPUs, 2 GB RAM) is enough for the prototype: a plan takes about 30 ms of CPU. For
the 500-concurrent-user registration-week target, raise `ADVISOR_WORKERS`. The rate limiter counts per
API process, so behind several API servers add a shared limit at the proxy or load balancer as well.
