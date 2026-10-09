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
| `ADVISOR_MAX_ADMIN_REQUEST_BYTES` | `8000000` | Largest admin upload (a course list or term schedule); other requests stay at 512 KB |
| `ADVISOR_BACKUP_PASSPHRASE` | empty | Only for the backup commands, so they can run unattended; otherwise they ask for it |
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
| Take an encrypted backup | Admin page, Backup and restore tab; or `docker compose exec api python -m app.cli backup-export /tmp/advisor.aab` |
| Check an encrypted backup | `python -m app.cli backup-inspect FILE` (asks for the passphrase; shows the rows per table) |
| Restore an encrypted backup | See [Encrypted backups](#encrypted-backups) |
| Rotate the admin token | Edit `ADVISOR_ADMIN_TOKEN` in `.env`, then `docker compose up -d api` |
| Logs | `docker compose logs -f api` (JSON lines: method, path, status, duration, request ID) |
| Health | `/api/health` (process up), `/api/ready` (database and catalog loaded) |

Schedule `scripts/backup-db.sh` daily with cron and copy the files off the server. The database holds
only catalog data and admin records, so a lost database can also be rebuilt from `data/catalog/` and
`data/programs/`. What only a backup brings back is the work done in the admin page: rule corrections,
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

## Scaling notes

One small server (2 vCPUs, 2 GB RAM) is enough for the prototype: a plan takes about 30 ms of CPU. For
the 500-concurrent-user registration-week target, raise `ADVISOR_WORKERS`. The rate limiter counts per
API process, so behind several API servers add a shared limit at the proxy or load balancer as well.
