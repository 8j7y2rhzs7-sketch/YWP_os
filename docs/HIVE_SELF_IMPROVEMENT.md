# Hive self-improvement (second loop)

Hive already calibrates picks from settled outcomes. The **self-improvement loop**
makes Hive invent better *tactics* for that calibration so humans do not have to
brainstorm every upgrade.

## Loops

| Loop | Job |
|---|---|
| Learning | Bounded probability blend from bucket evidence |
| Self-improvement | Invent → simulate on history → promote only if better |

## Safety rules

- Never train on Hive-adjusted probabilities as ground truth (uses base `model_probability` + outcome).
- Never override research SKIP / constitutional gates.
- Policy search is bounded (shift ≤ 5%, min_sample 20–120, scale 0.5–1.5).
- Promotion requires clear leave-one-out Brier improvement (ε).
- Every cycle is versioned in `hive_model_snapshots` with an English explanation.
- Active policy is rollbackable by writing a prior policy snapshot.

## When it runs

- Automatically after Sync Scores / settle when enough new Hive outcomes map (`YWP_HIVE_SELF_IMPROVE_MIN_MAPPED`, default 5).
- Manually via `POST /api/v1/hive/self-improve/run`.

## API

- `GET /api/v1/hive/self-improve/policy` — active tactics
- `GET /api/v1/hive/self-improve/cycles` — recent invent/simulate/promote runs
- `POST /api/v1/hive/self-improve/run` — run one reflection cycle

## Idea menu (bounded creativity)

Each cycle mutates the current policy within caps:

- tighten / loosen shift bound
- raise / lower min sample
- more conservative / aggressive shift scale
- inhibit worst-calibrated bucket
- clear inhibits

Winning ideas become the live analyze blend policy.
