# Security and privacy

The app handles one kind of sensitive data, a student's course history and grades, and is built so that
data never has to be stored. Only students with an AUIB email address can use it, so the server also
keeps the addresses of students who are signed in. This page lists what is handled, where it goes and
how it is protected, followed by the open items before a university-wide launch.

## Data inventory

| Data | Source | Where it lives | Retention |
| --- | --- | --- | --- |
| Course catalog: courses, descriptions, requirement groups | SIS, scraped under one student's login, and AUIB's released curricula | PostgreSQL; in the public repository only sealed (`data/sealed/curriculum.sealed`, AES-256-GCM); plain files only on maintainers' computers | Until replaced by a newer import |
| Prerequisite corrections, courses and programs edited in the admin page, term schedules, import history, audit log | Data maintainers | PostgreSQL | Kept as an audit trail |
| Encrypted backups of the above | An admin (admin page or CLI) | Wherever the admin stores the file | Set by whoever keeps it; unreadable without the passphrase |
| A student's courses, grades, answers to the quick questions (interests, what they would rather avoid, plans after graduating), plan settings and up to 3 saved plans to compare (F6.2) | The student, typed or pasted | **The student's browser only** (local storage) | Until the student clears it |
| The same data while a plan is computed | Sent with each planning request | API memory for the length of the request | Discarded when the response is sent |
| Pasted Course History text | The student | API memory while it is parsed | Discarded when the response is sent |
| AUIB email address of each signed-in student, with the session's start, last use and end, and a SHA-256 hash of the session token (F9.1) | The student, when signing in | PostgreSQL (`sessions`) | Until the session ends (30 days), the student signs out, or signs out on every device, which deletes all of their sessions |
| Admins and advisors: AUIB address, role, who added them and when (ADR 0009) | The master token or an admin | PostgreSQL (`staff`); not in encrypted backups | Until removed |
| Sign-in codes: the address, a keyed hash of the code (never the code), times and wrong tries | The app, when a student asks for a code | PostgreSQL (`login_codes`) | Deleted a day after they are created |
| The sign-in code email: address and code | The app | The mail provider (AUIB's SMTP relay or a service such as Mailgun) and the student's mailbox | Set by the provider |
| Which address the browser's saved plan belongs to | The browser, after signing in | The student's browser (local storage) | Until the plan is cleared |
| Request logs: time, method, path, status, duration, request ID | API | Container log output | Set by the host's log rotation |
| Proxy access logs: as above plus client IP address | Caddy | Container log output | Set by the host's log rotation |

What is **not** collected: names, student IDs, SIS passwords or sessions, and email addresses other
than the AUIB address a student signs in with. The app never logs into SIS. Request bodies and query
strings are never logged by the API, error responses never echo submitted values, and sign-in codes
are never logged (except in the development mail mode, which the app refuses in production). The
address and the session are never linked to the courses or plans a student sends: those still go
through the API without being stored.

### The scraper's raw output

The scraper that produced the CS data runs on a student's own machine under their own SIS login. Its
output folder (`sis_data/`) contains a logged-in browser profile and pages that show that student's
progress. It is listed in `.gitignore` and excluded from every Docker build context. The course
catalog (`data/catalog/`) and packages in `data/programs/` are produced by
`scripts/prepare_program_package.py`, which removes the per-student fields (`page_text`, `element_id`)
and keeps only catalog facts. The minors were written by hand from announcements sent to all students, and the other majors were
generated from AUIB's published curricula (`scripts/curricula`); none of these hold personal data.

### Course data in a public repository

The code is public, but the course and program data are only for signed-in AUIB students (F9.1). So
git holds them sealed: the catalog, the packages and the curriculum scripts are one file encrypted with
AES-256-GCM under `ADVISOR_DATA_KEY` ([ADR 0008](decisions/0008-sealed-course-data.md)), and the plain
files are git-ignored. The images carry only the sealed file; the import opens it into a temporary
folder that is deleted afterwards. CI publishes no reports or screenshots, because artifacts of a
public repository can be downloaded by anyone. Individual course codes still appear in tests and
examples.

## Controls

| Area | Control | Where |
| --- | --- | --- |
| Transport | HTTPS with automatic certificates and HTTP-to-HTTPS redirect when `SITE_ADDRESS` is a domain; HSTS header. On Heroku, the router provides HTTPS (Automated Certificate Management for a custom domain), Caddy redirects plain HTTP to HTTPS and the API connects to Heroku Postgres over TLS | `deploy/Caddyfile`, `deploy/heroku/Caddyfile`, `app/settings.py` |
| Network | Only the proxy publishes ports; PostgreSQL is on an internal network with no route in or out. On Heroku, the API and the web server listen on 127.0.0.1 inside the dyno and only Caddy takes Heroku's traffic; the rate limit reads the client address Heroku's router records, which a visitor cannot set | `docker-compose.yml`, `deploy/heroku/start.sh` ([ADR 0006](decisions/0006-heroku.md)) |
| Containers | Non-root users in the API and web images; minimal base images (`python:3.13-slim`, `node:24-alpine`) | `api/Dockerfile`, `web/Dockerfile` |
| Secrets | Database password, the master token, `ADVISOR_DATA_KEY` and the SMTP password (and optionally `ADVISOR_SECRET_KEY`, otherwise derived from the master token) come from `.env`, which is git-ignored (on Heroku, from config vars); the app refuses to start in production with SQLite, a short admin token or a missing or short secret key | `.env.example`, `app/settings.py` |
| Student access (F9.1) | Every catalog and planner endpoint needs a session; only exact `@auib.edu.iq` addresses get a code; 6-digit codes expire after 10 minutes, work once and stop after 5 wrong tries; one code a minute and 5 an hour per address, 10 an hour per visitor; session tokens are 256-bit random values in an `HttpOnly`, `Secure`, `SameSite=Lax` cookie limited to `/api`; the server keeps only hashes of codes (HMAC with `ADVISOR_SECRET_KEY`) and tokens; the app refuses to start in production without the secret key and SMTP settings ([ADR 0007](decisions/0007-sign-in-with-auib-email.md)) | `app/services/auth.py`, `app/api/routes/auth.py`, `app/api/deps.py`, `app/settings.py` |
| Admin access | Admins sign in by AUIB email and need the `admin` role, checked on every request; the audit log records their address. Only the master token (`ADVISOR_ADMIN_TOKEN`, compared in constant time) adds or removes admins, and it opens the admin page in an emergency, recorded as "master token"; admins add or remove advisors ([ADR 0009](decisions/0009-admins-and-advisors-by-email.md)) | `app/api/deps.py`, `app/services/staff.py`, `app/api/routes/admin_staff.py` |
| Input | Every request field is bounded (lengths, list sizes, value ranges) and unknown fields are rejected; bodies over 512 KB are refused by the API and over 1 MB by the proxy, except admin uploads (8 MB, admin token required) | `app/api/schemas.py`, `app/api/admin_schemas.py`, `app/security.py` |
| Uploaded tables | CSV and pasted tables are read with Python's `csv` module; an .xlsx file is unpacked with the standard library only, with limits on file size (5 MB), unpacked size (60 MB), rows (5,000), columns and cell length, and any part that declares a DTD is refused, which rules out XML entity attacks | `app/importer/tables.py` |
| Backups | AES-256-GCM with a 256-bit key derived from the passphrase by scrypt (n=2^15, r=8, p=1), a random salt and nonce per file, and the header authenticated; the passphrase is never stored or logged. Restoring from the admin page needs the admin token, the file's passphrase and a typed confirmation; the data from before the restore is saved and returned first, and the audit log is never rolled back. The server command restores everything and needs `--yes` | `app/services/backup.py`, `app/api/routes/admin_catalog.py`, `app/cli.py` |
| Abuse | Per-client rate limit on planning endpoints and on asking for and entering sign-in codes (60 requests a minute by default), on top of the per-address code limits | `app/security.py`, `app/services/auth.py` |
| Browser | Content Security Policy, `X-Frame-Options: DENY`, `nosniff`, strict referrer policy, permissions policy; planning and admin responses are `Cache-Control: no-store` | `web/next.config.ts`, `app/security.py` |
| Storage in the browser | Profile and saved plans in local storage, both removed by a "Clear my data" button on the plan and privacy pages; when another student signs in on the same browser, the previous student's profile and plans are removed first; signing out offers to remove them (ticked by default); the session cookie cannot be read by scripts; admin token in session storage only | `web/src/lib/profile.ts`, `web/src/lib/auth.ts` |
| Dependencies | Pinned versions; `pip-audit` and `npm audit` (production dependencies) run in CI; Dependabot opens weekly update PRs | `.github/` |
| Code quality | Strict type checking (mypy, TypeScript), linting with security rules (Ruff's Bandit set), 336 API tests, browser tests including automated WCAG 2.1 AA checks | CI workflow |

At the time of writing, `pip-audit` and `npm audit --omit=dev` report no known vulnerabilities. `npm
audit` without `--omit=dev` reports a denial-of-service advisory in a glob library used only by the
ESLint tooling; it never ships in the production image.

## Threats considered

| Threat | Mitigation |
| --- | --- |
| A database breach exposes students' grades | Grades are never stored on the server |
| Someone on a shared lab computer sees another student's plan | Signing out removes the plan from the browser unless the student unticks it; a different student signing in removes the previous student's plan first; "Clear my data" on every plan |
| Someone outside AUIB reads the course data | Every catalog and planner endpoint needs a session, and a session needs a code sent to an `@auib.edu.iq` mailbox; the public repository holds the data only sealed, CI fails if a plain data file is committed, and CI uploads no screenshots |
| The data key leaks | It opens every sealed version, including those in the git history; a new key protects later commits only (operations.md, The data key). The key is shared only with maintainers and servers |
| Guessing a sign-in code | 5 wrong tries end a code (a 1 in 200,000 chance per code); 5 codes an hour per address; codes expire after 10 minutes |
| Flooding a student's mailbox or the mail provider with codes | One code a minute and 5 an hour per address, 10 an hour per visitor, and the rate limit |
| A database copy used to sign in | Codes are stored as keyed hashes and session tokens as SHA-256 hashes; neither can be turned back into a working code or cookie |
| A stolen session cookie | `HttpOnly` (no script can read it), `Secure`, sent only to `/api` and not on cross-site requests (`SameSite=Lax`); "sign out on all my devices" ends every session of the student; an operator can end all sessions with one SQL statement (`docs/operations.md`) |
| Wrong prerequisites lead a student to a wrong plan | Every rule is shown beside its SIS source sentence; unclear text becomes a visible note, never a silent guess; admin review queue; disclaimer on every plan that the registrar's audit is authoritative |
| Master token leak | It is long and random, kept out of daily use, and changed in `.env` or Heroku's config vars without signing admins out; every use is audited as "master token", and admin actions are reversible (course edits undone, hidden items shown again, a backup restored) |
| An admin's mailbox or session is taken over | The attacker gets that admin's rights, but cannot create admins (only the master token can); the master token removes the admin at once, and the audit log shows what was done under that address |
| A former admin keeps access | Removing the role takes effect on the next request; no shared secret has to change |
| A backup file is lost or stolen | It is encrypted; without the passphrase it reveals nothing, and it never contains student data |
| A leaked admin token used to restore a crafted backup | The same token could already edit the catalog piece by piece; a restore is recorded in the audit log, which a restore never replaces, and an earlier backup puts the data back |
| A crafted spreadsheet upload | Size, row and cell limits; no DTDs; uploads are previewed and saved all or nothing; only admins can upload |
| Flooding the planner | Rate limit, body size limits at the proxy and the API, bounded inputs; a plan is computed in about 30 ms |
| Script injection | React escapes all output; the API returns JSON only with `default-src 'none'`; CSP restricts scripts to the app's own origin |
| Supply chain | Pinned dependencies, audits in CI, Dependabot, official base images |

## Open items before a university-wide launch

- [ ] AUIB single sign-on (Google or Microsoft) with IT-managed groups for admins and advisors (F9.4);
      it could replace the emailed codes and fill the role table. Admins already sign in by email
      ([ADR 0009](decisions/0009-admins-and-advisors-by-email.md)).
- [ ] Remove the plain course data from the git history (before it was sealed) and have GitHub purge
      cached views and pull-request refs, or recreate the repository (ADR 0008).
- [ ] Choose the mail provider with AUIB IT: AUIB's own relay keeps addresses inside the university;
      an outside service needs SPF and DKIM records on the sending domain so that codes do not land in
      junk mail.
- [ ] Agree with IT how long a sign-in should last (30 days now) and whether students who leave AUIB
      should be signed out (their mailbox closes, so they cannot sign in again).
- [ ] Tighten the Content Security Policy from `'unsafe-inline'` scripts to nonces or Subresource
      Integrity (supported by Next.js; needs dynamic rendering or an experimental flag).
- [ ] Agree log retention with AUIB IT (proxy logs contain client IP addresses). On Heroku, logs
      stream through Logplex and are kept only by a log add-on or drain, if one is added.
- [ ] On Heroku, confirm with IT that a US or EU region is acceptable for the catalog, the admin
      records and signed-in students' email addresses (their courses and grades never reach the server).
- [ ] Encrypt the nightly `pg_dump` backups at rest too (`scripts/backup-db.sh` shows the `gpg` step).
      Backups taken from the admin page or `backup-export` are already encrypted.
- [ ] A penetration test or review by AUIB IT before the full release.
- [ ] Confirm with IT that the scraper may be used, or replace it with a registrar export
      (requirements document, open questions).
