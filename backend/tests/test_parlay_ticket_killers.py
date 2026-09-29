"""Ticket-killers must not stack onto parlays."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.schemas import CandidateInput, RiskProfile
from app.services.decision_engine import decision_engine, verified_safer_alternative
from app.services.ticket_builder import build_cards


def test_placeholder_safer_alternative_is_not_verified() -> None:
    assert verified_safer_alternative(None) is False
    assert verified_safer_alternative("") is False
    assert verified_safer_alternative("Safer version of Player Over 22.5") is False
    assert verified_safer_alternative("Pick a different market on this sheet") is False
    assert (
        verified_safer_alternative("Use a lower line only if its own model edge is verified: X")
        is False
    )
    assert verified_safer_alternative("Under 21.5 points (same player)") is True


def test_critical_miss_by_one_skips_even_with_placeholder_safer() -> None:
    now = datetime.now(UTC)
    candidate = CandidateInput(
        candidate_id="ml-thin",
        event_id="event-1",
        event_name="A @ B",
        sport="mlb",
        league="MLB",
        start_time=now,
        market_type="moneyline",
        selection="Team A ML",
        american_odds=-110,
        estimated_probability=0.64,
        variance=0.55,
        data_quality=0.95,
        data_source="TEST",
        source_timestamp=now,
        source_status={"market": "confirmed"},
        recent_hit_rate=0.5,
        average_cushion=0.1,
        cushion_scale=1.0,
        miss_by_one_count_l10=8,
        matchup_score=0.5,
        script_alignment=0.4,
        multiple_paths_score=0.3,
        role_stability=0.4,
        ticket_killer_count=3,
        safer_alternative="Safer version of Team A ML",
        thesis_key="ml-a",
        script_key="script-a",
        schedule_verified=True,
        current_form_verified=True,
        l5_l10_verified=True,
        lineup_confirmed=True,
        injuries_verified=True,
        weather_verified=True,
        starter_confirmed=True,
        motivation_rotation_verified=True,
        home_away_verified=True,
        market_movement_verified=True,
        sport_specific_sweep_complete=True,
        universe_scan_complete=True,
    )
    evaluation = decision_engine.evaluate(candidate, RiskProfile.balanced)
    assert evaluation.decision == "SKIP"
    assert "MISS_BY_ONE_GATE_FAILED" in evaluation.reason_codes


def _play(*, miss: float, rank: int, thesis: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=str(uuid4()),
        analysis_id=str(uuid4()),
        created_by_user_id=str(uuid4()),
        candidate_id=f"cand-{rank}",
        event_id=f"event-{rank}",
        event_name="A @ B",
        sport="mlb",
        league="MLB",
        slate_date=date.today(),
        mode="pregame",
        market_type="moneyline",
        market_period="full_game",
        selection=f"Team {rank} ML",
        line=None,
        american_odds=-110,
        estimated_probability=Decimal("0.58"),
        implied_probability=Decimal("0.52"),
        adjusted_probability=Decimal("0.58"),
        edge=Decimal("0.06"),
        expected_value=Decimal("0.05"),
        confidence_score=90,
        ywp_rating=Decimal("8.50"),
        vision_score=Decimal("7.50"),
        miss_by_one_risk=Decimal(str(miss)),
        reliability=Decimal("0.80"),
        stability=Decimal("0.80"),
        variance=Decimal("0.25"),
        data_quality=Decimal("0.90"),
        risk="low",
        risk_tier="Minimal",
        variance_rating="Low",
        edge_class="Strong",
        expected_value_label="Positive",
        suggested_stake_pct=Decimal("0.01"),
        decision="PLAY",
        recommendation_tier="core_parlay" if miss < 0.55 else "support",
        rank=rank,
        reason_codes=["OK"],
        reasoning_summary="test",
        warnings=[],
        safer_alternative=None,
        higher_upside=None,
        invalidation_conditions=[],
        live_trigger=None,
        hedge=None,
        quick_cash=False,
        chain_reaction_key=None,
        thesis_key=thesis,
        script_key=f"script-{rank}",
        player_key=f"player-{rank}",
        data_source="UNIT",
        source_timestamp=datetime.now(UTC),
        model_version="test",
        protocol_version="2026.09.03",
        input_hash=f"hash-{rank}",
        snapshot={"probability_source": "model", "script_alignment": 0.7},
        outcome=None,
        created_at=datetime.now(UTC),
    )


def test_elevated_miss_excluded_from_parlay_cards() -> None:
    safe = [_play(miss=0.20, rank=i + 1, thesis=f"safe-{i}") for i in range(4)]
    killer = _play(miss=0.62, rank=5, thesis="killer")
    cards, quarantined = build_cards([*safe, killer], max_legs=5, min_rating=0)

    assert "max_bet" in cards
    # Killer may still be Max Bet if it ranks highest — here rank 5 so max is safe.
    assert cards["max_bet"].legs[0].id == safe[0].id

    for key in ("core_parlay", "core_3", "elite_two", "ticket_a", "ghostt", "hybrid_mix"):
        if key not in cards:
            continue
        for leg in cards[key].legs:
            assert float(leg.miss_by_one_risk) < 0.55, f"{key} stacked ticket-killer"

    reasons = " ".join(item.reason for item in quarantined)
    assert "Elevated miss-by-1" in reasons
