from __future__ import annotations

from app.core.config import Settings
from app.services.odds_provider import (
    extract_best_odds,
    key_diagnostics,
    match_game_to_event,
)
from app.services import odds_provider as odds_mod


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


def test_key_diagnostics_never_echoes_secret() -> None:
    info = key_diagnostics("03c0e41ace40a1a7303f182dfa09706d")
    assert info["fingerprint"] == "03c0…706d"
    assert info["length"] == 32
    assert info["looks_like_hex"] is True
    dumped = str(info)
    assert "03c0e41ace40a1a7303f182dfa09706d" not in dumped


def test_lookalike_hex_key_is_normalized(monkeypatch) -> None:
    class _Fake:
        odds_api_key = "03c0e4lace40ala7303f182dfa09706d"

    monkeypatch.setattr(odds_mod, "settings", _Fake())
    assert odds_mod._normalized_key() == "03c0e41ace40a1a7303f182dfa09706d"
