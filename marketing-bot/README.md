# YWP OS Marketing Bot

Cursor-ready, approval-first Instagram marketing for YWP OS SPORTS (`@ywpossports`). It reads publication-eligible Decision Cards from the existing YWP OS backend, generates a black-and-gold 1080×1350 post and compliant caption, waits for owner approval, then publishes through Meta's official Instagram API.

## Safety model

- Publishing is disabled by default.
- A card must be VERIFIED, non-demo, current, unexpired, complete, and explicitly publication-eligible.
- The bot rechecks the card at approval and publication time.
- Certainty language such as “guaranteed,” “can't lose,” “100%,” or “lock” is blocked.
- Every caption includes freshness, 21+, responsible-betting language, and no-guarantee language.
- The marketing feed is read-only and excludes bankroll, private tickets, user information, and credentials.

## What is included

- Local web dashboard with Sync, Approve, Publish, and Copy Caption actions
- Strict YWP OS feed schema and expiry checks
- Premium black-and-gold PNG renderer
- Official Instagram image-container and publish calls
- File-backed draft queue for the first MVP
- FastAPI integration contract and Cursor implementation prompt
- Render/Docker deployment files and automated safety tests

## Quick start in Cursor

1. Extract this folder into the current YWP OS repository.
2. Read `CURSOR_IMPLEMENTATION_PROMPT.md` and `YWP_OS_MARKETING_CONTRACT.md`.
3. Connect the backend route using the current repository models and authentication.
4. Copy `.env.example` to `.env` and set a long random `ADMIN_KEY`.
5. Keep `IG_PUBLISH_ENABLED=false` during setup.
6. Run:

```bash
npm install
npm run typecheck
npm test
npm run preview
npm run dev
```

7. Open `http://localhost:8787`, enter the admin key, and choose **Sync YWP OS**.

## Meta setup

Use an Instagram Professional account and Meta's official content-publishing permissions. Put the resulting Instagram user ID and access token in environment variables; never commit them. Confirm the current supported Graph API version in Meta's developer dashboard and set `META_GRAPH_VERSION` accordingly. The public deployment URL must be configured as `PUBLIC_BASE_URL` because Meta fetches the generated image from that URL.

Only after a test card renders correctly and Meta setup is complete should `IG_PUBLISH_ENABLED` be changed to `true`. Paid or boosted betting advertising is separate from organic publishing and may require Meta's prior written permission.

## Deployment notes

The included file-backed queue is suitable for a single-instance MVP and local Cursor testing. On Render, attach a persistent disk or replace `DraftStore` with the existing YWP OS database before relying on long-term history. Store every secret in deployment environment variables.

## Next controlled upgrade

After the image workflow is proven, add separate Story/Reel templates, performance insights, scheduled approval windows, and verified win/loss recap cards. Keep owner approval as the final publication gate until the workflow has a reliable history.
