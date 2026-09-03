# Production Checklist

## Data and decisions

- [ ] Live provider adapters pass contract tests and freshness checks.
- [ ] Lineups, starters, injuries, weather, odds, and market availability have independent timestamps.
- [ ] No provider field is silently fabricated.
- [ ] Official cards are reproducible from stored inputs, model version, and weights.
- [ ] Lock Check reads a fresh snapshot and expires quickly.
- [ ] Settlement feeds are reconciled against sportsbook rules.
- [ ] Every supported sport has provider contract tests for its sport-specific Strict Mode gates.
- [ ] Risk-profile changes alter stake guidance only, never the canonical official card.
- [ ] Miss-by-1 reports distinguish signed line miss, ticket killer, final leg, repeated thesis, and unique theses failed.
- [ ] Learning proposals enforce sample thresholds, bounded deltas, admin review, version history, monitoring, and rollback.
- [ ] Live/cash-out actions use a fresh timestamped state, compare offer to fair remaining value, store action/offer/time/reason, and never become a chase path.

## Security and privacy

- [ ] Unique production secret is stored in a secret manager.
- [ ] Database/Redis use private networking, TLS, backups, and least-privilege users.
- [ ] CORS allowlist contains exact production origins.
- [ ] Rate limits, abuse protection, audit retention, alerts, and incident response are configured.
- [ ] Privacy policy, deletion/export workflows, and retention periods are implemented.
- [ ] Penetration test and dependency/security scans pass.

## Responsible operation

- [ ] Legal counsel approves jurisdictions, product language, and data/provider licenses.
- [ ] Age gate, self-exclusion links, time/spend controls, and crisis/tilt interventions are present where required.
- [ ] Marketing never describes probabilistic recommendations as guaranteed wins.
- [ ] Users can see assumptions, risk, invalidation conditions, and `PASS` decisions.
- [ ] Deposit/spend/time limits, loss-pause behavior, and responsible-gaming resources work on every client.

## Brand, graphics, and accessibility

- [ ] Supplied crest/minimal logo are used from `mobile/assets/brand`; no generated placeholder replaces them.
- [ ] Native app icon, Android adaptive icon, splash screen, and web favicon render on target devices.
- [ ] PLAY and PASS share graphics are generated from the stored card object and include protocol/date/responsible language.
- [ ] Historical reference-card content cannot be imported as a current recommendation.
- [ ] Text contrast, non-color status labels, screen-reader labels, reduced-motion behavior, dynamic text, and 44-point touch targets pass QA.

## Release

- [ ] Alembic migrations run successfully on a production-like snapshot.
- [ ] Backend lint/tests/migration check, mobile typecheck, Expo Doctor, static web export, and real-device smoke tests pass.
- [ ] Monitoring covers API latency/errors, provider freshness, failed Lock Checks, auth anomalies, and settlement drift.
- [ ] Store signing, privacy labels, screenshots, support URL, and account-deletion route are complete.
