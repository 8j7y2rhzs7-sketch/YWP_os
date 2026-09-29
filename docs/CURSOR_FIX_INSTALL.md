# YWP verified-live MLB fix for Cursor

This overlay is based on the Cursor branch `cursor/deploy-backend-4fbe`. Copy the overlay into the
root of that repository, preserving every folder path, then commit and redeploy.

## What actually calculates the picks

The Android app does **not** calculate the board, and Render does not supply sports facts. Render
hosts the Python backend. The backend now performs the work in this order:

1. `mlb_provider.py` downloads official schedule, starter, L5/L10, roster-status, lineup, weather,
   and bullpen-workload facts from MLB Stats API endpoints.
2. `mlb_model.py` creates a transparent probability from those MLB facts without looking at the
   sportsbook odds.
3. `odds_provider.py` gets the actual offered line and price from The Odds API.
4. `live_mlb_slate.py` compares the independent model probability with that price.
5. `decision_engine.py` applies AIN, Strict Mode, Miss-by-1, workload, research-completeness, value,
   and safety gates.
6. The Android app displays the result and can open the attached MLB source URL.

MLB supplies baseball facts; it does not supply Hard Rock/DraftKings/FanDuel prices. Do not scrape
the visible MLB.com page from the phone. The backend uses the official MLB data endpoint and keeps
all provider credentials on Render.

## Fixes included

1. Real team names no longer imply that the research is complete.
2. Every slate and analysis is labeled `DEMO`, `PARTIAL`, or `VERIFIED`.
3. MLB moneyline, total, and run-line probabilities now come from an independent performance
   model—not the sportsbook implied probability.
4. Pitcher strikeout candidates require a real posted prop line and price. The old manufactured
   `-115` price and model-created betting line are removed.
5. Strict Mode blocks an official play when any required YWP verification is missing.
6. The full self-learning protocol remains approval-gated and sample-size limited.
7. The Miss-by-1 protocol remains active and uses actual L5/L10 results and cushion.
8. Production no longer silently falls back to synthetic records after a live-provider failure.
9. The Android production build cannot silently point to `localhost`.
10. The incorrect `official_pass_count` calculation is fixed.
11. Exact-team matching now prevents shared nicknames such as White Sox/Red Sox from receiving the
    opponent's price.
12. Source URLs survive analysis storage and appear on raw candidates and recommendation cards.

## Data-source map

| Input | Source | Used for |
| --- | --- | --- |
| Schedule, teams, venue, probable starters | MLB Stats API | Full-slate universe and starter check |
| Team L5/L10 scores and run differential | MLB Stats API | Current form and model probability |
| 40-man roster status | MLB Stats API | Injury/unavailability verification |
| Posted batting orders and game weather | MLB live feed | Lineup and conditions check |
| Recent reliever appearances/pitches | MLB box scores | Bullpen workload and rotation check |
| Moneyline, spread, total, optional K prop | The Odds API | Actual market line/price only |
| Recommendation probability | YWP MLB model | Independent calculation |

The MLB endpoints used by this adapter are currently public and need no key. A commercial product
owner should still review MLB's terms and obtain any required permission or data license before
distribution.

## Files in this overlay

- `backend/app/core/config.py`
- `backend/pyproject.toml`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/api/health.py`
- `backend/app/api/sports.py`
- `backend/app/services/readiness.py`
- `backend/app/services/decision_engine.py`
- `backend/app/services/live_mlb_slate.py`
- `backend/app/services/mlb_model.py`
- `backend/app/services/mlb_provider.py`
- `backend/app/services/odds_provider.py`
- `backend/app/services/live_wnba_slate.py`
- `backend/app/services/live_generic_slate.py`
- `backend/app/services/providers.py`
- `backend/tests/test_decision_engine.py`
- `backend/tests/test_live_mlb_slate.py`
- `backend/tests/test_mlb_model.py`
- `backend/tests/test_mlb_provider.py`
- `backend/tests/test_odds_provider.py`
- `mobile/src/lib/api.ts`
- `mobile/src/types.ts`
- `mobile/src/components/RecommendationCard.tsx`
- `mobile/app/(tabs)/slate.tsx`
- `mobile/.env.production.example`
- `render.yaml`
- `backend/uv.lock`
- `RELEASE_NOTES.md`
- `examples/2026-09-03-board.example.json`

Copy all of them together because the API response and Android TypeScript types are one contract.

## Render settings

Set these on the deployed Render service, not in the Android app:

```text
YWP_ENV=production
YWP_DEMO_MODE=false
ODDS_API_KEY=<real Odds API key>
DATABASE_URL=<Render PostgreSQL connection>
YWP_JWT_SECRET=<generated secret of at least 32 bytes>
YWP_MLB_PROPS_ENABLED=false
YWP_MLB_MAX_PROP_EVENTS=4
```

Pitcher props are off by default so refreshing the slate cannot unexpectedly burn event-prop API
quota. Turn `YWP_MLB_PROPS_ENABLED=true` on only when you want automatic strikeout markets. The
maximum limits attempted prop-event requests per slate refresh; it never manufactures a prop when
the provider has none.

Keep provider keys private. Never put a secret in an `EXPO_PUBLIC_` variable.

After redeploying, open:

```text
https://YOUR-RENDER-SERVICE.onrender.com/api/v1/health
https://YOUR-RENDER-SERVICE.onrender.com/api/v1/health/providers
```

Confirm `demo_mode` is `false`, `mlb.ok` is `true`, and `odds.ok` is `true`. If MLB is connected but
odds is degraded, the backend correctly returns no actionable MLB candidates because no real price
is available.

## Android build setting

Set this during the Expo/EAS production build:

```text
EXPO_PUBLIC_API_URL=https://YOUR-RENDER-SERVICE.onrender.com/api/v1
```

The public backend URL is safe in the app. Odds keys, JWT secrets, database credentials, and Whop
secrets are not.

## Status meanings

- `DEMO`: synthetic records used only for interface testing.
- `PARTIAL`: real MLB/market data and a real model calculation exist, but one or more required
  checks—commonly posted lineups, umpire/park grading, motivation context, or opening-to-current
  market movement—are not verified. The engine calculates diagnostics but Strict Mode returns
  `SKIP`.
- `VERIFIED`: an independent probability and every required current YWP research check are supplied.
  Only this state is eligible for an official play.

This distinction is deliberate: showing real teams proves the schedule feed works; it does not prove
that all research is complete.

## Validation

From `backend`:

```bash
uv sync --extra dev
uv run ruff check app tests migrations
uv run pytest
```

From `mobile` after installing its locked dependencies:

```bash
npm ci
npm run typecheck
npx expo-doctor@latest
```

The overlay passes all **29 backend tests** and the changed Python files pass Ruff. The live MLB
schedule endpoint returned nine real games for the September 3 regression check. The new Android
source-link code type-checks; a complete mobile check in the build environment still requires the
locked NetInfo, Clipboard, and AsyncStorage packages to be installed by `npm ci`.
