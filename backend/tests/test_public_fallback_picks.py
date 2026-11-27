"""Odds-down public fallback must still clear LEAN picks (not empty SKIP)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.schemas import CandidateInput
from app.services.decision_engine import decision_engine
from app.services.readiness import candidate_readiness, is_public_schedule_fallback


def _public_ml(*, probability: float = 0.62) -> CandidateInput:
    tip = datetime.now(UTC) + timedelta(hours=4)
    return CandidateInput(
        candidate_id="pub-nba-ml-home",
        event_id="espn-1",
        event_name="Away @ Home",
        sport="nba",
        league="NBA",
        market_type="moneyline",
        market_period="full_game",
        selection="Home ML",
        american_odds=-163,
        estimated_probability=probability,
        start_time=tip,
        home_team="Home",
        away_team="Away",
        data_source="PUBLIC_SCHEDULE_FALLBACK",
        source_timestamp=datetime.now(UTC),
        probability_source="model",
        thesis_key="pub-thesis",
        script_key="pub-script",
        reason_codes=["PUBLIC_SCHEDULE_FALLBACK", "NO_SPORTSBOOK_PRICE", "CURRENT_FORM"],
        reasoning=["Odds down — public schedule + form only."],
        variance=0.28,
        data_quality=0.70,
        schedule_verified=True,
        current_form_verified=True,
        home_away_verified=True,
        universe_scan_complete=True,
        market_movement_verified=False,
        game_status="PRE_GAME",
        market_status="OPEN",
        source_status={"schedule": "confirmed", "market": "n/a", "current_form": "confirmed"},
    )


def test_public_fallback_is_recognized() -> None:
    assert is_public_schedule_fallback(_public_ml()) is True


def test_public_fallback_does_not_hard_stop_as_skip() -> None:
    evaluation = decision_engine.evaluate(_public_ml())
    assert evaluation.decision == "LEAN"
    assert "PUBLIC_FALLBACK_LEAN" in evaluation.reason_codes
    assert "NO_CLEAN_EDGE" not in evaluation.reason_codes
    assert "Official YWP output: SKIP / NO PLAY." not in evaluation.reasoning_summary


def test_public_fallback_readiness_ignores_missing_book_market() -> None:
    # Market consensus cannot exist while Odds is down — should not alone empty the board.
    row = _public_ml()
    assert candidate_readiness(row) in {"PARTIAL", "VERIFIED"}
