# YWP Quant Engine v0.2

An auditable probability and decision gate for threshold markets and multi-leg tickets. It is deliberately conservative: missing verification, weak samples, unknown same-event dependence, unavailable prices, or insufficient edge produce **REJECT**, not a forced recommendation.

This is a research and decision-support engine, not a guarantee of outcomes. Its quality depends on timestamped, correctly scoped inputs and out-of-sample calibration.

API version pairing: **3.3.63+**.

## What institutional-grade calculation means here

Finest quantitative sports pricing is not a vibe score. It is:

1. **Fair market probability** — remove the book’s overround with a method that respects skew (Shin), with multiplicative / power as comparables; multi-way normalize for 3+ outcome markets.
2. **Outcome family** — count props use Poisson or Negative Binomial when overdispersed; continuous props stay Normal. Family is chosen from data, not assumed.
3. **Usage mixture** — minutes, foul trouble, blowouts, pace, and opponent enter as an explicit scenario mixture on the mean, not a single fudge factor.
4. **Uncertainty** — every leg carries a posterior median and a 90% interval; tickets size and edge-check off the downside.
5. **Dependence** — same-event legs require measured ρ; joint win rate uses Gaussian and Student-t copulas and takes the more pessimistic value (tail dependence).
6. **Price edge** — model joint p vs de-vigged market; EV per unit stake; fractional Kelly on the lower-90 probability.
7. **Calibration loop** — Brier (Murphy decomposition), ECE, calibration slope, log loss, CLV when a close is supplied.
8. **Hard REJECT** — no qualify without price, samples, verification, or edge.

## What it calculates

For each leg:

- verification score and explicit input failures;
- posterior median hit probability and a 90% uncertainty interval;
- projected mean, dispersion, effective sample size;
- distribution family (`negbin` / `poisson` / `normal` / `direct`) and overdispersion ratio;
- minutes / foul / blowout mixture diagnostics;
- data-quality and fragility warnings.

For the whole ticket:

- joint probability under Gaussian and Student-t copulas (conservative = min);
- uncertainty range for the joint probability;
- fair American odds;
- Shin / multiplicative / power de-vigged market probability (or vig-proxy);
- model edge, downside edge, expected value;
- fractional Kelly stake recommendation;
- optional CLV vs closing fair;
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

## Integration

Vendored at `backend/app/services/ywp_quant`. Board and Decision Board call it through `app.services.quant_bridge.audit_ticket`. HTTP surface: `POST /api/v1/sports/quant-audit`.

```bash
cd backend && uv run pytest tests/test_ywp_quant_v2.py tests/test_ywp_quant_bridge.py tests/test_edge_pipeline.py -q
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
  "market_family": "count",
  "verification": {
    "status": "pregame",
    "event_confirmed": true,
    "line_confirmed": true,
    "role_confirmed": true,
    "source_timestamp": "2026-09-28T20:00:00Z",
    "max_age_hours": 4
  },
  "observation_groups": [
    {
      "name": "recent",
      "values": [18, 25, 21, 16, 29, 20, 23, 17],
      "weight": 1.0,
      "overlap_group": "season",
      "recency_halflife": 4.0
    }
  ],
  "context": {
    "expected_minutes": 32.0,
    "baseline_minutes": 34.0,
    "pace_multiplier": 1.03,
    "opponent_multiplier": 0.98,
    "availability_probability": 0.99,
    "blowout_probability": 0.18,
    "blowout_workload_multiplier": 0.80,
    "foul_trouble_probability": 0.10,
    "foul_trouble_minutes_multiplier": 0.85
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

## Model outline (v0.2)

1. Pool capped effective sample weights across observation groups, discounting declared overlap; optional recency half-life.
2. Estimate within-group and between-group variance.
3. Choose Normal / Poisson / NegBin from overdispersion and count-likeness.
4. Apply pace, opponent, availability, and an explicit minutes / foul / blowout mixture.
5. Draw posterior means and dispersions; weak data widens uncertainty.
6. Estimate each threshold probability and its posterior interval.
7. Repair an invalid supplied correlation matrix to the nearest PSD correlation and report the repair.
8. Simulate joint hits with Gaussian and Student-t copulas; take the conservative joint.
9. Compare joint probability with Shin/best de-vigged market probability; compute EV and fractional Kelly.
10. Enforce configurable minimum probability, sample, quality, edge, leg-count, and verification rules.

## Calibration

Use `calibration.rich_grade_report` (or the pipeline Performance path) on locked pregame forecasts:

- Brier + Murphy reliability / resolution / uncertainty
- ECE
- calibration slope & intercept
- log loss
- mean CLV (model fair − close fair) when closing odds exist

## Remaining upgrades (honest backlog)

- ingest official lineups, injuries, and closing lines with source timestamps on every board row;
- sport/market-specific hierarchical priors instead of one generic family;
- estimate ρ from paired residuals rather than pipeline priors alone;
- freeze / retrain any segment that is miscalibrated or undersampled.

The target is not to “win every ticket.” The target is calibrated probabilities, positive expected value after price, and the discipline to return **NO QUALIFYING PLAY** most of the time when evidence is weak.
