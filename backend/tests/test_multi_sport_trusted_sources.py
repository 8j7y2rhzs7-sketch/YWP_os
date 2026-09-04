from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.services import espn_provider, sport_model, sport_research
from app.services.trusted_sources import sources_for, trusted_sources_manifest


def test_trusted_sources_include_multi_sport_pool() -> None:
    manifest = trusted_sources_manifest()
    ids = {item["id"] for item in manifest["sources"]}
    assert "mlb_stats_api" in ids
    assert "espn_site_api" in ids
    assert "ywp_sport_model" in ids
    assert "the_odds_api" in ids
    nfl = trusted_sources_manifest("nfl")
    nfl_ids = {item["id"] for item in nfl["sources"]}
    assert "espn_site_api" in nfl_ids
    assert "mlb_stats_api" not in nfl_ids
    assert sources_for("form", "wnba")
    assert any(item["id"] == "espn_site_api" for item in sources_for("injuries", "nba"))


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


def test_build_verified_candidate_uses_model_not_market() -> None:
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
            "lineup_confirmed": True,
            "injuries_verified": True,
            "weather_verified": True,
            "starter_confirmed": True,
            "motivation_rotation_verified": True,
            "market_movement_verified": True,
            "sport_specific_sweep_complete": True,
        },
        "source_status": {
            "schedule": "confirmed",
            "market": "confirmed",
            "current_form": "confirmed",
            "injuries": "confirmed",
            "starter": "confirmed",
            "lineup": "confirmed",
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
    assert candidate.schedule_verified is True
    assert candidate.current_form_verified is True
    assert candidate.sport_specific_sweep_complete is True
    assert "DEMO" not in candidate.data_source
    assert candidate.estimated_probability != 0.5 or candidate.data_quality >= 0.55


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
