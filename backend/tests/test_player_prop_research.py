from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch

from app.schemas import CandidateInput
from app.services import player_prop_research, readiness
from app.services.decision_engine import decision_engine
from app.schemas import RiskProfile


def _board_prop(**overrides) -> CandidateInput:
    now = datetime(2026, 9, 17, 20, 0, tzinfo=UTC)
    base = dict(
        candidate_id="board-wnba-prop-1",
        event_id="game-1",
        event_name="Connecticut Sun @ Atlanta Dream",
        sport="wnba",
        league="WNBA",
        start_time=now,
        home_team="Atlanta Dream",
        away_team="Connecticut Sun",
        market_type="player_points_over",
        selection="A'ja Wilson Over 22.5 points",
        line=Decimal("22.5"),
        american_odds=-115,
        estimated_probability=0.535,
        probability_source="market_implied",
        variance=0.45,
        data_quality=0.35,
        data_source="THE_ODDS_API_BOARD",
        source_timestamp=now,
        missing_fields=["independent_model_projection"],
        source_status={"market": "confirmed", "schedule": "confirmed"},
        schedule_verified=True,
        market_movement_verified=True,
        reason_codes=["SPORTSBOOK_MENU", "MARKET_IMPLIED"],
        thesis_key="board:wnba:game-1:player_points_over",
        script_key="board:wnba:game-1:player_points_over",
    )
    base.update(overrides)
    return CandidateInput(**base)


def test_enrich_upgrades_market_implied_wnba_prop_to_model() -> None:
    games = [
        {"points": 28, "totalRebounds": 10, "assists": 3, "game_date": f"2026-09-{d:02d}"}
        for d in range(16, 6, -1)
    ]
    candidate = _board_prop()
    with (
        patch.object(player_prop_research.espn_provider, "resolve_team_id", return_value="1"),
        patch.object(
            player_prop_research.espn_provider,
            "resolve_athlete_id",
            return_value={"id": "99", "name": "A'ja Wilson"},
        ),
        patch.object(
            player_prop_research.espn_provider,
            "get_athlete_gamelog",
            return_value={
                "verified": True,
                "games": games,
                "source_url": "https://espn.test/gamelog",
            },
        ),
        patch.object(
            player_prop_research.espn_provider,
            "get_league_injuries",
            return_value={"verified": True, "by_team": {}},
        ),
    ):
        enriched = player_prop_research.enrich_player_prop_candidates(
            [candidate], slate_date=date(2026, 9, 17)
        )[0]

    assert enriched.probability_source == "model"
    assert enriched.data_source == "ESPN_PLAYER_PROP_MODEL"
    assert enriched.estimated_probability > 0.5
    assert "independent_model_projection" not in (enriched.missing_fields or [])
    assert readiness.candidate_readiness(enriched) == "VERIFIED"
    assert readiness.candidate_verification_gaps(enriched) == []

    evaluation = decision_engine.evaluate(enriched, RiskProfile.balanced)
    assert "NO_INDEPENDENT_PROBABILITY" not in evaluation.reason_codes
    assert evaluation.decision in {"PLAY", "LEAN", "WATCH", "SKIP"}


def test_enrich_drops_out_player_and_keeps_unresolved_rows() -> None:
    priced = _board_prop()
    with (
        patch.object(player_prop_research.espn_provider, "resolve_team_id", return_value="1"),
        patch.object(
            player_prop_research.espn_provider,
            "resolve_athlete_id",
            return_value={"id": "99", "name": "A'ja Wilson"},
        ),
        patch.object(
            player_prop_research.espn_provider,
            "get_athlete_gamelog",
            return_value={
                "verified": True,
                "games": [{"points": 24}] * 10,
                "source_url": "https://espn.test/gamelog",
            },
        ),
        patch.object(
            player_prop_research.espn_provider,
            "get_league_injuries",
            return_value={
                "verified": True,
                "by_team": {
                    "Las Vegas Aces": [{"name": "A'ja Wilson", "status": "Out"}],
                },
            },
        ),
    ):
        out = player_prop_research.enrich_player_prop_candidates([priced])[0]

    # Out athletes stay on the slate as market_implied (visible) but are not modeled.
    assert out.probability_source == "market_implied"
    assert out.candidate_id == priced.candidate_id


def test_enrich_maps_pra_market_type_from_board_flatten() -> None:
    games = [
        {"points": 20, "totalRebounds": 8, "assists": 5, "game_date": f"2026-09-{d:02d}"}
        for d in range(16, 6, -1)
    ]
    candidate = _board_prop(
        market_type="player_pra_over",
        selection="A'ja Wilson Over 30.5 pts+reb+ast",
        line=Decimal("30.5"),
    )
    with (
        patch.object(player_prop_research.espn_provider, "resolve_team_id", return_value="1"),
        patch.object(
            player_prop_research.espn_provider,
            "resolve_athlete_id",
            return_value={"id": "99", "name": "A'ja Wilson"},
        ),
        patch.object(
            player_prop_research.espn_provider,
            "get_athlete_gamelog",
            return_value={"verified": True, "games": games, "source_url": "x"},
        ),
        patch.object(
            player_prop_research.espn_provider,
            "get_league_injuries",
            return_value={"verified": False, "by_team": {}},
        ),
    ):
        enriched = player_prop_research.enrich_player_prop_candidates([candidate])[0]

    assert enriched.probability_source == "model"
    assert enriched.injuries_verified is True
    assert enriched.source_status.get("injuries") == "probable"


def test_live_wnba_slate_enriches_props_in_place() -> None:
    from app.services import live_wnba_slate as wnba

    odds_events = [
        {
            "id": "game-1",
            "home_team": "Atlanta Dream",
            "away_team": "Connecticut Sun",
            "commence_time": "2026-09-17T23:30:00Z",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "title": "DraftKings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Atlanta Dream", "price": -140},
                                {"name": "Connecticut Sun", "price": 120},
                            ],
                        }
                    ],
                }
            ],
        }
    ]
    prop_payload = {
        "id": "game-1",
        "home_team": "Atlanta Dream",
        "away_team": "Connecticut Sun",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "markets": [
                    {
                        "key": "player_points",
                        "outcomes": [
                            {
                                "name": "Over",
                                "description": "A'ja Wilson",
                                "price": -115,
                                "point": 22.5,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    research = {
        "schedule_verified": True,
        "form_verified": False,
        "injuries_verified": False,
        "weather_verified": False,
        "home_away_verified": True,
        "starter_confirmed": False,
        "lineup_confirmed": False,
        "market_movement_verified": True,
        "sport_specific_sweep_complete": False,
        "missing_fields": [],
        "source_status": {},
        "source_urls": [],
        "factors": {},
        "estimated_probability_home": 0.55,
        "estimated_probability_away": 0.45,
        "data_quality": 0.7,
        "flags": {},
    }
    modeled = _board_prop(probability_source="model", data_source="ESPN_PLAYER_PROP_MODEL")

    def fake_enrich(rows, slate_date=None):
        return [modeled if "Wilson" in r.selection else r for r in rows]

    with (
        patch.object(wnba, "get_game_odds", return_value=odds_events),
        patch.object(wnba, "league_injuries", return_value={}),
        patch.object(wnba, "build_event_research", return_value=research),
        patch.object(wnba, "get_player_props", return_value=prop_payload),
        patch.object(wnba, "enrich_player_prop_candidates", side_effect=fake_enrich),
        patch.object(wnba.settings, "wnba_max_prop_events", 10),
    ):
        slate = wnba.live_wnba_slate(date(2026, 9, 17))
        status = wnba.get_last_wnba_props_status()

    prop_rows = [c for c in slate if "Wilson" in c.selection]
    assert prop_rows
    assert any(c.probability_source == "model" for c in prop_rows)
    assert status["prop_candidates"] >= 1
    assert status["model_props"] >= 1
    assert "ESPN form-modeled" in wnba.wnba_props_slate_notice()
