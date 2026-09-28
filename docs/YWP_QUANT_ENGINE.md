# YWP Quant Engine v0.1

An auditable probability and decision gate for threshold markets and multi-leg tickets. It is deliberately conservative: missing verification, weak samples, unknown same-event dependence, unavailable prices, or insufficient edge produce **REJECT**, not a forced recommendation.

This is a research and decision-support engine, not a guarantee of outcomes. Its quality depends on timestamped, correctly scoped inputs and out-of-sample calibration.

## What it calculates

For each leg:

- verification score and explicit input failures;
- posterior median hit probability and a 90% uncertainty interval;
- projected mean, dispersion, effective sample size, and workload/blowout adjustments;
- data-quality and fragility warnings.

For the whole ticket:

- joint probability through a Gaussian copula;
- uncertainty range for the joint probability;
- fair American odds;
- raw or de-vigged market probability;
- model edge and downside edge;
- a reproducible `QUALIFY` or `REJECT` decision with blockers.

## Why this corrects the old workflow

The old process rated legs independently with labels such as “8/10,” then stacked them without calculating their joint probability. That is mathematically invalid. A ticket priced at +1500 has a raw break-even probability of 6.25%; whether it has value can only be assessed after modeling every marginal probability, their uncertainty, and their dependence.

The engine refuses to:

- treat a recent hit rate as a calibrated probability;
- count overlapping L5/L10/season samples as independent evidence;
- assume same-game legs are independent;
- infer that the opposite side is good merely because one side is rejected;
- qualify a ticket without a comparable market price;
- hide missing role, status, timestamp, or line verification.

## Install and run

From this directory:

```bash
python -m pip install -e .
ywp-quant examples/failed_wnba_ticket.json --output examples/failed_wnba_ticket.audit.json
```

Without installation:

```bash
PYTHONPATH=src python -m ywp_quant.cli examples/failed_wnba_ticket.json
```

Run tests:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Grade a locked, out-of-sample forecast ledger:

```bash
PYTHONPATH=src python -m ywp_quant.grade examples/sample_ledger.jsonl
```

## Input contract

Each leg needs a stable `id`, `event_id`, exact `market`, `direction`, `line`, verification block, data-quality score, observations, and context. Observation groups may represent recent, season, or matchup data. Give overlapping groups the same `overlap_group`; later groups in that cluster are heavily discounted.

```json
{
  "id": "player_points",
  "event_id": "AWAY_HOME_2026-09-28",
  "market": "Player points",
  "direction": "over",
  "line": 19.5,
  "data_quality": 0.82,
  "verification": {
    "status": "pregame",
    "event_confirmed": true,
    "line_confirmed": true,
    "role_confirmed": true,
    "source_timestamp": "2026-09-28T20:00:00Z",
    "max_age_hours": 4
  },
  "observation_groups": [
    {"name": "season", "values": [18, 25, 21, 16, 29, 20, 23, 17], "weight": 1.0, "overlap_group": "season"}
  ],
  "context": {
    "mean_multiplier": 1.0,
    "mean_add": 0.0,
    "variance_multiplier": 1.0,
    "workload_multiplier": 1.0,
    "workload_uncertainty": 0.06,
    "availability_probability": 0.99,
    "blowout_probability": 0.18,
    "blowout_workload_multiplier": 0.80
  }
}
```

Ticket-level market and dependence data:

```json
{
  "ticket": {
    "market": {"american_odds": 250, "opposite_american_odds": -320},
    "simulations": 250000,
    "correlations": [
      {"leg_a": "player_points", "leg_b": "team_over", "rho": 0.24}
    ]
  }
}
```

Do not invent correlation values. Estimate them from historical paired residuals under comparable roles, or leave them blank and accept the automatic rejection for same-event tickets.

## Model outline

1. Pool capped effective sample weights across observation groups, discounting declared overlap.
2. Estimate within-group and between-group variance.
3. Draw posterior means and dispersions; weak data widens uncertainty.
4. Apply explicit context adjustments and a two-state blowout/workload mixture.
5. Estimate each threshold probability and its posterior interval.
6. Repair an invalid supplied correlation matrix to the nearest positive-semidefinite correlation matrix and report the repair.
7. Simulate joint hits with a Gaussian copula.
8. compare joint probability with raw or de-vigged market probability.
9. Enforce configurable minimum probability, sample, quality, edge, leg-count, and verification rules.

## Required production upgrades

Version 0.1 is a transparent baseline, not a finished predictive advantage. Before treating it as production-grade:

- ingest official lineups, injuries, market prices, and closing lines with source timestamps;
- train sport/market-specific hierarchical models rather than one generic outcome family;
- estimate correlations from paired residuals instead of subjective guesses;
- separate model training, validation, and untouched test periods;
- store every forecast before the event and grade it automatically;
- inspect Brier score, log loss, calibration slope, closing-line value, and return by probability bucket;
- freeze or retrain any segment that is miscalibrated or lacks enough observations.

The target is not to “win every ticket.” The target is calibrated probabilities, positive expected value after price, and the discipline to return **NO QUALIFYING PLAY** most of the time when evidence is weak.
