# YWP OS v3.0

YWP OS is a structured decision platform for sports analysis. It preserves capital, identifies measurable edge, controls variance, and records every outcome so the system can improve without overreacting to one result.

This repository is the complete runnable MVP source for iOS, Android, web, and the backend API. It includes:

- Email/password authentication with short-lived access tokens and rotating refresh tokens.
- User profile, timezone, risk profile, bankroll rules, and ledger.
- Structured slate ingestion with a demo provider and a clean adapter boundary for live data providers.
- The YWP decision pipeline: validation → implied probability → edge → risk → recommendation → learning.
- Official outputs: Max Bet, Elite 2, Core 3/4/5, Core Parlay, Cash Builder, Edge Plays, and Stay Away.
- Special outputs: Fortress, Handicap, No Stress, Scripted, Quick Cash, Chain Reaction, Ghostt, and Comeback.
- Correct ABC doctrine: A is the best available card, B uses different players/theses, and C is the best diversified combination of A and B.
- Per-play Follow, Skip, and Replace workflow with recorded skip reasons.
- Mandatory Lock Check with `LOCKED`, `WARNING`, `CHANGE_REQUIRED`, and `SKIP` outcomes.
- In-app result/process grading with CLV, signed miss distance, live-trigger and cash-out audit, ROI, confidence calibration, Miss-by-1 analysis, and pattern reporting.
- Controlled self-learning with evidence thresholds, bounded weight proposals, human approval, version history, and rollback—never silent automatic mutation.
- Current QA rules: thesis-exposure caps, first-start-back pitcher exclusions, no line escalation for payout, K-duration gates, filler-leg tax, two-path low-total validation, previous-game recency guard, bullpen-game volatility, and the soccer 90-minute/extra-time trap.
- Reproducible recommendation records with model version, reason codes, normalized input, and input hash.
- The exact supplied YWP crest, minimalist mark, app icon, splash art, and original decision-card references wired into Expo and the in-app 1080 × 1350 share-card generator.

## Architecture

```text
Expo universal app (iOS / Android / Web)
                 |
           REST / JSON API
                 |
FastAPI + YWP Decision/Lock/Ticket services
        |                       |
    PostgreSQL                Redis
        |
Provider adapters (demo now; live sports/odds/weather later)
```

The AI layer is optional and never acts as the source of truth. Deterministic validation, bankroll protection, auditability, and provider-supplied data remain outside the model.

## Run the full local stack

Requirements: Docker Desktop, Node.js 22, and npm.

1. Start the API, PostgreSQL, and Redis:

   ```bash
   docker compose up --build
   ```

2. In another terminal, start the universal app:

   ```bash
   cd mobile
   cp .env.example .env
   npm ci
   npm run start
   ```

3. Open the web option from Expo, or use a development build for iOS/Android. The bundled demo login is:

   ```text
   Email: demo@ywp-os.com
   Password: YwpDemo!2026
   ```

The demo account exists only when `YWP_DEMO_MODE=true`.

API documentation is available at `http://localhost:8000/docs`. Health is at `http://localhost:8000/api/v1/health`.

## Run without Docker

```bash
cd backend
cp ../.env.example .env
uv sync --extra dev
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --reload
```

For a zero-setup local database, set `DATABASE_URL=sqlite:///./ywp.db` and leave `REDIS_URL` blank.

## Connect live data

The app intentionally ships with demo data because no live-data credentials are embedded in source code. Implement a provider in `backend/app/services/providers.py`, then map its output to `CandidateInput`. Populate these server-side variables:

- `SPORTS_DATA_API_KEY`
- `ODDS_API_KEY`
- `WEATHER_API_KEY`
- League-specific keys such as `MLB_STATS_API_KEY`

Never expose provider keys through `EXPO_PUBLIC_*` variables.

## Before production

- Generate a cryptographically random `YWP_JWT_SECRET` of at least 32 bytes.
- Set `YWP_DEMO_MODE=false` and remove demo credentials from operational runbooks.
- Use managed PostgreSQL and Redis with encryption, backups, and private networking.
- Apply migrations with `alembic upgrade head` during deployment.
- Configure exact CORS origins and HTTPS.
- Add provider contracts and confirm their redistribution/display rights.
- Complete legal review for every state/country served, responsible-gaming controls, privacy policy, terms, age gating, and app-store requirements.
- Add rate limiting, WAF rules, secret management, monitoring, error reporting, and restore drills.
- Validate real-device builds with `npx expo-doctor@latest` and EAS development builds before store submission.

## Important product boundary

YWP OS is decision support, not a guarantee of outcomes and not a sportsbook. `PASS`/`SKIP` is a first-class result. Official picks remain canonical for a provider snapshot; a user's risk profile changes stake guidance, not which plays qualify. A user remains the final decision maker.

## Complete handoff map

- [Build and deployment](docs/BUILD_AND_DEPLOY.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API guide](docs/API.md)
- [Canonical YWP rules](docs/YWP_RULES.md)
- [Protocol changelog, upgrades, and removals](docs/PROTOCOL_CHANGELOG.md)
- [Brand system and exact asset mapping](docs/BRAND_SYSTEM.md)
- [Source manifest](docs/SOURCE_MANIFEST.md)
- [Production checklist](docs/PRODUCTION_CHECKLIST.md)
- [Release notes](RELEASE_NOTES.md)
