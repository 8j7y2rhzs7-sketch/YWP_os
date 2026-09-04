# YWP Trusted Sources

Strict Mode may auto-verify research only from this certified list.

## MLB

| Source | Role | Used for |
| --- | --- | --- |
| MLB Stats API (`statsapi.mlb.com`) | Primary | Schedule, form, lineups, roster/injuries, weather, umpires, park/venue, bullpen workload |
| MLB.com Gameday | Reference link | Human-readable official game page on candidates |
| The Odds API | Market | Current sportsbook prices and multi-book consensus |
| Open-Meteo | Secondary weather | Backup only when MLB weather is not posted |
| YWP MLB Independent Model | Internal | Projection from official MLB facts; never from book price |

## WNBA / NBA / NFL / NHL / NCAAF / Soccer / KBO

| Source | Role | Used for |
| --- | --- | --- |
| ESPN Site API (`site.api.espn.com`) | Primary | Schedule, L5/L10 form, injuries, venue/indoor flag |
| The Odds API | Market | Current sportsbook prices and multi-book consensus |
| Open-Meteo | Secondary weather | Outdoor NFL / NCAAF / soccer / KBO when venue city is known |
| YWP Multi-Sport Independent Model | Internal | Projection from ESPN form + injuries; never from book price |

## Not trusted

- Random blogs / tip sheets
- Unauthenticated sportsbook HTML scrapes
- Social rumor without official confirmation
- Manufactured or sportsbook-implied probabilities used as YWP projections

## Protocol endpoint

Authenticated clients can read the live registry at:

`GET /api/v1/protocol/trusted-sources`

Optional filter:

`GET /api/v1/protocol/trusted-sources?sport=nfl`
