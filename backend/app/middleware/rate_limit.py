"""
Simple in-memory rate limiter for auth endpoints.
Uses a sliding window per IP. Production should use Redis,
but this works without any infrastructure.
"""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Callable

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

RATE_LIMIT_PATHS = {
    "/api/v1/auth/login": (10, 60),
    "/api/v1/auth/register": (5, 60),
    "/api/v1/auth/refresh": (20, 60),
}

_lock = Lock()
_buckets: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_rate_limited(key: str, max_requests: int, window_seconds: int) -> bool:
    now = time.monotonic()
    with _lock:
        hits = _buckets[key]
        cutoff = now - window_seconds
        _buckets[key] = [t for t in hits if t > cutoff]
        if len(_buckets[key]) >= max_requests:
            return True
        _buckets[key].append(now)
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path.rstrip("/")
        if settings.env == "test":
            return await call_next(request)
        limit = RATE_LIMIT_PATHS.get(path)
        if limit and request.method == "POST":
            max_req, window = limit
            ip = _client_ip(request)
            key = f"{ip}:{path}"
            if _is_rate_limited(key, max_req, window):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many requests. Please try again later."},
                    headers={"Retry-After": str(window)},
                )
        return await call_next(request)
