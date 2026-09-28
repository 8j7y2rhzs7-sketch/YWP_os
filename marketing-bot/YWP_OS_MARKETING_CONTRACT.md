# YWP OS → Marketing Bot contract

The marketing bot reads one authenticated, read-only endpoint from the existing YWP OS backend:

`GET /api/v1/marketing/approved-cards`

The route must return saved application truth. It must never recompute picks, invent missing fields, reinterpret another sportsbook's price as Hard Rock, or upgrade PARTIAL/REVIEW/DEMO data to VERIFIED.

```json
{
  "generatedAt": "2026-09-26T12:00:00-04:00",
  "cards": [
    {
      "id": "immutable-card-id",
      "sport": "MLB",
      "title": "Official Two-Pick Card",
      "status": "VERIFIED",
      "publicationEligible": true,
      "demo": false,
      "sportsbook": "Hard Rock",
      "eventStart": "2026-09-26T19:10:00-04:00",
      "verifiedAsOf": "2026-09-26T16:15:00-04:00",
      "expiresAt": "2026-09-26T18:55:00-04:00",
      "ywpScore": 84,
      "modelProbability": null,
      "dataQuality": "COMPLETE",
      "sourceVersion": "3.3.4",
      "legs": [
        {
          "id": "immutable-leg-id",
          "event": "Away Team at Home Team",
          "selection": "Home Team",
          "market": "Moneyline",
          "line": null,
          "price": "-135"
        }
      ]
    }
  ]
}
```

## Required backend rules

1. Require an existing authenticated service account or scoped read token.
2. Return only cards that the owner explicitly made publication-eligible.
3. Keep YWP Score, model probability, and data quality separate.
4. Include exact sport, teams/event, market scope, line, price, sportsbook, event time, timezone, source freshness, and expiry.
5. Preserve PASS/PARTIAL/REVIEW/DEMO/EXPIRED states; the bot will reject them.
6. Revoking publication eligibility must remove the card from future feed responses.
7. Do not expose bankroll, stake, account, ticket, private-user, provider-secret, or sportsbook-login data.

The included FastAPI file is an adapter template. Cursor must map it to the current repository models after comparing the active branch with release `android-v3.3.4`.
