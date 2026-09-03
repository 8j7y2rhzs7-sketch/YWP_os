# YWP verified-live engine fix

Applied on `cursor/verified-live-patches-4fbe` without replacing the later energy, learning, ticket-editor, or sport-visual work.

## What this fixes

1. Real team names no longer imply that the research is complete.
2. Every slate and analysis is labeled `DEMO`, `PARTIAL`, or `VERIFIED`.
3. Sportsbook implied probability is identified as a market price, not an independent YWP projection.
4. Strict Mode blocks an official play when required YWP research is missing.
5. Production no longer silently falls back to synthetic/demo data if a live provider fails.
6. The Android production build no longer silently points to `localhost`.
7. `official_pass_count` now counts qualified (non-SKIP) plays. `official_pass` remains true only when every candidate is SKIP.

## Status meanings

- `DEMO`: synthetic records used only to test the interface.
- `PARTIAL`: real schedule or odds are present, but at least one required research input is missing, or the probability is only a sportsbook implied price. The engine may calculate diagnostics, but Strict Mode returns `SKIP`.
- `VERIFIED`: the independent probability and the complete YWP research checklist were supplied. Only this state is eligible for an official play.

## Render settings

Set these on the deployed Render service, not inside the Android app:

```text
YWP_ENV=production
YWP_DEMO_MODE=false
ODDS_API_KEY=<real Odds API key>
DATABASE_URL=<Render PostgreSQL connection>
YWP_JWT_SECRET=<generated secret of at least 32 bytes>
```

After deploy, open `https://ywp-os-api.onrender.com/api/v1/health` and confirm `demo_mode` is `false` and `version` is `3.2.0` or later.

## Android build setting

```text
EXPO_PUBLIC_API_URL=https://ywp-os-api.onrender.com/api/v1
```

The public URL is safe in the app. Provider keys, JWT secrets, database credentials, and Whop secrets are not.
