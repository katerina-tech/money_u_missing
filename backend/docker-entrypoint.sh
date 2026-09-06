#!/bin/sh
# Container entrypoint.
#
# Migrations run before the server starts, in the app container rather than as a
# separate release step. That is the right trade for a single-instance
# deployment: the schema can never be behind the code. It would be the wrong
# trade at multiple replicas, where concurrent migrations race - the note is
# here so that decision is revisited rather than inherited.
set -eu

echo '{"event":"startup","message":"running database migrations"}'
alembic upgrade head

# Idempotent: loads legal facts, ingests the knowledge corpus, registers
# sources. Re-running changes nothing.
echo '{"event":"startup","message":"seeding reference data"}'
python -m scripts.seed || echo '{"event":"startup","message":"seed skipped or partially failed"}'

echo '{"event":"startup","message":"starting api"}'
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips='*' \
    --no-access-log
