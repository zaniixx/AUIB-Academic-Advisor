# syntax=docker/dockerfile:1
# API image. Build from the repository root so the course catalog and program data are included:
#   docker build -f api/Dockerfile -t auib-advisor-api .

FROM python:3.14-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

FROM base AS build
WORKDIR /build
COPY api/requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --require-virtualenv -r requirements.txt

FROM base AS runtime
LABEL org.opencontainers.image.title="AUIB Academic Advisor API"
RUN groupadd --system app && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app
COPY --from=build /opt/venv /opt/venv
# The course data ships sealed (ADR 0008); the import opens it with ADVISOR_DATA_KEY at start-up.
ENV PATH="/opt/venv/bin:$PATH" \
    ADVISOR_SEALED_DATA=/data/sealed/curriculum.sealed
WORKDIR /app
COPY api/alembic.ini ./
COPY api/migrations ./migrations
COPY api/app ./app
COPY --chmod=755 api/docker-entrypoint.sh ./
COPY data/sealed /data/sealed
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status != 200)"]
ENTRYPOINT ["./docker-entrypoint.sh"]
