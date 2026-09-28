"""Vendored ywp_quant engine + OS bridge."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.services.quant_bridge import audit_ticket, recommendation_to_quant_leg
from app.services.ywp_quant.engine import analyze_document
from app.services.ywp_quant.odds import american_to_probability, devig_two_way


def test_vendored_devig() -> None:
    result = devig_two_way(-110, -110)
    assert abs(result["fair_probability"] - 0.5) < 1e-9
    assert american_to_probability(1500) == 0.0625


def test_failed_same_event_ticket_rejects_without_correlation() -> None:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    document = {
        "seed": 1,
        "ticket": {"market": {"american_odds": 1500}, "simulations": 8_000, "correlations": []},
        "legs": [
            {
                "id": "a",
                "event_id": "G1",
                "market": "points",
                "direction": "over",
                "line": 19.5,
                "data_quality": 0.8,
                "verification": {
                    "status": "pregame",
                    "event_confirmed": True,
                    "line_confirmed": True,
                    "role_confirmed": True,
                    "source_timestamp": now,
                    "max_age_hours": 48,
                },
                "observation_groups": [
                    {"name": "recent", "values": [22, 18, 25, 20, 19, 24, 21, 17, 23, 26]}
                ],
            },
            {
                "id": "b",
                "event_id": "G1",
                "market": "points",
                "direction": "over",
                "line": 14.5,
                "data_quality": 0.8,
                "verification": {
                    "status": "pregame",
                    "event_confirmed": True,
                    "line_confirmed": True,
                    "role_confirmed": True,
                    "source_timestamp": now,
                    "max_age_hours": 48,
                },
                "observation_groups": [
                    {"name": "recent", "values": [16, 12, 15, 18, 11, 14, 17, 13, 19, 15]}
                ],
            },
        ],
    }
    result = analyze_document(document)
    assert result["decision"] == "REJECT"
    assert any("UNVERIFIED_SAME_EVENT" in b for b in result["blockers"])


def test_bridge_uses_observation_values_when_present() -> None:
    item = SimpleNamespace(
        id="leg-1",
        candidate_id="c1",
        event_id="E1",
        market_type="player_points_over",
        selection="Star Over 22.5 points",
        line=Decimal("22.5"),
        data_quality=Decimal("0.80"),
        decision="PLAY",
        adjusted_probability=Decimal("0.58"),
        miss_by_one_risk=Decimal("0.20"),
        stability=Decimal("0.80"),
        source_timestamp=datetime.now(UTC),
        snapshot={"observation_values": [28, 24, 30, 22, 26, 25, 27, 23, 29, 21]},
    )
    leg = recommendation_to_quant_leg(item)
    assert "observation_groups" in leg
    assert leg["observation_groups"][0]["values"][0] == 28.0


def test_audit_independent_legs_can_qualify() -> None:
    now = datetime.now(UTC)

    def leg(i: int, event: str) -> SimpleNamespace:
        return SimpleNamespace(
            id=str(uuid4()),
            candidate_id=f"c{i}",
            event_id=event,
            market_type="moneyline",
            selection=f"Team {i} ML",
            line=None,
            american_odds=-120,
            data_quality=Decimal("0.90"),
            decision="PLAY",
            adjusted_probability=Decimal("0.62"),
            miss_by_one_risk=Decimal("0.15"),
            stability=Decimal("0.85"),
            source_timestamp=now,
            player_key=f"p{i}",
            script_key=f"s{i}",
            thesis_key=f"t{i}",
            snapshot={
                "probability_source": "model",
                "model_probability": 0.62,
                "starter_confirmed": True,
                "effective_samples": 20,
            },
        )

    result = audit_ticket(
        [leg(1, "e1"), leg(2, "e2")],
        american_odds=260,
        opposite_american_odds=-320,
        simulations=12_000,
    )
    assert result["decision"] in {"QUALIFY", "REJECT"}
    assert result["pipeline_threshold"] in {"qualify", "reject"}
    assert result["force_pick"] is False
    assert "ticket" in result
