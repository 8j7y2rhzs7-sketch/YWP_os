from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class HiveSettings:
    enabled: bool = True
    anon_secret: str = ""
    min_sample: int = 40
    # Eligible settled samples needed before Hive is treated as fully matured.
    optimal_sample: int = 200
    max_probability_shift: float = 0.035
    require_verified_outcome: bool = True
    require_consent: bool = False
    release_version: str = "hive-1"


def get_hive_settings() -> HiveSettings:
    return HiveSettings(
        enabled=_bool("YWP_HIVE_ENABLED", True),
        anon_secret=os.getenv("YWP_HIVE_ANON_SECRET", "") or os.getenv("YWP_JWT_SECRET", ""),
        min_sample=int(os.getenv("YWP_HIVE_MIN_SAMPLE", "40")),
        optimal_sample=int(os.getenv("YWP_HIVE_OPTIMAL_SAMPLE", "200")),
        max_probability_shift=float(os.getenv("YWP_HIVE_MAX_PROBABILITY_SHIFT", "0.035")),
        require_verified_outcome=_bool("YWP_HIVE_REQUIRE_VERIFIED_OUTCOME", True),
        # Product-owned recommendation snapshots do not require a separate user
        # consent toggle; keep the env switch for optional future policy changes.
        require_consent=_bool("YWP_HIVE_REQUIRE_CONSENT", False),
        release_version=os.getenv("YWP_HIVE_RELEASE_VERSION", "hive-1"),
    )


class _SettingsProxy:
    """Read env on each access so tests can monkeypatch before calls."""

    def __getattr__(self, name: str):
        return getattr(get_hive_settings(), name)


settings = _SettingsProxy()
