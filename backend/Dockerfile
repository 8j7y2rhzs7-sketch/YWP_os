FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts
RUN pip install --upgrade pip && pip install .

COPY alembic.ini ./
COPY migrations ./migrations

EXPOSE 8000
# Keep a single worker on the 512MB instance — a second worker OOMs the box.
# Concurrent phones are handled by single-flight caches in-app.
# Set UVICORN_WORKERS=2 only after upgrading RAM, and keep DB pool_size low.
# app.boot listens even when Postgres is suspended, then retries migrations.
ENV PGCONNECT_TIMEOUT=8
CMD ["python", "-m", "app.boot"]
