# YWP OS Marketing Bot — project status

Updated: September 26, 2026

## Complete

- One-tap **promo** creatives (not live tickets) — auto-APPROVED
- Optional Instagram publish when `IG_PUBLISH_ENABLED=true`
- Optional hands-off schedule via `PROMO_AUTO_INTERVAL_HOURS`
- Dashboard: Post promo / Generate only
- Black-and-gold 1080×1350 renderer + compliant captions
- Meta Instagram image publishing client
- Backend: marketing feed + admin rotate-token (for legacy sync if ever needed)
- Safety tests for promo + caption gates

## Deliberately locked

- `IG_PUBLISH_ENABLED` defaults to `false` until Meta is wired once.
- Bot does not place wagers, edit Decision Cards, or read private ticket/bankroll data.
- Paid/boosted betting advertising is not enabled by this package.
- Live-ticket marketing is not the product path (no per-post eligibility / Lock Check ritual).

## Remaining owner work (one-time)

1. Meta Professional + app credentials into env.
2. HTTPS `PUBLIC_BASE_URL` the bot can serve images from.
3. `IG_PUBLISH_ENABLED=true` after one successful test publish.
4. Optional: `PROMO_AUTO_INTERVAL_HOURS=24` so the bot posts without clicks.

No per-post verification after that.
