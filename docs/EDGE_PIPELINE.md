# YWP OS Edge Pipeline (v1.0)

Nine stages from research to calibration. API **3.3.61+**.

| # | Stage | Status in v1 |
|---|--------|----------------|
| 1 | Verification gate | Wired via readiness / research flags |
| 2 | Minutes / usage | Partial — `role_stability` proxy; full injury/foul/blowout model next |
| 3 | Stat distribution | Mean / σ / tail on modeled legs |
| 4 | Context adjustments | Partial — matchup / script / role scores |
| 5 | Market comparison | De-vig when opposite odds present; vig-proxy otherwise |
| 6 | Correlation engine | Same-game / same-player / script ρ priors |
| 7 | Monte Carlo | Correlated ticket sims → joint win rate |
| 8 | Decision threshold | `qualify` / `borderline` / `reject` — never force a pick |
| 9 | Calibration | Brier, CLV, predicted vs actual by market on Performance |

Surfaces: `Recommendation.snapshot.pipeline`, `AnalyzeResponse.pipeline_stages`, `TicketCardOut.pipeline` / Monte Carlo fields, `PerformanceOut.brier` / `calibration_by_market`.
