# YWP Trusted Sources

Strict Mode may auto-verify research only from this certified list.

| Source | Role | Used for |
| --- | --- | --- |
| MLB Stats API (`statsapi.mlb.com`) | Primary | Schedule, form, lineups, roster/injuries, weather, umpires, park/venue, bullpen workload |
| MLB.com Gameday | Reference link | Human-readable official game page on candidates |
| The Odds API | Market | Current sportsbook prices and multi-book consensus |
| Open-Meteo | Secondary weather | Backup only when MLB weather is not posted |
| YWP MLB Independent Model | Internal | Projection from official MLB facts; never from book price |

## Not trusted

- Random blogs / tip sheets
- Unauthenticated sportsbook HTML scrapes
- Social rumor without official confirmation
- Manufactured or sportsbook-implied probabilities used as YWP projections

## Protocol endpoint

Authenticated clients can read the live registry at:

`GET /api/v1/protocol/trusted-sources`
