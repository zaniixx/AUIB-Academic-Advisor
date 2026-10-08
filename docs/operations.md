# Operations

Everything runs from `docker compose`. A server needs Docker with Compose, this repository and a `.env`
file. Moving to a new server needs the same three things plus a database backup, and takes well under
the two-hour portability target.

## First deployment

1. Install Docker Engine with the Compose plugin.
2. Copy the repository to the server (for example `git clone`).
3. Create `.env` from `.env.example`:
   - `POSTGRES_PASSWORD`: `openssl rand -base64 32`
   - `ADVISOR_ADMIN_TOKEN`: `openssl rand -hex 32` (leave empty to switch the admin API off)
   - `SITE_ADDRESS`: the public domain name for automatic HTTPS, or `:80` for plain HTTP inside a
     trusted network. For HTTPS, ports 80 and 443 must reach the server and DNS must point to it.
4. Start: `docker compose up -d --build`
5. Check: `docker compose ps` shows every service as healthy, and `https://<domain>/api/ready` answers
   `{"status": "ready", ...}`.

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
| `ADVISOR_RATE_LIMIT_PER_MINUTE` | `60` | Planning requests per minute per client address |
| `ADVISOR_WORKERS` | `2` | API worker processes |
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
| Rotate the admin token | Edit `ADVISOR_ADMIN_TOKEN` in `.env`, then `docker compose up -d api` |
| Logs | `docker compose logs -f api` (JSON lines: method, path, status, duration, request ID) |
| Health | `/api/health` (process up), `/api/ready` (database and catalog loaded) |

Schedule `scripts/backup-db.sh` daily with cron and copy the files off the server. The database holds
only catalog data and admin records, so a lost database can also be rebuilt from `data/programs/`; only
admin rule corrections and the audit log would need the backup.

## Moving to another server

1. On the old server: `sh scripts/backup-db.sh`.
2. On the new server: copy the repository, `.env` and the backup file.
3. `docker compose up -d --build`, then `sh scripts/restore-db.sh backups/<file>.dump`.
4. Point DNS at the new server. Caddy obtains a certificate on its own.

## Scaling notes

One small server (2 vCPUs, 2 GB RAM) is enough for the prototype: a plan takes about 30 ms of CPU. For
the 500-concurrent-user registration-week target, raise `ADVISOR_WORKERS`. The rate limiter counts per
API process, so behind several API servers add a shared limit at the proxy or load balancer as well.
