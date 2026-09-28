# YWP OS Edge Pipeline (v1.1)

Nine stages from research to calibration. API **3.3.63+**.

Authoritative ticket gate: vendored **ywp_quant v0.2** (`app.services.ywp_quant`) via
`POST /api/v1/sports/quant-audit` and Decision Board card builds. Same-event
tickets without measured correlations **REJECT**. No forced picks.

| # | Stage | Status in v1.1 |
|---|--------|----------------|
| 1 | Verification gate | Wired via readiness / research flags |
| 2 | Minutes / usage | Explicit minutes / foul / blowout mixture in ywp_quant |
| 3 | Stat distribution | NegBin / Poisson / Normal + mean / σ / tail |
| 4 | Context adjustments | Pace, opponent, availability, injury restriction multipliers |
| 5 | Market comparison | Shin / power / multiplicative de-vig; multi-way; vig-proxy |
| 6 | Correlation engine | Same-game / same-player / script ρ priors; PSD repair |
| 7 | Monte Carlo | Gaussian + Student-t copula; conservative joint |
| 8 | Decision threshold | `qualify` / `reject` via quant gate + EV / fractional Kelly |
| 9 | Calibration | Brier decomposition, ECE, slope, CLV on Performance |

Surfaces: `Recommendation.snapshot.pipeline`, `AnalyzeResponse.pipeline_stages`, `TicketCardOut.pipeline` / Monte Carlo fields, `PerformanceOut.brier` / `calibration_by_market`.
