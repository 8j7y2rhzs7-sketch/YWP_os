# Finish Marketing Bot setup

Backend API **3.3.59+** supports admin token rotation without Render dashboard access.

## 1. Mint the scoped feed token (one-time)

```bash
# Login as an admin user, then:
curl -sS -X POST https://ywp-os-api.onrender.com/api/v1/marketing/rotate-token \
  -H "Authorization: Bearer $ADMIN_JWT"
```

Copy the returned `token` into `marketing-bot/.env` as `YWP_OS_API_TOKEN`.  
Optional: also set `YWP_MARKETING_SERVICE_TOKEN` on Render to the same value.

## 2. Mark a Decision Card publication-eligible

Only locked/saved tickets with VERIFIED legs export. As admin:

```bash
curl -sS -X POST \
  "https://ywp-os-api.onrender.com/api/v1/marketing/tickets/$TICKET_ID/publication-eligibility" \
  -H "Authorization: Bearer $ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{"eligible":true,"expires_at":"2026-09-27T23:00:00Z"}'
```

Revoke anytime with `{"eligible":false}`.

## 3. Run the bot dashboard (publish still off)

```bash
cd marketing-bot
cp .env.example .env
# set ADMIN_KEY (long random) + YWP_OS_API_TOKEN from step 1
# keep IG_PUBLISH_ENABLED=false
npm install
npm run dev
```

Open `http://localhost:8787`, enter the admin key, **Sync YWP OS**.

## 4. Meta Instagram (owner-only — required before any public post)

1. Convert `@ywpossports` to a Professional account if needed.
2. Create a Meta app with Instagram content publishing permissions.
3. Put `IG_USER_ID` + `IG_ACCESS_TOKEN` in env; set `PUBLIC_BASE_URL` to a reachable HTTPS host.
4. Private test publish once, confirm Meta returns a media ID.
5. Only then set `IG_PUBLISH_ENABLED=true`.

Paid/boosted betting ads are out of scope for this bot.
