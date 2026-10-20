"""Locked rules from the last card: one-point WNBA, two-catch NFL, early MLB cash-out."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.schemas import CandidateInput, RiskProfile
from app.services.calculation_discipline import (
    one_point_miss_blockers,
    reception_role_blockers,
)
from app.services.decision_engine import decision_engine
from app.services.live_cashout import (
    advise_live_cashout,
    locked_live_trigger,
    ticket_must_hold,
)
from app.services.player_prop_research import min_prop_cushion
from app.services.protocols import CURRENT_PROTOCOL


def _prop(**overrides) -> CandidateInput:
    now = datetime.now(UTC)
    base = dict(
        candidate_id="miss-rule-1",
        event_id="event-1",
        event_name="Away @ Home",
        sport="wnba",
        league="WNBA",
        start_time=now,
        home_team="Home",
        away_team="Away",
        market_type="player_points_over",
        selection="Star Over 22.5 points",
        line=Decimal("22.5"),
        american_odds=-110,
        estimated_probability=0.62,
        probability_source="model",
        variance=0.30,
        data_quality=0.9,
        data_source="ESPN_PLAYER_PROP_MODEL",
        source_timestamp=now,
        source_status={"market": "confirmed", "schedule": "confirmed", "player_form": "confirmed"},
        schedule_verified=True,
        universe_scan_complete=True,
        current_form_verified=True,
        l5_l10_verified=True,
        home_away_verified=True,
        market_movement_verified=True,
        injuries_verified=True,
        starter_confirmed=True,
        lineup_confirmed=True,
        weather_verified=True,
        sport_specific_sweep_complete=True,
        independent_value_verified=True,
        motivation_rotation_verified=True,
        cushion_scale=4.0,
        role_stability=0.8,
        player_key="wnba-star",
        thesis_key="wnba-star-pts",
        script_key="wnba-star-form",
        recent_hit_rate=0.8,
        average_cushion=4.1,
        matchup_score=0.7,
        script_alignment=0.7,
        multiple_paths_score=0.75,
        miss_by_one_count_l10=2,
    )
    base.update(overrides)
    return CandidateInput(**base)


def test_one_point_shorts_skip_even_with_a_fat_average() -> None:
    # Two games land on 22 against 22.5. The average is still well clear.
    values = [30, 22, 28, 22, 27, 29, 26, 31, 24, 27]
    candidate = _prop(observation_values=values)
    assert one_point_miss_blockers(candidate) == ["ONE_POINT_MISS_GATE"]
    evaluation = decision_engine.evaluate(candidate, RiskProfile.balanced)
    assert evaluation.decision == "SKIP"
    assert "ONE_POINT_MISS_GATE" in evaluation.reason_codes


def test_clean_points_prop_is_not_a_one_point_miss() -> None:
    values = [28, 27, 26, 30, 25, 29, 24, 31, 27, 26]
    candidate = _prop(
        observation_values=values,
        average_cushion=4.6,
        miss_by_one_count_l10=0,
        recent_hit_rate=1.0,
    )
    assert one_point_miss_blockers(candidate) == []
    evaluation = decision_engine.evaluate(candidate, RiskProfile.balanced)
    assert "ONE_POINT_MISS_GATE" not in evaluation.reason_codes


def test_short_wnba_spread_is_a_one_point_loss() -> None:
    short = _prop(market_type="spread", selection="Home -1.5", line=Decimal("-1.5"))
    clear = _prop(market_type="spread", selection="Home -6.5", line=Decimal("-6.5"))
    assert one_point_miss_blockers(short) == ["ONE_POINT_MISS_GATE"]
    assert one_point_miss_blockers(clear) == []
    evaluation = decision_engine.evaluate(short, RiskProfile.balanced)
    assert evaluation.decision == "SKIP"
    assert "ONE_POINT_MISS_GATE" in evaluation.reason_codes


def test_two_catch_role_cannot_be_a_reception_over() -> None:
    # Antonio Williams shape: the night can end on two catches.
    candidate = _prop(
        sport="nfl",
        league="NFL",
        market_type="player_receptions_over",
        selection="Antonio Williams Over 3.5 receptions",
        line=Decimal("3.5"),
        cushion_scale=2.0,
        average_cushion=1.6,
        player_key="nfl-antonio-williams",
        thesis_key="nfl-williams-rec",
        script_key="nfl-williams-targets",
        observation_values=[4, 2, 1, 3, 2, 5, 2, 3, 1, 4],
    )
    assert min_prop_cushion(candidate) == 1.5
    assert reception_role_blockers(candidate) == ["RECEPTION_ROLE_VANISH"]
    evaluation = decision_engine.evaluate(candidate, RiskProfile.balanced)
    assert evaluation.decision == "SKIP"
    assert "RECEPTION_ROLE_VANISH" in evaluation.reason_codes


def test_volume_receiver_is_not_a_two_catch_role() -> None:
    candidate = _prop(
        sport="nfl",
        league="NFL",
        market_type="player_receptions_over",
        selection="Volume Receiver Over 5.5 receptions",
        line=Decimal("5.5"),
        cushion_scale=2.0,
        average_cushion=1.6,
        player_key="nfl-volume",
        thesis_key="nfl-volume-rec",
        script_key="nfl-volume-targets",
        observation_values=[8, 7, 9, 6, 8, 7, 5, 8, 7, 6],
        recent_hit_rate=0.9,
        miss_by_one_count_l10=0,
    )
    assert reception_role_blockers(candidate) == []
    evaluation = decision_engine.evaluate(candidate, RiskProfile.balanced)
    assert "RECEPTION_ROLE_VANISH" not in evaluation.reason_codes


def test_points_cushion_floor_is_one_point_and_pass_yards_stay_wide() -> None:
    points = _prop()
    yards = _prop(
        sport="nfl",
        league="NFL",
        market_type="player_pass_yds_over",
        selection="QB Over 275.5 pass yards",
        line=Decimal("275.5"),
        cushion_scale=25.0,
    )
    assert min_prop_cushion(points) == 1.5
    assert min_prop_cushion(yards) >= 5.0


def test_hold_batter_through_the_last_plate_appearance() -> None:
    diaz = advise_live_cashout(
        market_type="player_hits_over",
        game_status="LIVE",
        thesis_broken=False,
        plate_appearances_remaining=1,
        sibling_legs_live=True,
    )
    assert diaz.action == "HOLD"
    assert diaz.code == "HOLD_THROUGH_PLATE_APPEARANCE"
    # Marking the thesis broken does not override a remaining at-bat.
    scared = advise_live_cashout(
        market_type="player_hits_over",
        game_status="LIVE",
        thesis_broken=True,
        plate_appearances_remaining=1,
    )
    assert scared.action == "HOLD"
    trigger = locked_live_trigger("mlb", "player_hits_over")
    assert trigger is not None
    assert len(trigger) <= 255
    assert "plate appearance" in trigger


def test_two_catches_do_not_cash_the_rest_of_the_ticket() -> None:
    williams_live = advise_live_cashout(
        market_type="player_receptions_over",
        game_status="LIVE",
        thesis_broken=True,
        sibling_legs_live=True,
    )
    assert williams_live.action == "HOLD"
    assert williams_live.code == "HOLD_RECEPTIONS_UNTIL_FINAL"

    williams_final = advise_live_cashout(
        market_type="player_receptions_over",
        game_status="FINAL",
        thesis_broken=True,
        sibling_legs_live=True,
    )
    assert williams_final.action == "CASH_OUT"
    assert williams_final.scope == "LEG"
    assert williams_final.code == "CASH_DEAD_LEG_ONLY"

    diaz = advise_live_cashout(
        market_type="player_hits_over",
        game_status="LIVE",
        plate_appearances_remaining=1,
    )
    assert ticket_must_hold([williams_final, diaz]) is True


def test_protocol_locks_the_three_misses() -> None:
    blocks = " ".join(CURRENT_PROTOCOL["live_cashout_protocol"]["hard_blocks"])
    pre = " ".join(CURRENT_PROTOCOL["miss_by_one_protocol"]["pre_ticket"])
    assert "plate appearance" in blocks
    assert "two catches" in blocks
    assert "1.5" in blocks
    assert "within a point" in pre
    assert "two catches" in pre
