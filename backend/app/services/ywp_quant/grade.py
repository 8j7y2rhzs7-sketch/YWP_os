"""Grade a timestamped JSONL forecast ledger out of sample."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .calibration import brier_score, calibration_table, log_loss


def grade_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    graded = [record for record in records if record.get("outcome") in (0, 1)]
    if not graded:
        raise ValueError("No graded records with binary outcomes")
    probabilities = [float(record["probability"]) for record in graded]
    outcomes = [int(record["outcome"]) for record in graded]
    closing_edges = [
        float(record["closing_probability"]) - float(record["probability"])
        for record in graded if record.get("closing_probability") is not None
    ]
    settled = [record for record in graded if record.get("profit") is not None and record.get("stake")]
    total_stake = sum(float(record["stake"]) for record in settled)
    total_profit = sum(float(record["profit"]) for record in settled)
    return {
        "forecasts": len(graded),
        "brier_score": brier_score(probabilities, outcomes),
        "log_loss": log_loss(probabilities, outcomes),
        "mean_forecast": sum(probabilities) / len(probabilities),
        "hit_rate": sum(outcomes) / len(outcomes),
        "mean_probability_clv": (sum(closing_edges) / len(closing_edges)) if closing_edges else None,
        "roi": (total_profit / total_stake) if total_stake else None,
        "calibration": calibration_table(probabilities, outcomes),
        "warning": "Do not tune thresholds on this report and call the same sample a test set.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade a JSONL ledger of locked pre-event forecasts")
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    records = [json.loads(line) for line in args.ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    rendered = json.dumps(grade_records(records), indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
