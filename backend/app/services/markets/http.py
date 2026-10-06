"""Small public HTTP helper: timeout, retry, and a polite request pace."""

from __future__ import annotations

import contextlib
import time
from datetime import UTC, datetime

import httpx

from app.core.config import settings
from app.services.markets.adapter import AdapterError


class RequestPace:
    """Minimum gap between calls so a scan stays under public rate limits."""

    def __init__(self, min_interval: float) -> None:
        self.min_interval = max(0.0, float(min_interval))
        self._next = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        now = time.monotonic()
        delay = self._next - now
        if delay > 0:
            time.sleep(delay)
            now = time.monotonic()
        self._next = now + self.min_interval


class PublicHttp:
    def __init__(
        self,
        venue: str,
        *,
        client: httpx.Client | None = None,
        min_interval: float = 0.12,
        retries: int = 3,
        timeout: float = 10.0,
    ) -> None:
        self.venue = venue
        self.retries = retries
        self.pace = RequestPace(min_interval)
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(timeout, connect=5.0),
            headers={
                "User-Agent": f"YWP-OS-markets/{settings.app_version} (read-only)",
                "Accept": "application/json",
            },
        )
        self.last_error: str | None = None
        self.last_latency_ms: float | None = None
        self.last_success_at: datetime | None = None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def get_json(
        self, url: str, params: dict[str, object] | None = None
    ) -> dict[str, object] | list:
        last_message = "request failed"
        last_status: int | None = None
        for attempt in range(self.retries):
            self.pace.wait()
            started = time.perf_counter()
            try:
                response = self.client.get(url, params=params)
            except httpx.HTTPError as exc:
                last_message = str(exc)
                self.last_error = last_message
                if attempt + 1 >= self.retries:
                    raise AdapterError(self.venue, last_message) from exc
                self._backoff(attempt)
                continue
            self.last_latency_ms = (time.perf_counter() - started) * 1000
            if response.status_code == 429 or response.status_code >= 500:
                last_status = response.status_code
                last_message = f"HTTP {response.status_code}"
                self.last_error = last_message
                if attempt + 1 >= self.retries:
                    raise AdapterError(self.venue, last_message, status_code=response.status_code)
                self._backoff(attempt, response.headers.get("Retry-After"))
                continue
            if response.status_code >= 400:
                self.last_error = f"HTTP {response.status_code}"
                raise AdapterError(
                    self.venue,
                    f"HTTP {response.status_code} from {url}",
                    status_code=response.status_code,
                )
            self.last_error = None
            self.last_success_at = datetime.now(UTC)
            payload = response.json()
            if isinstance(payload, dict | list):
                return payload
            raise AdapterError(self.venue, "Response was not JSON")
        raise AdapterError(self.venue, last_message, status_code=last_status)

    def _backoff(self, attempt: int, retry_after: str | None = None) -> None:
        # Tests inject a zero pace. Don't stall the suite on a fake 429.
        if self.pace.min_interval <= 0:
            return
        delay = 0.25 * (2**attempt)
        if retry_after:
            with contextlib.suppress(ValueError):
                delay = max(delay, float(retry_after))
        time.sleep(min(delay, 5.0))
