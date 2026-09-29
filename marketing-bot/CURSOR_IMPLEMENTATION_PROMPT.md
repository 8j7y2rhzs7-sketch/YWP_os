# Cursor prompt — connect YWP OS Marketing Bot

Open the existing `YWP_os` repository in Cursor and add the extracted `YWP_OS_Marketing_Bot` folder without replacing the mobile or backend applications.

Before editing, identify the active branch, deployed backend version, and differences from release `android-v3.3.4` (`ffc46524dc1d8f61c797daf931fd1a34dc86bb22`) and backend comparison commit `65ac95128bad4403c9574a7803290d805d17d2a8`. Preserve all newer fixes. Do not start from an older `main` branch.

Implement the read-only contract in `YWP_OS_MARKETING_CONTRACT.md` using the repository's current FastAPI authentication, card, evidence, and leg models. Register the router under `/api/v1`. Use `integration/python_fastapi_marketing_router.py` as a behavioral template, not as copy-paste production code.

Hard requirements:

- The app remains the only source of pick/card truth.
- Export only immutable saved cards with VERIFIED status, complete current evidence, explicit owner publication eligibility, and a future expiry.
- Never export DEMO, PARTIAL, REVIEW, SKIP, EXPIRED, synthetic fallback, stale evidence, unsupported probability, or mismatched sportsbook data.
- Keep YWP Score, model probability, and data quality separate.
- Do not expose bankroll, stake, actual tickets, user PII, provider keys, or sportsbook credentials.
- Use a scoped service token and record access in backend audit logs.
- Keep Instagram publication approval-first. Do not create a background job that bypasses the bot's APPROVED state.
- Do not place bets, modify picks, settle tickets, or alter production settings.

Validation:

1. Add backend tests for authentication, eligible card export, stale card exclusion, demo exclusion, revoked eligibility, timezone/expiry handling, and secret-field absence.
2. Run the existing backend suite.
3. In this folder, run `npm install`, `npm run typecheck`, and `npm test`.
4. Copy `.env.example` to `.env`, configure a long `ADMIN_KEY`, backend URL and scoped token, and leave `IG_PUBLISH_ENABLED=false`.
5. Run `npm run dev`, open `http://localhost:8787`, and sync one sanitized test card.
6. Verify the rendered PNG and caption exactly match the test card.
7. Complete Meta professional-account/API setup and a private test before enabling Instagram publishing.

Return changed files, test results, remaining setup actions, and anything blocked. Do not claim a live Instagram post unless Meta returns the published media ID.
