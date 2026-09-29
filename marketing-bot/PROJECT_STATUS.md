# YWP OS Marketing Bot — project status

Created: September 26, 2026

## Complete

- Cursor-ready Node/TypeScript project
- Approval-first dashboard
- YWP OS read-only marketing-feed contract
- FastAPI adapter template for the existing backend
- Strict VERIFIED/current/non-demo/publication-eligible checks
- Expiry recheck at draft approval and again at publication
- Black-and-gold 1080×1350 Instagram card renderer
- Caption generator with freshness and responsible-betting language
- Meta Instagram image publishing client
- Render and Docker deployment definitions
- Automated safety tests and sample rendered preview

## Deliberately locked

- `IG_PUBLISH_ENABLED` defaults to `false`.
- The bot cannot place wagers, edit Decision Cards, access sportsbook accounts, or read private ticket/bankroll data.
- Paid/boosted betting advertising is not enabled by this package.

## Backend wiring (done in YWP_os)

- `GET /api/v1/marketing/approved-cards`
- `POST /api/v1/marketing/rotate-token` (admin; DB-hashed scoped token)
- `POST /api/v1/marketing/tickets/{id}/publication-eligibility` (admin)
- See `SETUP.md`

## Remaining owner/setup work

1. Extract the package into the current YWP OS repository and open it in Cursor.
2. Run the included Cursor prompt to map the feed contract to the repository's current FastAPI models and authentication.
3. Create a scoped read-only service token for the bot.
4. Connect the `@ywpossports` Professional account through Meta's developer setup.
5. Store all credentials as environment variables and perform one controlled test.
6. Enable publishing only after the exact test card, caption, account, and Meta response are verified.

## Validation completed before packaging

- TypeScript typecheck: passed
- Production build: passed
- Safety tests: 4 passed
- Dashboard health endpoint: passed
- Dashboard HTML smoke test: passed
- PNG preview render: passed and visually inspected
