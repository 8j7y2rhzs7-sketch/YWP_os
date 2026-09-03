# YWP OS v3.1 Verified Live MLB Release

App version: `3.1.0`  
Model version: `ywp-sports-v3.1.0`  
Protocol version: `2026.09.03` (unchanged canonical protocol)

## v3.1 additions and corrections

- Added official MLB Stats API sourcing for schedule, actual L5/L10 scores, probable starters,
  roster availability, posted batting orders, game weather, and recent bullpen workload.
- Added an independent MLB performance model. Sportsbook implied probability is no longer used as
  the recommendation probability.
- Removed manufactured pitcher strikeout lines and the hard-coded `-115` prop price. A K candidate
  now requires a real provider line and price; automatic prop requests are quota-capped and off by
  default.
- Added `DEMO` / `PARTIAL` / `VERIFIED` readiness, required-source gaps, source URLs, and strict
  fail-closed behavior when research is incomplete.
- Preserved the canonical AIN, Miss-by-1, loss-audit, ABC, ticket, bankroll, and controlled
  self-learning protocols.
- Corrected shared-nickname odds matching, MLB innings notation (`5.2` = 5⅔ innings), and the
  `official_pass_count` response field.
- Removed production demo fallback and production localhost fallback.

## v3.0 base release

Protocol version: `2026.09.03`

This handoff is the complete runnable MVP source for the universal Expo client and FastAPI backend. It consolidates the current protocols, prior loss-audit upgrades, corrected ABC doctrine, exact supplied brand assets, controlled learning workflow, database migration, deployment files, tests, and operating documentation.

## Included in this release

- iOS, Android, and static-web client with login, Command Center, Slate Runner, Decision Board, all card families, Ticket Vault, Lock Center, Learning/Miss-by-1 views, settings, and PNG share graphics.
- API with authentication, bankroll ledger, normalized slates, deterministic analysis, Ticket Builder, leg actions, Lock Check, immutable result/live-cashout grading, performance/calibration/pattern reports, controlled weight proposals, approval, and rollback.
- Canonical AIN, Strict Mode, Vision/cushion, Miss-by-1, no-forcing, sport-specific, bankroll, live/cashout, QA/loss-audit, and self-learning rules.
- Exact supplied crest, minimalist logo, native app icon/splash assets, untouched originals, and cleaned visual-reference cards.
- PostgreSQL/SQLite models, Alembic migration, Docker Compose, demo provider/seed, dependency locks, CI, and production checklist.

## Upgraded or corrected

- Missing verification now fails closed instead of appearing confirmed.
- Official picks no longer change with a user's risk profile; only stake guidance changes.
- Quick Cash and Chain Reaction are first-class built cards and learning fields.
- NBA, NCAAF, and KBO protocol checks are represented alongside MLB, WNBA/basketball, soccer, and football gates.
- Learning requires repeated evidence, bounded proposals, human approval, a new version, and rollback support.
- Live/cash-out audit now records action, offer, time, verified reason, trigger result, and process grade; the mobile app includes the complete entry workflow.
- PASS/SKIP remains official and the system never manufactures a replacement to fill a card.

## Removed or superseded

- Forced two-pick output, incorrect ABC meanings, payout-driven line escalation, random “risky” cards, narrative-only projections, fabricated missing data, one-result self-modification, and loss-chasing behavior.

## Deployment boundary

Live provider keys, sportsbook credentials, signing certificates, production domains, jurisdiction-specific legal language, and data licenses are intentionally not included. Add them through secret management only after the production checklist is complete.
