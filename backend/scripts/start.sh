#!/bin/sh
# Open the web port even when the free database is still waking up.
# A sleeping Postgres host used to block this script forever, so Render held
# every request and never returned a response.
set -u

attempts=0
max_attempts=4
until alembic upgrade head; do
  attempts=$((attempts + 1))
  if [ "$attempts" -ge "$max_attempts" ]; then
    echo "Database migrations did not finish. Starting the API anyway."
    break
  fi
  echo "Database not ready (attempt ${attempts}/${max_attempts}). Waiting 5s."
  sleep 5
done

python -m app.seed || echo "Owner setup did not finish. Starting the API anyway."

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${UVICORN_WORKERS:-1}" \
  --timeout-keep-alive 30
