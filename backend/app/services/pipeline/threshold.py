"""Stage 8 — qualify / borderline / reject (no forced pick)."""

from __future__ import annotations

from typing import Any


def map_decision_threshold(
    *,
    decision: str,
    confidence_score: int,
    edge: float,
    miss_by_one_risk: float,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    """Map engine decision → pipeline threshold vocabulary."""
    codes = list(reason_codes or [])
    decision_u = (decision or "").upper()

    if decision_u == "PLAY" and miss_by_one_risk < 0.55 and edge >= 0.03 and confidence_score >= 85:
        return {
            "threshold": "qualify",
            "decision": decision_u,
            "force_pick": False,
            "note": "Clears confidence, fair edge, and miss-by-1 cushion gates.",
            "reason_codes": codes,
        }

    if decision_u in {"LEAN", "WATCH", "REVIEW"} or (
        decision_u == "PLAY" and (miss_by_one_risk >= 0.55 or edge < 0.03)
    ):
        label = {
            "LEAN": "Lean — edge present but not full qualify.",
            "WATCH": "Watch — incomplete conviction; do not force.",
            "REVIEW": "Review — outlier or mapping issue; do not force.",
            "PLAY": "Play flagged borderline by cushion/edge conflict.",
        }.get(decision_u, "Borderline — do not force a ticket.")
        return {
            "threshold": "borderline",
            "decision": decision_u,
            "force_pick": False,
            "note": label,
            "reason_codes": codes,
        }

    return {
        "threshold": "reject",
        "decision": decision_u or "SKIP",
        "force_pick": False,
        "note": "Reject / PASS. Uncertainty or gates failed — no forced pick.",
        "reason_codes": codes,
    }
