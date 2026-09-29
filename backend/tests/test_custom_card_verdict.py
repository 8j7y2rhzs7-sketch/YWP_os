"""Custom cards publish one verdict and honor leg verification."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.services.quant_bridge import audit_ticket, recommendation_to_quant_leg
from app.services.ticket_builder import preview_custom_card


def _leg(
    *,
    name: str,
    event_id: str,
    decision: str,
    threshold: str,
    readiness: str,
    reason_codes: list[str],
    probability: str = "0.70",
) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=str(uuid4()),
        analysis_id=str(uuid4()),
        created_by_user_id=str(uuid4()),
        candidate_id=f"c-{name}",
        event_id=event_id,
        event_name=name,
        sport="mlb",
        league="MLB",
        slate_date=date.today(),
        mode="pregame",
        market_type="moneyline",
        market_period="full_game",
        selection=name,
        line=None,
        american_odds=150,
        estimated_probability=Decimal(probability),
        implied_probability=Decimal("0.40"),
        adjusted_probability=Decimal(probability),
        edge=Decimal("0.20"),
        expected_value=Decimal("0.15"),
        confidence_score=88,
        ywp_rating=Decimal("8.0"),
        vision_score=Decimal("7.0"),
        miss_by_one_risk=Decimal("0.20"),
        reliability=Decimal("0.8"),
        stability=Decimal("0.8"),
        variance=Decimal("0.25"),
        data_quality=Decimal("0.90"),
        risk="low",
        risk_tier="Minimal",
        variance_rating="Low",
        edge_class="Strong",
        expected_value_label="Positive",
        suggested_stake_pct=Decimal("0.01"),
        decision=decision,
        recommendation_tier="stay_away" if decision == "SKIP" else "cash_builder",
        rank=1,
        reason_codes=reason_codes,
        reasoning_summary="test",
        warnings=[],
        safer_alternative=None,
        higher_upside=None,
        invalidation_conditions=[],
        live_trigger=None,
        hedge=None,
        quick_cash=False,
        chain_reaction_key=None,
        thesis_key=f"thesis-{event_id}",
        script_key=f"script-{event_id}",
        player_key=None,
        data_source="MLB_STATS_API+THE_ODDS_API",
        source_timestamp=now,
        model_version="test",
        protocol_version="2026.09.03",
        input_hash=event_id,
        snapshot={
            "probability_source": "model",
            "model_probability": float(probability),
            "readiness": readiness,
            "pipeline_threshold": threshold,
            "effective_samples": 20,
            "starter_confirmed": readiness == "VERIFIED",
            "pipeline": {
                "stages": {
                    "verification": {
                        "status": "ok" if readiness == "VERIFIED" else "partial",
                        "readiness": readiness,
                        "verification_status": readiness,
                    }
                }
            },
            "pipeline_distribution": {"tail_probability": float(probability)},
        },
        outcome=None,
        created_at=now,
    )


def _assert_one_published_verdict(card) -> None:
    pipe = card.pipeline or {}
    monte_carlo = pipe.get("monte_carlo") or {}
    assert card.pipeline_threshold == pipe.get("card_threshold")
    assert card.joint_win_probability == pipe.get("joint_win_probability")
    assert card.joint_win_probability == monte_carlo.get("win_probability")
    if card.joint_win_probability is None:
        assert card.monte_carlo_sims is None
        assert monte_carlo.get("sims") is None
    else:
        assert card.monte_carlo_sims == monte_carlo.get("sims")
        assert card.monte_carlo_sims is not None


def test_rejected_unverified_legs_do_not_qualify() -> None:
    sox = _leg(
        name="White Sox ML",
        event_id="game-sox",
        decision="SKIP",
        threshold="reject",
        readiness="PARTIAL",
        reason_codes=["VERIFICATION_GAP", "RESEARCH_INCOMPLETE"],
    )
    padres = _leg(
        name="Padres ML",
        event_id="game-padres",
        decision="SKIP",
        threshold="reject",
        readiness="PARTIAL",
        reason_codes=["VERIFICATION_GAP", "RESEARCH_INCOMPLETE"],
    )
    for leg in (sox, padres):
        mapped = recommendation_to_quant_leg(leg)
        assert mapped["verification"]["event_confirmed"] is False
        assert mapped["verification"]["status"] == "unverified"

    audited = audit_ticket([sox, padres], simulations=4_000)
    assert audited["decision"] == "REJECT"
    assert audited["pipeline_threshold"] == "reject"
    assert audited["legs"]
    for leg in audited["legs"]:
        assert leg["verification_score"] < 1.0
        assert leg["verification_issues"]

    card = preview_custom_card([sox, padres], label="Rejected moneylines")
    _assert_one_published_verdict(card)
    assert card.pipeline_threshold == "reject"
    assert card.joint_win_probability is None
    quant = (card.pipeline or {})["ywp_quant"]
    assert quant["decision"] == "REJECT"
    assert quant["pipeline_threshold"] == "reject"
    assert quant.get("authoritative_for_card") is False
    assert not any(warning.startswith("ywp_quant QUALIFY") for warning in card.warnings)


def test_verified_legs_publish_one_quant_probability() -> None:
    first = _leg(
        name="Yankees ML",
        event_id="game-nyy",
        decision="PLAY",
        threshold="qualify",
        readiness="VERIFIED",
        reason_codes=["OK"],
    )
    second = _leg(
        name="Dodgers ML",
        event_id="game-lad",
        decision="PLAY",
        threshold="qualify",
        readiness="VERIFIED",
        reason_codes=["OK"],
    )
    card = preview_custom_card([first, second], label="Verified moneylines")
    _assert_one_published_verdict(card)
    assert card.pipeline_threshold == "qualify"
    assert card.joint_win_probability is not None
    quant = (card.pipeline or {})["ywp_quant"]
    assert quant["decision"] == "QUALIFY"
    assert quant["authoritative_for_card"] is True
    assert card.joint_win_probability == quant["ticket"]["model_probability"]
    assert card.monte_carlo_sims == quant["ticket"]["simulations"]
    for leg in quant["legs"]:
        assert leg["verification_score"] == 1.0
        assert leg["verification_issues"] == []
