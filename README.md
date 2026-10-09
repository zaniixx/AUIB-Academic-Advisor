# AUIB Academic Advisor

A web app that shows each AUIB student what to take next, what is left to graduate, and what a change
(dropping, delaying, switching) does to their graduation date. This repository holds the prototype
described in the [project requirements document](AUIB%20Academic%20Advisor%20—%20Project%20Requirements%20Document.md):
Computer Science first, with other programs added by importing their data.

Students use it without an account: they pick their major, paste their SIS Course History and get a
term-by-term plan. Their courses stay in their browser and are never stored on the server.

## What works today

| Area | Status |
| --- | --- |
| Curriculum import from the SIS scraper, with validation (F0.1, F0.6, F0.7) | Done |
| Prerequisite parsing from course descriptions, 343 of 351 CS-catalog rules fully understood (F0.2) | Done |
| Admin review and correction of rules, kept across re-imports, audit log (F0.3, F9.3) | Done |
| Admin editing: edit, add, bulk-upload (CSV, spreadsheet paste, .xlsx) and hide courses; build, edit and hide majors and minors; edits kept across imports | Done |
| 16 majors: Computer Science from SIS, and Biology, Chemistry, Physics, English Literature, Psychology, International Relations, six Business tracks, Optometry, Anesthesia Technology and Dental Surgery from AUIB's released curricula; Radiologic Sciences, Dental Technology and Pharmacy wait as drafts (F0.6) | Done, to confirm with the colleges |
| Encrypted backup and restore in the admin page (AES-256-GCM, passphrase or generated key); the command line restores too, for moving servers | Done |
| Remaining requirements, eligibility, term-by-term plan, locks (F1.1–F1.6) | Done |
| Drop/delay what-if with graduation impact (F1.5) | Done |
| Build the plan one term at a time: add recommended courses or Auto-fill the term, then finish it; later terms stay a folded-away suggestion (F1.9) | Done |
| Quick questions fitted to the major (what the student enjoys, what they would rather avoid, plans after graduating) and explained elective recommendations (F2.1, F2.2) | Done |
| Gateway courses and longest prerequisite chain (F3.2) | Done |
| Degree map: every course by term with prerequisite arrows (F5.1, F5.2) | Done |
| Printable plan for the advisor on A4: the next semester in detail, an optional overview of every term, sign-off area (F5.4) | Done |
| Minors in Psychology and Teaching and Learning Design, planned with the major; shared courses count toward both (F11.2) | Done, TLD lists to confirm with CEHD |
| "Replace with" for courses the student chooses | Done |
| CGPA, last term GPA and retake suggestions; "Plan my grades": the CGPA from expected grades and the grades a target needs (F7.1–F7.3) | Done, rules to confirm with AUIB |
| Requirement versions: each student follows the version of their major in force when they joined AUIB (F0.4) | Done |
| Offering seasons: internships planned in summer only | Done |
| Progress tracking and "what's left" (F4) | Done |
| Guest mode and Course History paste, data kept in the browser only (F11) | Done |
| Per-term course schedules uploaded in the admin page; a term with one plans only its courses, and terms without one are marked "not confirmed" (F0.5, F1.8) | Done |
| Offering history (F3.1, F3.3) | Waiting for registrar data |
| AUIB sign-in and saved accounts (F9.1, F9.2, F9.4), scenario comparison (F6.2), course requests (F12), reviews (F8) | Next milestones |

The full list, with the code and tests behind each item, is in
[docs/requirements-traceability.md](docs/requirements-traceability.md).

## Run it

You need Docker with Compose.

```sh
cp .env.example .env        # set POSTGRES_PASSWORD and ADVISOR_ADMIN_TOKEN
docker compose up -d --build
```

Open http://localhost. On start the API applies database migrations and imports the course catalog
(`data/catalog/`) and every program package in `data/programs/` that is not imported yet. To serve a real domain with automatic HTTPS, set `SITE_ADDRESS` in `.env`
(see [docs/operations.md](docs/operations.md)).

## Develop

| Part | Folder | Stack |
| --- | --- | --- |
| API and planning engine | [api/](api) | Python 3.13, FastAPI, SQLAlchemy, Alembic, NetworkX |
| Web app | [web/](web) | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Design system | [design-system/](design-system/auib-academic-advisor/MASTER.md) | AUIB colours, components, motion and accessibility rules for the web app |
| Course catalog | [data/catalog/](data/catalog) | Every AUIB course, shared by all programs, in the SIS scraper's format |
| Program data | [data/programs/](data/programs) | One package per major or minor: requirements and labels |
| Deployment | [docker-compose.yml](docker-compose.yml), [deploy/](deploy) | Docker, PostgreSQL 17, Caddy |

API (from `api/`):

```sh
python -m venv .venv && .venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head                                  # SQLite file by default
python -m app.cli import-all --accept-warnings        # load data/catalog and data/programs
uvicorn app.main:create_app --factory --reload        # http://localhost:8000/api/docs
pytest                                                # 278 tests
ruff check app tests && mypy app
```

Web (from `web/`, with the API running on port 8000):

```sh
npm ci
npm run dev            # http://localhost:3000; /api is proxied to the API
npm run lint && npm run typecheck && npm test
npx playwright test    # end-to-end and accessibility tests against a running stack
```

After changing an API response, run `python -m app.cli export-openapi ../web/openapi.json` in `api/` and
`npm run gen:api` in `web/`; CI fails if the web types fall out of date.

## Documentation

- [System diagrams](docs/system-diagrams.md): an overview and one diagram per part, with what to check in an audit
- [Architecture](docs/architecture.md): components, data flow, data model
- [Security and privacy](docs/security-and-privacy.md): what data is handled and how it is protected
- [Operations](docs/operations.md): deploying, configuring, backing up and moving servers
- [Adding a program](docs/data-pipeline.md): from SIS scrape to published program
- [Requirements traceability](docs/requirements-traceability.md): every requirement ID and its status
- [Design decisions](docs/decisions/): why the main choices were made

## Data and privacy in one paragraph

Catalog data (courses, requirements) is public information scraped from SIS and committed as
sanitised packages; the raw scraper output in `sis_data/` contains a logged-in browser profile and
personal progress, so it is git-ignored and never copied into an image. Students' course histories are
processed in memory for each request and never stored or logged. Details are in
[docs/security-and-privacy.md](docs/security-and-privacy.md).
