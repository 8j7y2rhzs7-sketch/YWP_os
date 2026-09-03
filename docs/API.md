# API Guide

Base path: `/api/v1`

## Core endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | Create an account and tokens |
| POST | `/auth/login` | Authenticate and rotate-able tokens |
| POST | `/auth/refresh` | Rotate a refresh token |
| POST | `/auth/logout` | Revoke a refresh token |
| GET/PATCH | `/users/me` | Read or update profile and risk settings |
| GET/PATCH | `/bankroll` | Read or update bankroll guardrails |
| GET/POST | `/bankroll/transactions` | Ledger history and deposits/withdrawals |
| GET | `/sports/slate` | Retrieve normalized provider candidates |
| POST | `/sports/analyze` | Analyze and persist candidates |
| POST | `/sports/build-ticket` | Build official, special, Stay Away, and ABC cards |
| GET | `/sports/recommendations/{id}` | Retrieve a stored recommendation |
| POST | `/tickets` | Save a selected draft ticket |
| GET | `/tickets` | List the current user's tickets |
| GET | `/tickets/{id}` | Retrieve one user-owned ticket |
| PATCH | `/tickets/{id}/legs/{leg_id}` | Follow, skip, replace, or remove one leg with a reason |
| POST | `/tickets/{id}/lock-check` | Run final pre-placement validation |
| POST | `/tickets/{id}/place` | Mark a currently valid locked ticket placed |
| POST | `/tickets/{id}/cancel` | Cancel an unplaced ticket |
| POST | `/sports/result` | Immutably grade outcome, process, CLV, Miss-by-1, live triggers, and cash-out action |
| GET | `/learning/performance` | ROI, win rate, and calibration |
| GET | `/learning/patterns` | Repeated success/failure modes |
| GET | `/learning/miss-by-one` | Signed miss-distance and ticket-killer analysis |
| POST | `/learning/error-analysis` | Store a structured post-result audit |
| GET | `/learning/weights/proposals` | List controlled learning proposals |
| POST | `/learning/weights/propose` | Generate evidence-gated, bounded proposals |
| POST | `/learning/weights/proposals/{id}/review` | Admin approve or reject a proposal |
| POST | `/learning/weights/proposals/{id}/rollback` | Admin roll back an applied proposal |
| GET | `/protocol/current` | Read the canonical protocol and superseded rules |
| GET | `/protocol/runs/{analysis_id}` | Read AIN/Strict Mode health for an analysis |
| GET | `/health` | API, database, provider mode, and protocol health |

## Integrity rules

- Every protected object is scoped to the authenticated user; client-supplied ownership is never trusted.
- Provider verification flags default to `false`. A live adapter must positively verify schedule, actual L5/L10, lineups, injuries, weather, starters/roles, motivation/rotation, home-away/travel, market movement, and the applicable sport sweep.
- Analysis records keep normalized input, an input hash, timestamps, protocol/model versions, reason codes, warnings, and invalidation conditions so the decision can be reproduced.
- A Lock Check is fresh and expiring. `CHANGE_REQUIRED` and `SKIP` block placement; warnings require explicit acknowledgement.
- A live cash-out action records `HOLD`, `CASH_OUT`, `PARTIAL_HEDGE`, `NOT_OFFERED`, or `NOT_APPLICABLE`. An actual action requires the offer and a verified reason; it never overwrites the final result or process grade.
- Learning proposals do not apply themselves. Approval and rollback routes require an admin account.

FastAPI publishes the full OpenAPI contract and interactive examples at `/docs`; that generated contract is canonical over this summary.
