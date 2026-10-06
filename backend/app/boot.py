"""Process entrypoint for the Render container.

Migrations run before the API listens when Postgres is reachable. When the
database host does not resolve (a suspended free instance), the process still
listens so /api/v1/health can say so, and a background retry applies
migrations after the database comes back.
"""

from __future__ import annotations

import os
import sys

from app.services.database_guard import (
    enforce_production_secrets,
    last_prepare_failure,
    try_prepare_database,
)


def main() -> None:
    enforce_production_secrets()
    os.environ.setdefault("PGCONNECT_TIMEOUT", "8")
    ready = try_prepare_database()
    if not ready and last_prepare_failure() == "unavailable":
        os.environ["YWP_DB_BOOT_PENDING"] = "1"
        print(
            "Database unavailable at boot. API will listen and retry migrations.",
            flush=True,
        )
    elif not ready:
        os.environ["YWP_DB_BOOT_FAILED"] = "1"
        print(
            "Database migration failed. API will listen and /api/v1/health will say so.",
            flush=True,
        )
    port = os.environ.get("PORT", "8000")
    workers = os.environ.get("UVICORN_WORKERS", "1")
    os.execvp(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
            "--workers",
            workers,
            "--timeout-keep-alive",
            "30",
        ],
    )


if __name__ == "__main__":
    main()
