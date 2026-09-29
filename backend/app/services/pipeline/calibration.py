"""Stage 9 — calibration metrics: Brier, CLV, predicted vs actual."""

from __future__ import annotations

from typing import Any


def brier_score(probability: float, won: bool) -> float:
    outcome = 1.0 if won else 0.0
    return (float(probability) - outcome) ** 2


def summarize_calibration(
    rows: list[tuple[float, bool, float | None, str]],
) -> dict[str, Any]:
    """rows: (model_p, won, clv_probability_or_none, market_type)."""
    if not rows:
        return {
            "n": 0,
            "brier": None,
            "mean_clv": None,
            "predicted_hit_rate": None,
            "actual_hit_rate": None,
            "by_market": [],
        }

    briers: list[float] = []
    clvs: list[float] = []
    predicted = 0.0
    wins = 0
    by_market: dict[str, dict[str, Any]] = {}

    for prob, won, clv, market in rows:
        p = max(0.0, min(1.0, float(prob)))
        briers.append(brier_score(p, won))
        predicted += p
        wins += int(won)
        if clv is not None:
            clvs.append(float(clv))
        bucket = by_market.setdefault(
            market or "unknown",
            {"n": 0, "wins": 0, "brier_sum": 0.0, "pred_sum": 0.0, "clv_sum": 0.0, "clv_n": 0},
        )
        bucket["n"] += 1
        bucket["wins"] += int(won)
        bucket["brier_sum"] += briers[-1]
        bucket["pred_sum"] += p
        if clv is not None:
            bucket["clv_sum"] += float(clv)
            bucket["clv_n"] += 1

    n = len(rows)
    market_rows = []
    for market, values in sorted(by_market.items()):
        market_rows.append(
            {
                "market_type": market,
                "n": values["n"],
                "actual_hit_rate": round(values["wins"] / values["n"], 4),
                "predicted_hit_rate": round(values["pred_sum"] / values["n"], 4),
                "brier": round(values["brier_sum"] / values["n"], 6),
                "mean_clv": (
                    round(values["clv_sum"] / values["clv_n"], 6) if values["clv_n"] else None
                ),
            }
        )

    return {
        "n": n,
        "brier": round(sum(briers) / n, 6),
        "mean_clv": round(sum(clvs) / len(clvs), 6) if clvs else None,
        "predicted_hit_rate": round(predicted / n, 4),
        "actual_hit_rate": round(wins / n, 4),
        "by_market": market_rows,
    }
