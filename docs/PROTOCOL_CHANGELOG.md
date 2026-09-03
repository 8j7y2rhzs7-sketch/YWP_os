# YWP Protocol Changelog and Canonical State

## Canonical release

`2026.09.03` is the only active protocol version in this package. The runtime exposes it at `GET /api/v1/protocol/current`, stores the version on every recommendation and health run, and shows it in the app. Older advice cannot silently override it.

## Required global workflow

1. Verify schedule, identity, competition, market period, and data freshness.
2. Label sources and unknowns; never manufacture a player, line, injury, statistic, starter, or result.
3. Run the seven-point AIN sweep: matchup, actual L5/L10, situational angles, injury/rest, pace/tempo, H2H context, and market value.
4. Run the applicable sport-specific Strict Mode sweep.
5. Calculate implied probability, adjusted probability, edge, expected value, confidence, YIS, Vision, reliability, stability, variance, and Miss-by-1 risk.
6. Test role/workload, multiple cashing paths, cushion, line movement, motivation/rotation, home/away/travel, and game script.
7. Show safer and higher-upside alternatives without escalating a line merely for payout.
8. Eliminate the weakest leg, repeated thesis, unintended correlation, filler leg, stale-input case, and critical ticket-killer risk.
9. Build official and special cards only from qualified plays. If no play qualifies, return PASS.
10. Run a fresh Lock Check immediately before placement.
11. For live/cash-out action, refresh the game/market state, reprice the remaining thesis, compare the offer with fair value, and never chase or react to sunk cost.
12. Grade result and process separately; record CLV, signed miss distance, root cause, assumptions, unexpected events, Quick Cash/Chain Reaction/live-path result, cash-out audit, and lesson.
13. Create learning proposals only from adequate repeated evidence, with bounded deltas, human approval, versions, and rollback.

## Current card definitions

| Card | Canonical meaning |
|---|---|
| Max Bet | One strongest qualified play; never force a second lock |
| Elite 2 | Two strongest diversified plays when both qualify |
| Core 3/4/5 | Qualified official cards at the stated leg count |
| Core Parlay | Best diversified core within the configured maximum |
| Cash Builder | Lowest Miss-by-1 risk and variance among qualified plays |
| Edge Plays | Highest genuine EV; not merely plus-money selections |
| Fortress | Best low-hidden-risk plays across categories |
| Handicap | Largest measured Vision/cushion advantages |
| No Stress | Lowest variance and strongest role/cushion profile |
| Scripted | Independently supported plays with aligned game scripts |
| Quick Cash | Early-settlement or early-game edges tracked separately |
| Chain Reaction | Explicit trigger and downstream path; result is logged |
| Ghostt | Higher upside from real mispricing, never random extra legs or underdogs |
| Comeback | Best current edges; previous losses never increase action or stake |
| Ticket A | Best available picks |
| Ticket B | Best picks using different players/theses from A |
| Ticket C | Best diversified picks selected from A and B |
| Stay Away | Official failed-gate/PASS list with reasons retained |

## Loss-audit upgrades now enforced

- Cross-ticket thesis exposure detection and bankroll cap.
- First-start-back pitcher strikeout-over exclusion without confirmed normal workload.
- Pitcher K duration gate: expected batters faced, pitches, innings, contact, and pull context.
- No higher alternate line solely to inflate payout.
- Filler-leg tax for heavy juice without independent value.
- Low alternate over needs two credible scoring paths or one verified dominant path.
- Previous-game recency cannot become the projection by itself.
- Opener/bullpen games require current sequencing and availability.
- Soccer knockout analysis distinguishes regulation moneyline from to-qualify and checks aggregate, draw, extra time, and penalties.
- Critical Miss-by-1 risk is quarantined; a safer verified line or removal is required.
- Slips lost and unique theses failed are counted separately.

## Superseded or removed behavior

- Incorrect ABC interpretations.
- Forced two-pick output when only one play qualifies.
- Treating heavy juice as proof of safety.
- Building a “risky” card by lengthening a safe card or stacking underdogs.
- Using an old score, reputation, or public narrative as a projection.
- Guessing unavailable schedules, lines, players, injury status, or recent logs.
- Changing official picks according to personal risk profile; personal settings affect stake sizing only.
- Automatic learning from one result.
- Blaming completed non-causal legs for the loss of a dead ticket.
- Fear-based cash-outs, sunk-cost holds, and live additions intended only to rescue a losing pregame position.
