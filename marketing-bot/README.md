# YWP OS Marketing Bot

Instagram marketing for YWP OS SPORTS (`@ywpossports`). Day-to-day posts are **brand promo templates** — not live tickets. Templates are pre-vetted: create (and optionally publish) in one tap. Meta is connected **once**; you do not re-verify each post.

## How it works

1. Hit **Post promo** (or let `PROMO_AUTO_INTERVAL_HOURS` run).
2. Bot renders a black-and-gold 1080×1350 creative + compliant caption.
3. Status is `APPROVED` automatically (promo templates, not live bets).
4. If `IG_PUBLISH_ENABLED=true`, the same action publishes through Meta's official Instagram API.

## Safety model

- Publishing stays off until you flip `IG_PUBLISH_ENABLED` after Meta credentials are set.
- Promo captions block certainty language (“guaranteed,” “can't lose,” “100%,” etc.).
- Every caption includes freshness, 21+, responsible-betting, and no-guarantee language.
- Marketing never posts private tickets, bankroll, or live Decision Cards by default.
- Optional legacy `/api/sync` can still pull an approved-cards feed; that path is not the day-to-day bot.

## Quick start

```bash
cd marketing-bot
cp .env.example .env   # set a long random ADMIN_KEY
npm install
npm test
npm run dev
```

Open `http://localhost:8787` → **Post promo**.

## Meta setup (once)

Use an Instagram Professional account and Meta content-publishing permissions. Store `IG_USER_ID`, `IG_ACCESS_TOKEN`, `META_GRAPH_VERSION`, and an HTTPS `PUBLIC_BASE_URL` (Meta fetches the image from that URL). Then set `IG_PUBLISH_ENABLED=true`. Optional: `PROMO_AUTO_INTERVAL_HOURS=24` for scheduled posts with zero clicks.

Paid/boosted betting ads are separate and may need Meta's written permission.

## Deployment

File-backed queue is fine for a single-instance MVP. On Render, use a persistent disk (or swap `DraftStore` to the YWP OS DB) before relying on long-term history. Keep secrets in env vars only.

See `SETUP.md` for the short operator checklist.
