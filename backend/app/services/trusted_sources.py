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

ALL_SPORTS = [
    "mlb",
    "wnba",
    "nba",
    "nfl",
    "ncaaf",
    "ncaab",
    "nhl",
    "soccer",
    "mls",
    "epl",
    "kbo",
]

TRUSTED_SOURCES: list[dict[str, Any]] = [
    {
        "id": "mlb_stats_api",
        "name": "MLB Stats API",
        "tier": "primary",
        "sports": ["mlb"],
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
        "sports": ["mlb"],
        "base_url": "https://www.mlb.com/gameday",
        "categories": ["schedule", "lineups", "umpires", "weather"],
        "auth": "none",
        "notes": "Human-readable official game page linked from candidates.",
    },
    {
        "id": "espn_site_api",
        "name": "ESPN Site API",
        "tier": "secondary",
        "sports": [
            "wnba",
            "nba",
            "nfl",
            "ncaaf",
            "ncaab",
            "nhl",
            "soccer",
            "mls",
            "epl",
            "kbo",
        ],
        "base_url": "https://site.web.api.espn.com/apis/site/v2/sports",
        "categories": [
            "schedule",
            "form",
            "lineups",
            "injuries",
            "park",
            "motivation",
            "weather",
        ],
        "auth": "none",
        "notes": (
            "Structured ESPN Site JSON API (not HTML scrape). Secondary fact source — "
            "Render/host egress may 403; cascade continues with Odds-priced plays."
        ),
    },
    {
        "id": "nhl_web_api",
        "name": "NHL Web API",
        "tier": "primary",
        "sports": ["nhl"],
        "base_url": "https://api-web.nhle.com/v1",
        "categories": ["schedule", "form", "park"],
        "auth": "none",
        "notes": "Official NHL public Web API for schedule and club form.",
    },
    {
        "id": "the_odds_api",
        "name": "The Odds API",
        "tier": "market",
        "sports": ALL_SPORTS,
        "base_url": "https://api.the-odds-api.com",
        "categories": ["market_price", "market_movement", "schedule"],
        "auth": "ODDS_API_KEY",
        "notes": (
            "Certified sportsbook prices and the schedule backbone for non-MLB slates. "
            "Priced plays are shown even when fact sources are incomplete (PARTIAL)."
        ),
    },
    {
        "id": "open_meteo",
        "name": "Open-Meteo",
        "tier": "secondary",
        "sports": ["mlb", "nfl", "ncaaf", "soccer", "mls", "epl", "kbo"],
        "base_url": "https://api.open-meteo.com",
        "categories": ["weather"],
        "auth": "none",
        "notes": "Backup weather for outdoor sports when primary weather is missing.",
    },
    {
        "id": "college_football_data",
        "name": "CollegeFootballData (CFBD)",
        "tier": "secondary",
        "sports": ["ncaaf"],
        "base_url": "https://api.collegefootballdata.com",
        "categories": ["schedule", "form", "park", "weather", "motivation"],
        "auth": "CFBD_API_KEY",
        "notes": (
            "Free-tier JSON API for NCAA football games, teams, and form. "
            "NCAAF schedule/form backup when ESPN matching is thin. Optional Bearer key."
        ),
    },
    {
        "id": "balldontlie",
        "name": "BallDontLie NBA API",
        "tier": "secondary",
        "sports": ["nba"],
        "base_url": "https://api.balldontlie.io",
        "categories": ["schedule", "form"],
        "auth": "none",
        "notes": (
            "Validated free NBA JSON API for games/teams/stats. Registered for cascade use; "
            "ESPN remains primary until wired live."
        ),
    },
    {
        "id": "football_data_org",
        "name": "Football-Data.org",
        "tier": "secondary",
        "sports": ["soccer", "epl", "mls"],
        "base_url": "https://api.football-data.org/v4",
        "categories": ["schedule", "form"],
        "auth": "FOOTBALL_DATA_API_KEY",
        "notes": (
            "Free football (soccer) fixtures/results JSON API. Registered as secondary "
            "schedule/form source behind ESPN for soccer leagues."
        ),
    },
    {
        "id": "nba_stats_cdn",
        "name": "NBA Stats CDN",
        "tier": "reference",
        "sports": ["nba"],
        "base_url": "https://stats.nba.com",
        "categories": ["schedule", "form", "lineups"],
        "auth": "none",
        "notes": (
            "Official NBA stats endpoints (CDN). Reference/secondary; cloud egress often "
            "blocks these hosts, so ESPN remains the live cascade path."
        ),
    },
    {
        "id": "ncaa_data_api",
        "name": "NCAA Data API",
        "tier": "secondary",
        "sports": ["ncaaf", "ncaab"],
        "base_url": "https://data.ncaa.com",
        "categories": ["schedule"],
        "auth": "none",
        "notes": (
            "NCAA Casablanca FBS scoreboard JSON (no auth). Live-validated schedule "
            "tertiary for NCAAF after ESPN + CFBD. Does not price markets."
        ),
    },
    {
        "id": "nws_weather_gov",
        "name": "National Weather Service (api.weather.gov)",
        "tier": "secondary",
        "sports": ["mlb", "nfl", "ncaaf"],
        "base_url": "https://api.weather.gov",
        "categories": ["weather"],
        "auth": "none",
        "notes": (
            "Free US government weather JSON. Live-validated backup to Open-Meteo "
            "for outdoor US venues (NCAAF/NFL/MLB)."
        ),
    },
    {
        "id": "ywp_mlb_model",
        "name": "YWP MLB Independent Model",
        "tier": "primary",
        "sports": ["mlb"],
        "base_url": "internal://mlb_model",
        "categories": ["model"],
        "auth": "none",
        "notes": "Internal projection from official MLB facts. Never uses book price.",
    },
    {
        "id": "ywp_sport_model",
        "name": "YWP Multi-Sport Independent Model",
        "tier": "primary",
        "sports": [
            "wnba",
            "nba",
            "nfl",
            "ncaaf",
            "ncaab",
            "nhl",
            "soccer",
            "mls",
            "epl",
            "kbo",
        ],
        "base_url": "internal://sport_model",
        "categories": ["model"],
        "auth": "none",
        "notes": (
            "Internal projection from cascaded form/injury/venue facts. "
            "Never uses sportsbook implied probability as the model output."
        ),
    },
]


def trusted_sources_manifest(sport: str | None = None) -> dict[str, Any]:
    sources = TRUSTED_SOURCES
    if sport:
        sport_l = sport.lower()
        sources = [
            source
            for source in TRUSTED_SOURCES
            if sport_l in [item.lower() for item in source.get("sports", ALL_SPORTS)]
        ]
    return {
        "protocol": "YWP Trusted Source Research Protocol",
        "version": "2026.09.12-ts4",
        "rule": (
            "Strict Mode may auto-verify a research field only when a trusted source "
            "in that category returned confirmed data. Untrusted pages cannot clear gaps."
        ),
        "sports": ALL_SPORTS,
        "sources": sources,
        "category_owners": {
            category: [source["id"] for source in sources if category in source["categories"]]
            for category in sorted({cat for source in sources for cat in source["categories"]})
        },
    }


def sources_for(category: SourceCategory, sport: str | None = None) -> list[dict[str, Any]]:
    rows = [source for source in TRUSTED_SOURCES if category in source["categories"]]
    if sport:
        sport_l = sport.lower()
        rows = [
            source
            for source in rows
            if sport_l in [item.lower() for item in source.get("sports", ALL_SPORTS)]
        ]
    return rows
