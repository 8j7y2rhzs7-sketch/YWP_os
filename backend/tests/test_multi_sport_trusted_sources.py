from __future__ import annotations

import httpx

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.services import espn_provider, sport_model, sport_research
from app.services.trusted_sources import sources_for, trusted_sources_manifest


def test_trusted_sources_include_multi_sport_pool() -> None:
    manifest = trusted_sources_manifest()
    ids = {item["id"] for item in manifest["sources"]}
    assert "espn_site_api" in ids
    assert "nhl_web_api" in ids
    assert "mlb_stats_api" in ids
    assert "the_odds_api" in ids
    assert "ywp_sport_model" in ids
    nfl = trusted_sources_manifest("nfl")
    nfl_ids = {item["id"] for item in nfl["sources"]}
    assert "espn_site_api" in nfl_ids
    assert "mlb_stats_api" not in nfl_ids
    assert sources_for("form", "wnba")
    assert any(item["id"] == "espn_site_api" for item in sources_for("injuries", "nba"))
    assert any(item["id"] == "nhl_web_api" for item in sources_for("schedule", "nhl"))
    assert any(item["id"] == "the_odds_api" for item in sources_for("schedule", "soccer"))


def test_sport_model_prefers_form_not_coin_flip() -> None:
    home = {
        "verified": True,
        "l5": {"win_pct": 0.8, "avg_for": 110, "avg_against": 100},
        "l10": {"win_pct": 0.7, "avg_for": 108, "avg_against": 102, "totals": [210] * 10},
    }
    away = {
        "verified": True,
        "l5": {"win_pct": 0.3, "avg_for": 98, "avg_against": 112},
        "l10": {"win_pct": 0.35, "avg_for": 99, "avg_against": 110, "totals": [205] * 10},
    }
    projection = sport_model.project_matchup(
        home_form=home,
        away_form=away,
        market_type="moneyline",
        selection="Home Club ML",
        is_home_selection=True,
    )
    assert projection.win_probability > 0.55
    assert projection.expected_total > 0
    total = sport_model.project_matchup(
        home_form=home,
        away_form=away,
        market_type="game_total_over",
        selection="Over 200.5",
        line=200.5,
    )
    assert total.win_probability >= 0.5


def test_build_verified_candidate_stays_partial_without_lineups() -> None:
    research = {
        "espn_game": {
            "home_team": "Home Club",
            "away_team": "Away Club",
            "venue": "Arena",
            "source_url": "https://example.test",
        },
        "home_form": {
            "verified": True,
            "l10": {"win_pct": 0.6, "avg_for": 100, "avg_against": 95},
            "l5": {"win_pct": 0.6},
            "source_url": "https://example.test/home",
        },
        "away_form": {
            "verified": True,
            "l10": {"win_pct": 0.4, "avg_for": 95, "avg_against": 100},
            "l5": {"win_pct": 0.4},
            "source_url": "https://example.test/away",
        },
        "injuries": {"verified": True, "home_out": 0, "away_out": 1},
        "flags": {
            "schedule_verified": True,
            "current_form_verified": True,
            "l5_l10_verified": True,
            "lineup_confirmed": False,
            "injuries_verified": True,
            "weather_verified": True,
            "starter_confirmed": False,
            "motivation_rotation_verified": False,
            "home_away_verified": True,
            "market_movement_verified": True,
            "sport_specific_sweep_complete": False,
        },
        "source_status": {
            "schedule": "confirmed",
            "market": "confirmed",
            "current_form": "confirmed",
            "injuries": "confirmed",
            "starter": "probable",
            "lineup": "probable",
            "weather": "confirmed",
        },
        "source_urls": ["https://example.test"],
    }
    candidate = sport_research.build_verified_candidate(
        sport="wnba",
        league="WNBA",
        candidate_id="wnba-ml-home-1",
        event_id="evt",
        event_name="Away Club @ Home Club",
        home_team="Home Club",
        away_team="Away Club",
        start_time=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        market_type="moneyline",
        selection="Home Club ML",
        odds=-130,
        line=None,
        thesis_key="thesis-home-ml",
        script_key="script-home-control",
        reason_codes=["CURRENT_FORM"],
        reasoning=["test"],
        research=research,
    )
    assert candidate.probability_source == "model"
    assert candidate.lineup_confirmed is False
    assert candidate.sport_specific_sweep_complete is False
    from app.services.readiness import candidate_readiness, candidate_verification_gaps

    assert candidate_readiness(candidate) == "PARTIAL"
    gaps = candidate_verification_gaps(candidate)
    assert any("lineup" in gap.lower() for gap in gaps)
    assert any("sweep" in gap.lower() or "starter" in gap.lower() for gap in gaps)


def test_injuries_require_both_teams_matched() -> None:
    feed = {
        "verified": True,
        "by_team": {"Home Club": [{"status": "Out", "name": "Star"}]},
    }
    both = espn_provider.injuries_for_teams(feed, "Home Club", "Away Club")
    assert both["verified"] is False
    feed["by_team"]["Away Club"] = []
    both = espn_provider.injuries_for_teams(feed, "Home Club", "Away Club")
    assert both["verified"] is True
    assert both["home_out"] == 1


def test_espn_form_parses_completed_games(monkeypatch) -> None:
    monkeypatch.setattr(
        espn_provider,
        "_get",
        lambda *args, **kwargs: {
            "events": [
                {
                    "date": "2026-08-20T00:00:00Z",
                    "competitions": [
                        {
                            "status": {"type": {"completed": True, "name": "STATUS_FINAL"}},
                            "competitors": [
                                {
                                    "homeAway": "home",
                                    "winner": True,
                                    "score": {"value": 100},
                                    "team": {"id": "10", "displayName": "Home"},
                                },
                                {
                                    "homeAway": "away",
                                    "winner": False,
                                    "score": {"value": 90},
                                    "team": {"id": "20", "displayName": "Away"},
                                },
                            ],
                        }
                    ],
                }
            ]
            * 6
        },
    )
    form = espn_provider.get_team_recent_form("wnba", "10", date(2026, 9, 3))
    assert form["verified"] is True
    assert form["l10"]["games"] >= 5
    assert form["l10"]["wins"] == form["l10"]["games"]


def test_espn_get_falls_back_when_primary_host_403(monkeypatch) -> None:
    espn_provider._CACHE.clear()
    calls: list[str] = []

    class _Resp:
        def __init__(self, code: int, payload: dict | None = None):
            self.status_code = code
            self._payload = payload or {}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "denied",
                    request=httpx.Request("GET", "https://example.com"),
                    response=httpx.Response(self.status_code),
                )

        def json(self) -> dict:
            return self._payload

    def fake_get(url: str, **kwargs):
        calls.append(url)
        if "site.web.api.espn.com" in url:
            return _Resp(403)
        return _Resp(200, {"events": [{"id": "1"}]})

    import httpx
    monkeypatch.setattr(espn_provider.httpx, "get", fake_get)
    data = espn_provider._get(f"{espn_provider.SOURCE_API}/football/nfl/scoreboard")
    assert data["events"][0]["id"] == "1"
    assert any("site.web.api.espn.com" in u for u in calls)
    assert any("site.api.espn.com" in u for u in calls)
