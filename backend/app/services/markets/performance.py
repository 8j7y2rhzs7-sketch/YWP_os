"""Track record for markets calls. These buckets stay out of sports Hive."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models_markets import MarketCall, MarketOutcome
from app.services.pipeline.calibration import summarize_calibration
from app.services.ywp_quant.calibration import calibration_table


def track_record(db: Session, venue_group: str) -> dict[str, object]:
    calls = list(db.scalars(select(MarketCall).where(MarketCall.venue_group == venue_group)).all())
    call_ids = [call.id for call in calls]
    outcomes = []
    if call_ids:
        outcomes = list(
            db.scalars(select(MarketOutcome).where(MarketOutcome.call_id.in_(call_ids))).all()
        )
    by_call = {row.call_id: row for row in outcomes}
    rows: list[tuple[float, bool, float | None, str]] = []
    returns: list[float] = []
    wins = 0
    graded = 0
    for call in calls:
        outcome = by_call.get(call.id)
        if outcome is None or outcome.won is None:
            continue
        graded += 1
        wins += int(outcome.won)
        if outcome.realized_return is not None:
            returns.append(float(outcome.realized_return))
        if call.model_probability is None:
            continue
        rows.append((float(call.model_probability), bool(outcome.won), None, call.call_type))
    summary = summarize_calibration(rows)
    buckets: list[dict[str, float | int]] = []
    if rows:
        buckets = calibration_table([row[0] for row in rows], [int(row[1]) for row in rows])
    verdicts: dict[str, int] = {}
    for call in calls:
        verdicts[call.verdict] = verdicts.get(call.verdict, 0) + 1
    versions = sorted({call.model_version for call in calls})
    return {
        "venue_group": venue_group,
        "scope": "markets",
        "separate_from_sports": True,
        "n_calls": len(calls),
        "n_graded": graded,
        "hit_rate": round(wins / graded, 4) if graded else None,
        "mean_ev": round(sum(returns) / len(returns), 6) if returns else None,
        "brier": summary["brier"],
        "predicted_hit_rate": summary["predicted_hit_rate"],
        "actual_hit_rate": summary["actual_hit_rate"],
        "calibration_buckets": buckets,
        "by_verdict": verdicts,
        "model_versions": versions,
        "note": (
            "Markets calibration is stored on its own. It is not mixed into sports Hive buckets."
        ),
    }
