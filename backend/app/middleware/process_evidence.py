"""Record every API process movement for Ops Heal evidence collection."""

from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.ops_evidence import record_app_movement, should_record_movement

logger = logging.getLogger(__name__)


class ProcessEvidenceMiddleware(BaseHTTPMiddleware):
    """Forward-collect app movements across all API processes."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if settings.env == "test":
            return await call_next(request)

        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000.0
        path = request.url.path
        method = request.method
        status_code = int(response.status_code)

        if not should_record_movement(method=method, path=path, status_code=status_code):
            return response

        db = SessionLocal()
        try:
            record_app_movement(
                db,
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
            )
            db.commit()
        except Exception:  # noqa: BLE001 — never break requests for telemetry
            logger.exception("Failed to record process movement for %s %s", method, path)
            db.rollback()
        finally:
            db.close()
        return response
