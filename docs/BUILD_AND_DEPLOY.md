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

1. Confirm `ios.bundleIdentifier` / `android.package` in `mobile/app.json` (`com.ywpos.app`).
2. Install and authenticate EAS CLI (`npx eas-cli login`).
3. One-time: from `mobile/`, run `npx eas-cli init` so `extra.eas.projectId` is written into app config.
4. Apple requirements for device/TestFlight builds: Apple Developer Program membership, App Store Connect app record for `com.ywpos.app`, and EAS credentials (`npx eas-cli credentials -p ios`).

### Android APK (current sideload path)

```bash
cd mobile
npm run build:apk
```

### iOS / TestFlight

Full checklist: **[docs/IOS.md](./IOS.md)**.

```bash
cd mobile
npm run build:ios:preview
```

Install the resulting build on a registered iPhone, or submit to TestFlight after App Store Connect is linked:

```bash
npm run build:ios:production
npm run submit:ios
```

5. On a real iPhone verify: splash/font fallback, login restore, offline startup, tab safe-area, keyboard, deep links (`ywpos://`), slate → analyze → lock → place, graphic share sheet, result logging, and Whop/paywall only for non-provisioned accounts.
6. Production store binaries only after the production checklist is complete:

   ```bash
   npx eas-cli build --profile production --platform all
   ```

## Web deployment

```bash
cd mobile
npx expo export --platform web
```

Publish `mobile/dist` to the chosen static host and configure `EXPO_PUBLIC_API_URL` at build time. The API must use HTTPS and include that exact origin in `YWP_CORS_ORIGINS`.

## Live provider integration

Demo records are synthetic and explicitly labeled. A live launch requires licensed adapters for schedule, odds/markets, recent logs, lineups, injuries, weather, and settlement. Normalize provider output to `CandidateInput`; do not move provider keys into the client.

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
