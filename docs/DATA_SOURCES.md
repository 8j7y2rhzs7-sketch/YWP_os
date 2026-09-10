# Multi-source fact cascade (non-MLB)

Rule: **The Odds API shows the play. Fact sources enrich it. Missing facts = PARTIAL, not hidden.**

| Sport | Schedule / form (tried in order) | Prices |
|---|---|---|
| MLB | MLB Stats API | The Odds API |
| NHL | NHL Web API → ESPN Site API | The Odds API |
| NBA / NFL / NCAAF / NCAAB / WNBA / soccer / KBO | ESPN Site API (when reachable) | The Odds API |
| Outdoor weather | Open-Meteo | — |

HTML sites (mykbostats, 365scores, marketing pages) are **not** trusted auto-verify sources. Official JSON APIs only.

If ESPN 403s on Render, priced candidates still return. Change the slate date when Odds has no events that day (e.g. KBO often posts next Korea calendar day).
