# Build and Deployment Guide

## Local full stack

Requirements: Docker Desktop, Node.js 22, and npm.

```bash
docker compose up --build
```

The API container waits for PostgreSQL, applies Alembic migrations, and creates the demo account only while `YWP_DEMO_MODE=true`.

In a second terminal:

```bash
cd mobile
cp .env.example .env
npm ci
npm run start
```

Demo credentials:

```text
demo@ywp-os.com
YwpDemo!2026
```

For a physical phone, replace `localhost` in `mobile/.env` with the computer's LAN IP. Never put provider secrets in an `EXPO_PUBLIC_*` variable.

## Backend without Docker

```bash
cd backend
cp ../.env.example .env
uv sync --extra dev
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --reload
```

Use `DATABASE_URL=sqlite:///./ywp.db` for the zero-infrastructure development path.

## Validation

```bash
cd backend
uv run ruff format --check app tests migrations
uv run ruff check app tests migrations
uv run pytest --cov=app

cd ../mobile
npm run typecheck
npx expo-doctor@latest
npx expo export --platform web
```

The delivered package was validated with seven backend tests at 82% statement coverage, strict TypeScript, all 21 Expo Doctor checks, and a successful 20-route static web export.

## Native builds

Keep Android and iOS release pipelines separate: **[docs/RELEASE_CHANNELS.md](./RELEASE_CHANNELS.md)**.

- iOS / Expo Go / TestFlight: **[docs/IOS.md](./IOS.md)**
- Paid Android Whop delivery: **[docs/WHOP_PAID_DELIVERY.md](./WHOP_PAID_DELIVERY.md)**

### Try on a phone now (Expo Go, free)

```bash
cd mobile
npm ci
npm run start:phone
```

Scan the QR with Expo Go. Uses the production API from `.env.production`.

### Android APK (Whop sideload)

```bash
cd mobile
npm run build:apk
```

Publish only under GitHub tag `android-vX.Y.Z`. Do not use EAS for Android in this repo.

### iOS TestFlight (needs Apple Developer + EAS login)

1. Change `ios.bundleIdentifier` / `android.package` in `mobile/app.json` only if `com.ywpos.app` is unavailable.
2. `npx eas-cli login` then `npx eas-cli init` and `npx eas-cli credentials -p ios`.
3. `npm run build:ios:preview` then TestFlight.
4. Production: `npm run build:ios:production` then `npm run submit:ios`.

Test login, token rotation, slate run, PASS state, cards, ticket edits, Lock Check, graphic export, result grading, paywall Sync, and account controls on real devices before store submission.
## Web deployment

```bash
cd mobile
npx expo export --platform web
```

Publish `mobile/dist` to the chosen static host and configure `EXPO_PUBLIC_API_URL` at build time. The API must use HTTPS and include that exact origin in `YWP_CORS_ORIGINS`.

## Live provider integration

Demo records are synthetic and explicitly labeled. Non-MLB live slates use a
**multi-source cascade** — see **[docs/DATA_SOURCES.md](./DATA_SOURCES.md)**.
Odds-priced plays still show when fact feeds (ESPN/NHL) fail; readiness stays PARTIAL.

Every live candidate must explicitly confirm the schedule, universe scan, actual L5/L10, lineup, injuries, weather, starter/role, motivation/rotation, home-away/travel, market movement, and applicable sport-specific sweep. Omitted verification flags default to `false`.

## Deployment order

1. Provision private PostgreSQL and Redis.
2. Store secrets in the deployment platform's secret manager.
3. Run migrations.
4. Deploy API and verify `/api/v1/health`.
5. Run provider contract and Lock Check freshness tests.
6. Build mobile/web clients against the HTTPS API.
7. Complete legal, privacy, responsible-gaming, accessibility, security, store, and real-device review.
8. Release gradually with monitoring and rollback.
