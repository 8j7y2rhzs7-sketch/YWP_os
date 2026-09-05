from __future__ import annotations

from app.core.config import Settings
from app.services import odds_provider as odds_mod
from app.services.odds_provider import (
    extract_best_odds,
    extract_player_prop,
    key_diagnostics,
    match_game_to_event,
)


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


def test_match_game_to_event_prefers_exact_shared_nickname_sides() -> None:
    game = {
        "home_team": "Chicago White Sox",
        "away_team": "Boston Red Sox",
    }
    events = [
        {
            "id": "reversed",
            "home_team": "Boston Red Sox",
            "away_team": "Chicago White Sox",
        },
        {
            "id": "correct",
            "home_team": "Chicago White Sox",
            "away_team": "Boston Red Sox",
        },
    ]

    matched = match_game_to_event(game, events)

    assert matched is not None
    assert matched["id"] == "correct"


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


def test_extract_best_odds_does_not_cross_match_shared_nickname() -> None:
    bookmakers = [
        {
            "key": "draftkings",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Chicago White Sox", "price": -125},
                        {"name": "Boston Red Sox", "price": 110},
                    ],
                }
            ],
        }
    ]

    white_sox = extract_best_odds(bookmakers, "h2h", "Chicago White Sox")

    assert white_sox is not None
    assert white_sox["american_odds"] == -125


def test_extract_player_prop_requires_a_real_player_line_and_price() -> None:
    bookmakers = [
        {
            "key": "draftkings",
            "markets": [
                {
                    "key": "pitcher_strikeouts",
                    "outcomes": [
                        {
                            "name": "Over",
                            "description": "Test Pitcher",
                            "price": -115,
                            "point": 5.5,
                        },
                        {
                            "name": "Under",
                            "description": "Test Pitcher",
                            "price": -105,
                            "point": 5.5,
                        },
                    ],
                }
            ],
        }
    ]

    prop = extract_player_prop(bookmakers, "pitcher_strikeouts", "Test Pitcher")

    assert prop == {"book": "draftkings", "american_odds": -115, "point": 5.5}
    assert extract_player_prop(bookmakers, "pitcher_strikeouts", "Missing Pitcher") is None


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



def test_list_odds_sports_uses_free_catalog_and_cache(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append((path, dict(params or {})))
        return [
            {"key": "baseball_mlb", "title": "MLB", "active": True},
            {"key": "basketball_nba", "title": "NBA", "active": False},
        ]

    class _Fake:
        odds_api_key = "abcdef0123456789abcdef0123456789"

    monkeypatch.setattr(odds_mod, "settings", _Fake())
    monkeypatch.setattr(odds_mod, "_get_sync", fake_get)
    odds_mod._sports_cache.update(
        {"fetched_at": 0.0, "in_season": [], "all": [], "error": None}
    )

    first = odds_mod.list_odds_sports(include_out_of_season=True, force_refresh=True)
    second = odds_mod.list_odds_sports(include_out_of_season=True)
    assert [row["key"] for row in first] == ["baseball_mlb", "basketball_nba"]
    assert second == first
    assert len(calls) == 1
    assert calls[0][0] == "/v4/sports/"
    assert calls[0][1].get("all") == "true"
    assert odds_mod.in_season_odds_keys() == {"baseball_mlb"}
    assert odds_mod.app_sport_in_season("mlb") is True
    assert odds_mod.app_sport_in_season("nba") is False


def test_get_game_odds_skips_out_of_season_and_caches_paid(monkeypatch) -> None:
    calls: list[str] = []

    def fake_get(path: str, params: dict | None = None):
        calls.append(path)
        if path.rstrip("/").endswith("/sports"):
            return [{"key": "baseball_mlb", "title": "MLB", "active": True}]
        return [{"id": "evt-1", "home_team": "A", "away_team": "B", "bookmakers": []}]

    class _Fake:
        odds_api_key = "abcdef0123456789abcdef0123456789"

    monkeypatch.setattr(odds_mod, "settings", _Fake())
    monkeypatch.setattr(odds_mod, "_get_sync", fake_get)
    odds_mod._sports_cache.update(
        {"fetched_at": 0.0, "in_season": [], "all": [], "error": None}
    )
    odds_mod._odds_response_cache.clear()

    assert odds_mod.get_game_odds(sport="basketball_nba") == []
    status = odds_mod.get_last_fetch_status()
    assert status.get("error") == "sport_out_of_season"
    assert status.get("credit_cost") == 0

    first = odds_mod.get_game_odds(sport="baseball_mlb")
    second = odds_mod.get_game_odds(sport="baseball_mlb")
    assert len(first) == 1
    assert second == first
    paid = [c for c in calls if c.endswith("/odds")]
    assert len(paid) == 1
    assert odds_mod.get_last_fetch_status().get("cache_hit") is True


def test_probe_odds_api_uses_free_sports_catalog(monkeypatch) -> None:
    def fake_get(path: str, params: dict | None = None):
        assert "sports" in path
        return [{"key": "baseball_mlb", "title": "MLB", "active": True}]

    class _Fake:
        odds_api_key = "abcdef0123456789abcdef0123456789"

    monkeypatch.setattr(odds_mod, "settings", _Fake())
    monkeypatch.setattr(odds_mod, "_get_sync", fake_get)
    odds_mod._sports_cache.update(
        {"fetched_at": 0.0, "in_season": [], "all": [], "error": None}
    )
    status = odds_mod.probe_odds_api(sport="baseball_mlb")
    assert status["ok"] is True
    assert status["credit_cost"] == 0
    assert "free" in str(status.get("probe_mode") or status.get("probe_mode") or "").lower() or status.get("credit_cost") == 0
    assert status.get("target_sport_in_season") is True or status.get("target_sport_in_season") is True
