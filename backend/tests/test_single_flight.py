from __future__ import annotations

import threading
import time

from app.services.single_flight import clear_single_flight_cache, single_flight


def test_single_flight_coalesces_concurrent_callers() -> None:
    clear_single_flight_cache()
    calls = {"n": 0}
    barrier = threading.Barrier(4)
    results: list[int] = []
    lock = threading.Lock()

    def work() -> int:
        calls["n"] += 1
        time.sleep(0.05)
        return 42

    def runner() -> None:
        barrier.wait(timeout=2)
        value = single_flight("coalesce-test", work, ttl_seconds=1.0)
        with lock:
            results.append(value)

    threads = [threading.Thread(target=runner) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)

    assert results == [42, 42, 42, 42]
    assert calls["n"] == 1


def test_single_flight_ttl_reuses_result() -> None:
    clear_single_flight_cache()
    calls = {"n": 0}

    def work() -> str:
        calls["n"] += 1
        return "cached"

    assert single_flight("ttl-test", work, ttl_seconds=2.0) == "cached"
    assert single_flight("ttl-test", work, ttl_seconds=2.0) == "cached"
    assert calls["n"] == 1
