# 0001. Stack and deployment

Date: 2026-10-08. Status: accepted.

## Context

A single developer has two months for a prototype that the CS head of department and AUIB IT must be
able to approve, and the app may later move to AUIB IT's servers. The requirements document suggests
Next.js, FastAPI, PostgreSQL and a small cloud host, and requires that everything is containerised so a
server change is easy.

## Decision

- One repository with `api/` (Python 3.13, FastAPI, SQLAlchemy 2, Alembic), `web/` (Next.js 16,
  TypeScript, Tailwind CSS) and `data/programs/`.
- PostgreSQL 17 as the database; migrations are versioned with Alembic and checked against the models
  in CI.
- Docker images for the API and web app, run with Docker Compose together with PostgreSQL and a Caddy
  reverse proxy. Caddy is the only service with published ports and provides automatic HTTPS.
- The web app is typed against the API's OpenAPI schema (`openapi-typescript`); CI fails if they drift.

## Consequences

- One command starts the whole system anywhere Docker runs; moving servers means copying the folder,
  `.env` and a backup.
- Python keeps the planning code in the same language as the scraper and gives strict validation via
  Pydantic. Two languages (Python and TypeScript) must be maintained, which the schema-generated types
  keep in step.
- Compose suits one server. If AUIB later runs Kubernetes, the same images can be deployed there.
