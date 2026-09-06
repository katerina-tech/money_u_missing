# Backend image.
#
# Two stages: resolve dependencies from the committed lockfile, then copy a
# lean runtime. The lockfile is the point - `uv sync --frozen` fails rather
# than silently resolving something different from what the tests ran against,
# which is the whole reason the lock is committed.

FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.24 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so a source change does not invalidate the layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra postgres

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
COPY evals ./evals
COPY data/knowledge ./data/knowledge
COPY data/legal_facts.json data/demo_opportunities.json data/curated_opportunities.json ./data/


FROM python:3.12-slim-bookworm AS runtime

# curl is used by the container platform's health check and by the entrypoint.
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MYM_ENVIRONMENT=production \
    MYM_LOG_FORMAT=json

# Writable location for uploads and, in a non-Postgres deployment, the SQLite
# file. Owned by the unprivileged user because the process does not run as root.
RUN mkdir -p /app/data/uploads && chown -R app:app /app/data

COPY --chown=app:app docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8000}/api/health" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
