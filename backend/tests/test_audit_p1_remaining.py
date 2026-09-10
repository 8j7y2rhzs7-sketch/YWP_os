from __future__ import annotations

from datetime import UTC, datetime

from app.schemas import CandidateInput
from app.services.board_metrics import card_risk, market_scope_label
from app.services.readiness import candidate_verification_gaps
from app.services.sport_model import project_matchup


def _candidate(**overrides) -> CandidateInput:
    base = dict(
        candidate_id="cand-01",
        event_id="evt-01",
        event_name="Away @ Home",
        sport="nba",
        league="NBA",
        start_time=datetime.now(UTC),
        home_team="Home",
        away_team="Away",
        market_type="moneyline",
        selection="Home ML",
        american_odds=-110,
        estimated_probability=0.55,
        probability_source="model",
        variance=0.3,
        data_quality=0.7,
        data_source="TEST",
        source_timestamp=datetime.now(UTC),
        source_status={"schedule": "confirmed", "market": "confirmed", "bullpen": "unknown"},
        schedule_verified=True,
        universe_scan_complete=True,
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
        thesis_key="home-control",
        script_key="pace-script",
    )
    base.update(overrides)
    return CandidateInput(**base)


def test_nba_unknown_bullpen_is_not_a_hard_gap() -> None:
    gaps = candidate_verification_gaps(_candidate(sport="nba"))
    assert not any(gap.startswith("source:bullpen") for gap in gaps)


def test_mlb_unknown_bullpen_remains_a_hard_gap() -> None:
    gaps = candidate_verification_gaps(
        _candidate(
            sport="mlb",
            league="MLB",
            source_status={"schedule": "confirmed", "market": "confirmed", "bullpen": "unknown"},
        )
    )
    assert "source:bullpen" in gaps


def test_soccer_1x2_includes_draw_probability() -> None:
    home = project_matchup(
        home_form={"verified": True, "l5": {"win_pct": 0.6}, "l10": {"win_pct": 0.55}},
        away_form={"verified": True, "l5": {"win_pct": 0.4}, "l10": {"win_pct": 0.45}},
        market_type="moneyline",
        selection="Home ML",
        is_home_selection=True,
        include_draw=True,
    )
    draw = project_matchup(
        home_form={"verified": True, "l5": {"win_pct": 0.6}, "l10": {"win_pct": 0.55}},
        away_form={"verified": True, "l5": {"win_pct": 0.4}, "l10": {"win_pct": 0.45}},
        market_type="moneyline_draw",
        selection="Draw (90 min)",
        include_draw=True,
    )
    assert home.home_strength + home.away_strength < 0.99
    assert 0.08 <= draw.win_probability <= 0.92
    assert any("1X2" in note or "draw" in note.lower() for note in draw.notes)


def test_soccer_moneyline_label_is_not_run_line() -> None:
    assert "1X2" in market_scope_label("moneyline", "90_min", sport="soccer")
    assert "Run line" not in market_scope_label("spread", "full_game", sport="nfl")
    assert "Point spread" in market_scope_label("spread", "full_game", sport="nfl")


def test_custom_card_preview_uses_backend_multi_leg_risk() -> None:
    class Leg:
        def __init__(self, risk: str, miss: float, var: float, event_id: str, conf: int, yis: float, oid: str):
            self.risk = risk
            self.miss_by_one_risk = miss
            self.variance = var
            self.event_id = event_id
            self.confidence_score = conf
            self.ywp_rating = yis
            self.id = oid
            self.american_odds = -110
            self.selection = oid
            self.snapshot = {"probability_source": "model"}
            self.adjusted_probability = 0.55

    legs = [
        Leg("low", 0.2, 0.2, "e1", 80, 8.0, "a"),
        Leg("low", 0.2, 0.2, "e2", 78, 7.8, "b"),
    ]
    risk, explanation = card_risk(legs)  # type: ignore[arg-type]
    assert risk == "medium"
    assert "Multi-leg" in explanation
