"""Process-local single-flight + short TTL cache for expensive shared work.

When two phones open the app at once, identical slate/odds pulls used to each
fan out their own Odds/MLB HTTP storms on a single Render worker — classic 502
fuel. Callers share one in-flight Future per key so concurrent users wait on
the same result instead of doubling outbound load.
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from concurrent.futures import Future
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_lock = threading.Lock()
_inflight: dict[str, Future] = {}
_cache: dict[str, tuple[float, object]] = {}


def single_flight(
    key: str,
    fn: Callable[[], T],
    *,
    ttl_seconds: float = 0.0,
    copy_result: bool = True,
) -> T:
    """Run ``fn`` once per key; concurrent waiters share the same Future.

    If ``ttl_seconds`` > 0, successful results are reused until they expire.
    """
    now = time.monotonic()
    with _lock:
        if ttl_seconds > 0:
            cached = _cache.get(key)
            if cached is not None:
                fetched_at, value = cached
                if now - fetched_at < ttl_seconds:
                    return copy.deepcopy(value) if copy_result else value  # type: ignore[return-value]

        existing = _inflight.get(key)
        if existing is not None:
            leader = False
            future: Future = existing
        else:
            leader = True
            future = Future()
            _inflight[key] = future

    if not leader:
        logger.debug("single-flight join key=%s", key)
        result = future.result()
        return copy.deepcopy(result) if copy_result else result

    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 — propagate to all waiters
        future.set_exception(exc)
        with _lock:
            _inflight.pop(key, None)
        raise

    future.set_result(result)
    with _lock:
        if ttl_seconds > 0:
            _cache[key] = (time.monotonic(), result)
        _inflight.pop(key, None)
    return copy.deepcopy(result) if copy_result else result


def clear_single_flight_cache(prefix: str | None = None) -> None:
    """Test helper — drop cached entries (optionally by key prefix)."""
    with _lock:
        if prefix is None:
            _cache.clear()
            return
        for key in [item for item in _cache if item.startswith(prefix)]:
            _cache.pop(key, None)
