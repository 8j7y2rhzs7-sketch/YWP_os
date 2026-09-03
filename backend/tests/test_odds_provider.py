from __future__ import annotations

from app.core.config import Settings
from app.services.odds_provider import extract_best_odds, match_game_to_event


def test_empty_odds_secrets_normalize_to_none() -> None:
    for raw in ("", "-", "null", "None", '""', "''", "  -  "):
        settings = Settings(
            _env_file=None,
            YWP_JWT_SECRET="test-secret-that-is-longer-than-thirty-two-bytes",
            ODDS_API_KEY=raw,
        )
        assert settings.odds_api_key is None


def test_quoted_odds_secret_is_stripped() -> None:
    settings = Settings(
        _env_file=None,
        YWP_JWT_SECRET="test-secret-that-is-longer-than-thirty-two-bytes",
        ODDS_API_KEY='"abc123"',
    )
    assert settings.odds_api_key == "abc123"


def test_match_game_to_event_by_nickname() -> None:
    game = {
        "home_team": "Cleveland Guardians",
        "away_team": "Toronto Blue Jays",
    }
    events = [
        {
            "id": "evt-1",
            "home_team": "Cleveland Guardians",
            "away_team": "Toronto Blue Jays",
            "bookmakers": [],
        }
    ]
    matched = match_game_to_event(game, events)
    assert matched is not None
    assert matched["id"] == "evt-1"


def test_extract_best_odds_soft_match() -> None:
    bookmakers = [
        {
            "key": "draftkings",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Cleveland Guardians", "price": -130},
                        {"name": "Toronto Blue Jays", "price": 110},
                    ],
                }
            ],
        }
    ]
    best = extract_best_odds(bookmakers, "h2h", "Cleveland Guardians")
    assert best is not None
    assert best["american_odds"] == -130
