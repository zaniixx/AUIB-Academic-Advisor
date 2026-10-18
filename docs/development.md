# Running and developing the app

How to run the AUIB Academic Advisor on a server or on your own computer, and how to work on its code.
For what the app does and how it protects students' data, see the [README](../README.md).

## Run it

You need Docker with Compose.

```sh
cp .env.example .env        # set POSTGRES_PASSWORD, ADVISOR_ADMIN_TOKEN, ADVISOR_SECRET_KEY and the SMTP settings
docker compose up -d --build
```

Sign-in codes are emailed, so the API needs an SMTP server that can reach `@auib.edu.iq` mailboxes
(see [operations.md, Mail for sign-in codes](operations.md#mail-for-sign-in-codes)). To try
the app without one, set `ADVISOR_ENVIRONMENT=development` and `ADVISOR_MAIL_MODE=log` in `.env`; the
codes then appear in `docker compose logs api`.

Open http://localhost. On start the API applies database migrations and imports the course catalog
(`data/catalog/`) and every program package in `data/programs/` that is not imported yet. To serve a real domain with automatic HTTPS, set `SITE_ADDRESS` in `.env`
(see [operations.md](operations.md)).

On Heroku, the app deploys automatically from the `Prod` branch once CI passes: a container-stack app
with Heroku Postgres, connected to this repository. The set-up steps are in
[operations.md, Heroku](operations.md#heroku).

## Develop

| Part | Folder | Stack |
| --- | --- | --- |
| API and planning engine | [api/](../api) | Python 3.13, FastAPI, SQLAlchemy, Alembic, NetworkX |
| Web app | [web/](../web) | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Design system | [design-system/](../design-system/auib-academic-advisor/MASTER.md) | AUIB colours, components, motion and accessibility rules for the web app |
| Course catalog | [data/catalog/](../data/catalog) | Every AUIB course, shared by all programs, in the SIS scraper's format |
| Program data | [data/programs/](../data/programs) | One package per major or minor: requirements and labels |
| Deployment | [docker-compose.yml](../docker-compose.yml), [deploy/](../deploy); on Heroku [heroku.yml](../heroku.yml), [Dockerfile.heroku](../Dockerfile.heroku), [deploy/heroku/](../deploy/heroku) | Docker, PostgreSQL 17, Caddy; Heroku container stack and Heroku Postgres |

API (from `api/`):

```sh
python -m venv .venv && .venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head                                  # SQLite file by default
python -m app.cli import-all --accept-warnings        # load data/catalog and data/programs
uvicorn app.main:create_app --factory --reload        # http://localhost:8000/api/docs
pytest                                                # 323 tests
ruff check app tests && mypy app
```

Web (from `web/`, with the API running on port 8000):

```sh
npm ci
npm run dev            # http://localhost:3000; /api is proxied to the API
npm run lint && npm run typecheck && npm test
npx playwright test    # end-to-end and accessibility tests against a running stack
```

In development the API writes each sign-in code to its log instead of emailing it, so any
`@auib.edu.iq` address works. The browser tests sign in with sessions from
`python -m app.cli issue-session <address>`, run with `api/.venv` (or set `E2E_SESSION_TOKEN` and
`E2E_SIGN_OUT_TOKEN`, as CI does).

After changing an API response, run `python -m app.cli export-openapi ../web/openapi.json` in `api/` and
`npm run gen:api` in `web/`; CI fails if the web types fall out of date.

## Documentation

- [System diagrams](system-diagrams.md): an overview and one diagram per part, with what to check in an audit
- [Architecture](architecture.md): components, data flow, data model
- [Security and privacy](security-and-privacy.md): what data is handled and how it is protected
- [Operations](operations.md): deploying, configuring, backing up and moving servers
- [Adding a program](data-pipeline.md): from SIS scrape to published program
- [Requirements traceability](requirements-traceability.md): every requirement ID and its status
- [Design decisions](decisions/): why the main choices were made

