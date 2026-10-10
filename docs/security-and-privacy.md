# Security and privacy

The app handles one kind of sensitive data, a student's course history and grades, and is built so that
data never has to be stored. This page lists what is handled, where it goes and how it is protected,
followed by the open items before a university-wide launch.

## Data inventory

| Data | Source | Where it lives | Retention |
| --- | --- | --- | --- |
| Course catalog: courses, descriptions, requirement groups | SIS, scraped under one student's login | PostgreSQL and `data/programs/` | Until replaced by a newer import |
| Prerequisite corrections, courses and programs edited in the admin page, term schedules, import history, audit log | Data maintainers | PostgreSQL | Kept as an audit trail |
| Encrypted backups of the above | An admin (admin page or CLI) | Wherever the admin stores the file | Set by whoever keeps it; unreadable without the passphrase |
| A student's courses, grades, answers to the quick questions (interests, what they would rather avoid, plans after graduating), plan settings and up to 3 saved plans to compare (F6.2) | The student, typed or pasted | **The student's browser only** (local storage) | Until the student clears it |
| The same data while a plan is computed | Sent with each planning request | API memory for the length of the request | Discarded when the response is sent |
| Pasted Course History text | The student | API memory while it is parsed | Discarded when the response is sent |
| Request logs: time, method, path, status, duration, request ID | API | Container log output | Set by the host's log rotation |
| Proxy access logs: as above plus client IP address | Caddy | Container log output | Set by the host's log rotation |

What is **not** collected: names, student IDs, email addresses, SIS passwords or sessions. The app never
logs into SIS. Request bodies and query strings are never logged by the API, and error responses never
echo submitted values.

### The scraper's raw output

The scraper that produced the CS data runs on a student's own machine under their own SIS login. Its
output folder (`sis_data/`) contains a logged-in browser profile and pages that show that student's
progress. It is listed in `.gitignore` and excluded from every Docker build context. The committed
course catalog (`data/catalog/`) and package in `data/programs/` are produced by
`scripts/prepare_program_package.py`, which removes the per-student fields (`page_text`, `element_id`)
and keeps only catalog facts. The minors were written by hand from announcements sent to all students, and the other majors were
generated from AUIB's published curricula (`scripts/curricula`); none of these hold personal data.

## Controls

| Area | Control | Where |
| --- | --- | --- |
| Transport | HTTPS with automatic certificates and HTTP-to-HTTPS redirect when `SITE_ADDRESS` is a domain; HSTS header | `deploy/Caddyfile` |
| Network | Only the proxy publishes ports; PostgreSQL is on an internal network with no route in or out | `docker-compose.yml` |
| Containers | Non-root users in the API and web images; minimal base images (`python:3.13-slim`, `node:24-alpine`) | `api/Dockerfile`, `web/Dockerfile` |
| Secrets | Database password and admin token come from `.env`, which is git-ignored; the app refuses to start in production with SQLite or a short admin token | `.env.example`, `app/settings.py` |
| Admin access | Bearer token compared in constant time; admin API switched off when no token is set; every admin action written to the audit log | `app/api/deps.py`, `app/api/routes/admin.py` |
| Input | Every request field is bounded (lengths, list sizes, value ranges) and unknown fields are rejected; bodies over 512 KB are refused by the API and over 1 MB by the proxy, except admin uploads (8 MB, admin token required) | `app/api/schemas.py`, `app/api/admin_schemas.py`, `app/security.py` |
| Uploaded tables | CSV and pasted tables are read with Python's `csv` module; an .xlsx file is unpacked with the standard library only, with limits on file size (5 MB), unpacked size (60 MB), rows (5,000), columns and cell length, and any part that declares a DTD is refused, which rules out XML entity attacks | `app/importer/tables.py` |
| Backups | AES-256-GCM with a 256-bit key derived from the passphrase by scrypt (n=2^15, r=8, p=1), a random salt and nonce per file, and the header authenticated; the passphrase is never stored or logged. Restoring from the admin page needs the admin token, the file's passphrase and a typed confirmation; the data from before the restore is saved and returned first, and the audit log is never rolled back. The server command restores everything and needs `--yes` | `app/services/backup.py`, `app/api/routes/admin_catalog.py`, `app/cli.py` |
| Abuse | Per-client rate limit on planning endpoints (60 requests a minute by default) | `app/security.py` |
| Browser | Content Security Policy, `X-Frame-Options: DENY`, `nosniff`, strict referrer policy, permissions policy; planning and admin responses are `Cache-Control: no-store` | `web/next.config.ts`, `app/security.py` |
| Storage in the browser | Profile and saved plans in local storage, both removed by a "Clear my data" button on the plan and privacy pages; admin token in session storage only | `web/src/lib/profile.ts` |
| Dependencies | Pinned versions; `pip-audit` and `npm audit` (production dependencies) run in CI; Dependabot opens weekly update PRs | `.github/` |
| Code quality | Strict type checking (mypy, TypeScript), linting with security rules (Ruff's Bandit set), 306 API tests, browser tests including automated WCAG 2.1 AA checks | CI workflow |

At the time of writing, `pip-audit` and `npm audit --omit=dev` report no known vulnerabilities. `npm
audit` without `--omit=dev` reports a denial-of-service advisory in a glob library used only by the
ESLint tooling; it never ships in the production image.

## Threats considered

| Threat | Mitigation |
| --- | --- |
| A database breach exposes students' grades | Grades are never stored on the server |
| Someone on a shared lab computer sees another student's plan | "Clear my data" on every plan; the privacy page tells students to clear data on shared computers; nothing is tied to an identity |
| Wrong prerequisites lead a student to a wrong plan | Every rule is shown beside its SIS source sentence; unclear text becomes a visible note, never a silent guess; admin review queue; disclaimer on every plan that the registrar's audit is authoritative |
| Admin token leak | Token is long and random, rotated by changing `.env` and restarting the API; all admin actions are audited and reversible (course edits can be undone, hidden items shown again, and a backup restored) |
| A backup file is lost or stolen | It is encrypted; without the passphrase it reveals nothing, and it never contains student data |
| A leaked admin token used to restore a crafted backup | The same token could already edit the catalog piece by piece; a restore is recorded in the audit log, which a restore never replaces, and an earlier backup puts the data back |
| A crafted spreadsheet upload | Size, row and cell limits; no DTDs; uploads are previewed and saved all or nothing; only admins can upload |
| Flooding the planner | Rate limit, body size limits at the proxy and the API, bounded inputs; a plan is computed in about 30 ms |
| Script injection | React escapes all output; the API returns JSON only with `default-src 'none'`; CSP restricts scripts to the app's own origin |
| Supply chain | Pinned dependencies, audits in CI, Dependabot, official base images |

## Open items before a university-wide launch

- [ ] Replace the shared admin token with AUIB single sign-on (Google or Microsoft, restricted to AUIB
      accounts) when accounts arrive (F9.1).
- [ ] Tighten the Content Security Policy from `'unsafe-inline'` scripts to nonces or Subresource
      Integrity (supported by Next.js; needs dynamic rendering or an experimental flag).
- [ ] Agree log retention with AUIB IT (proxy logs contain client IP addresses).
- [ ] Encrypt the nightly `pg_dump` backups at rest too (`scripts/backup-db.sh` shows the `gpg` step).
      Backups taken from the admin page or `backup-export` are already encrypted.
- [ ] A penetration test or review by AUIB IT before the full release.
- [ ] Confirm with IT that the scraper may be used, or replace it with a registrar export
      (requirements document, open questions).
