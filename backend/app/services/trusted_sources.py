"""Certified data sources YWP OS is allowed to pull research from.

Only these sources may auto-verify Strict Mode research fields. Random blogs,
unauthenticated scrape targets, and sportsbook HTML pages are not trusted.
"""

from __future__ import annotations

from typing import Any, Literal

SourceTier = Literal["primary", "secondary", "market", "reference"]
SourceCategory = Literal[
    "schedule",
    "form",
    "lineups",
    "injuries",
    "weather",
    "umpires",
    "park",
    "bullpen",
    "market_price",
    "market_movement",
    "motivation",
    "model",
]

TRUSTED_SOURCES: list[dict[str, Any]] = [
    {
        "id": "mlb_stats_api",
        "name": "MLB Stats API",
        "tier": "primary",
        "base_url": "https://statsapi.mlb.com",
        "categories": [
            "schedule",
            "form",
            "lineups",
            "injuries",
            "weather",
            "umpires",
            "park",
            "bullpen",
            "motivation",
        ],
        "auth": "none",
        "notes": "Official MLB public Stats API. Primary baseball facts only.",
    },
    {
        "id": "mlb_gameday",
        "name": "MLB.com Gameday",
        "tier": "reference",
        "base_url": "https://www.mlb.com/gameday",
        "categories": ["schedule", "lineups", "umpires", "weather"],
        "auth": "none",
        "notes": "Human-readable official game page linked from candidates.",
    },
    {
        "id": "the_odds_api",
        "name": "The Odds API",
        "tier": "market",
        "base_url": "https://api.the-odds-api.com",
        "categories": ["market_price", "market_movement"],
        "auth": "ODDS_API_KEY",
        "notes": "Certified sportsbook prices and multi-book consensus only.",
    },
    {
        "id": "open_meteo",
        "name": "Open-Meteo",
        "tier": "secondary",
        "base_url": "https://api.open-meteo.com",
        "categories": ["weather"],
        "auth": "none",
        "notes": "Backup weather when MLB weather is not yet posted.",
    },
    {
        "id": "ywp_mlb_model",
        "name": "YWP MLB Independent Model",
        "tier": "primary",
        "base_url": "internal://mlb_model",
        "categories": ["model"],
        "auth": "none",
        "notes": "Internal projection from official MLB facts. Never uses book price.",
    },
]


def trusted_sources_manifest() -> dict[str, Any]:
    return {
        "protocol": "YWP Trusted Source Research Protocol",
        "version": "2026.09.03-ts1",
        "rule": (
            "Strict Mode may auto-verify a research field only when a trusted source "
            "in that category returned confirmed data. Untrusted pages cannot clear gaps."
        ),
        "sources": TRUSTED_SOURCES,
        "category_owners": {
            category: [source["id"] for source in TRUSTED_SOURCES if category in source["categories"]]
            for category in sorted({cat for source in TRUSTED_SOURCES for cat in source["categories"]})
        },
    }


def sources_for(category: SourceCategory) -> list[dict[str, Any]]:
    return [source for source in TRUSTED_SOURCES if category in source["categories"]]
