"""Official cards must use safe_pool (miss_by_one < 0.55) — locked 2026-11-14."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.services import ticket_builder


def _rec(
    *,
    rid: str,
    selection: str,
    thesis: str,
    miss: float,
    confidence: int = 90,
    ywp: float = 8.0,
    vision: float = 8.0,
    edge: float = 0.05,
    variance: float = 0.2,
    player: str = "p1",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=rid,
        selection=selection,
        decision="PLAY",
        ywp_rating=ywp,
        confidence_score=confidence,
        vision_score=vision,
        edge=edge,
        expected_value=0.05,
        variance=variance,
        miss_by_one_risk=miss,
        thesis_key=thesis,
        script_key=f"script-{thesis}",
        player_key=player,
        event_id=f"e-{rid}",
        snapshot={"script_alignment": 0.5},
        quick_cash=False,
        chain_reaction_key=None,
        risk="low",
    )


def _fake_card(key: str, label: str, legs: list, warnings: list[str] | None = None):
    return {
        "key": key,
        "label": label,
        "recommendation_ids": [item.id for item in legs],
        "warnings": list(warnings or []),
    }


def test_official_cards_exclude_high_miss_by_one() -> None:
    safe = _rec(
        rid="safe-1",
        selection="Bam REB O7.5",
        thesis="bam-reb",
        miss=0.20,
        player="bam",
    )
    killer = _rec(
        rid="kill-1",
        selection="Thin PTS O20.5",
        thesis="thin-pts",
        miss=0.72,
        confidence=96,
        ywp=9.5,
        vision=9.5,
        edge=0.10,
        player="thin",
    )
    with patch.object(ticket_builder, "_card", side_effect=_fake_card):
        cards, _ = ticket_builder.build_cards([safe, killer], max_legs=4, min_rating=0)

    for key in ("core_3", "core_4", "core_parlay", "elite_two", "ticket_a", "fortress"):
        ids = set(cards[key]["recommendation_ids"])
        assert "kill-1" not in ids, f"{key} included ticket-killer miss=0.72"
        assert "safe-1" in ids


def test_safe_pool_empty_falls_back_with_warn() -> None:
    only_thin = _rec(
        rid="thin-only",
        selection="Thin O20.5",
        thesis="thin",
        miss=0.60,
        confidence=88,
    )
    with patch.object(ticket_builder, "_card", side_effect=_fake_card):
        cards, _ = ticket_builder.build_cards([only_thin], max_legs=3, min_rating=0)

    assert "thin-only" in cards["core_3"]["recommendation_ids"]
    assert any("SAFE_POOL_EMPTY" in w for w in cards["core_3"]["warnings"])
