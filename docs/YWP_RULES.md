# Canonical YWP Rules

## Constitutional rules

1. Capital preservation comes first.
2. Expected value matters more than raw win rate.
3. Probability comes before prediction; guarantees are prohibited.
4. Losses are never chased.
5. Results create learning data, not automatic overreaction.
6. Process quality is graded separately from outcome.
7. Every recommendation must be explainable.
8. Official picks are identical for the same verified provider snapshot; personal risk settings change stake guidance only.
9. `PASS` and `SKIP` are successful protocol outcomes when the gates do not clear.

## Recommendation gates

- Missing or unreliable data lowers confidence or creates `SKIP`.
- No measurable edge means `PASS`, even when a team is likely to win.
- Safer alternatives, invalidation conditions, and live triggers travel with each play.
- Odds price, lineup, injuries, rest, motivation, venue, matchup, market movement, weather, and sport-specific context must be represented by provider data or marked missing.
- 95–97 confidence is rare. The engine intentionally caps normal recommendations at 97.

## AIN and Strict Mode

- AIN verifies matchup, actual L5/L10 form, situational angles, injury/rest, pace or tempo, H2H context, and market value.
- Strict Mode then verifies schedule identity, full slate/universe scan, role/workload, lineup/starter status, weather where applicable, motivation/rotation, venue/travel, line movement, current price, game script, and the applicable sport-specific gates.
- Unknown is not the same as cleared. Missing verification defaults to `false`, reduces health, and can force `SKIP`.
- Vision measures usable cushion around the offered line. A high model projection without cushion is not treated as safe.

## Current loss-audit protections

- One player/market thesis may appear on only one cash ticket unless total exposure is intentionally declared and capped.
- A pitcher strikeout over is an automatic no-bet in his first MLB appearance after an IL stint unless a normal workload is explicitly confirmed.
- A higher alternate line cannot be added merely to improve payout.
- Pitcher strikeout overs require expected batters faced, pitch count, innings probability, opponent contact profile, and manager-pull context.
- A heavily juiced filler leg must earn its place through current data and value.
- Low alternate overs require two independently credible scoring paths or one verified path capable of carrying the total.
- The prior game's scoring is context, never a projection by itself.
- Opener/bullpen games receive a volatility downgrade unless availability and sequencing are verified.
- Soccer knockout picks distinguish 90-minute moneyline from to-qualify markets and flag draw/extra-time traps.

## Miss-by-1 protocol

- Record signed miss distance against the played line, not only win/loss.
- Track whether the play killed a ticket, died on the final leg, shared a thesis with another loss, or failed after an avoidable line escalation.
- Separate slips lost from unique theses failed so duplicated exposure is visible.
- Quarantine critical Miss-by-1 risk unless a safer verified line preserves real edge; otherwise remove the leg.
- Segment review by sport, market, player/team, line band, script, role/workload, card type, and Quick Cash/Chain Reaction state.
- A narrow miss is not proof that the original process was good. Process, variance, assumptions, closing-line value, and unexpected events are graded separately.

## Self-learning protocol

1. Store the result, price and line CLV, signed miss distance, process grade, variance grade, root cause, assumptions, unexpected events, and lesson.
2. Aggregate repeated evidence across an adequate sample; one result cannot change production behavior.
3. Generate only bounded proposals against named weights and attach the supporting sample and reason.
4. Require human administrator approval before a proposal becomes active.
5. Version every approved weight set and retain the prior state.
6. Monitor the change and roll it back through the recorded rollback action if performance or calibration degrades.

The engine learns from patterns while preserving the constitutional rules. It cannot learn to chase losses, force picks, hide missing data, increase action after a loss, or redefine ABC cards.

## Live and cash-out protocol

1. Refresh score/clock/inning, current market and price, availability, injury/lineup state, and source time before acting.
2. Re-evaluate the original thesis, its invalidation conditions, fair remaining probability, remaining payout, and bankroll exposure.
3. Treat a cash-out offer as a new market price. Compare it with fair remaining value rather than reacting to fear, sunk cost, or a temporary deficit.
4. `HOLD` only when the verified thesis remains intact and the offer materially underprices fair remaining value.
5. `CASH_OUT` only when material new information breaks the thesis and the exit is reasonable against current fair value.
6. `PARTIAL_HEDGE` only when the opposing protected market has independent value or a hard bankroll/exposure rule requires reduction.
7. `SKIP_LIVE_ADD` when the new live entry lacks clean edge. Never double down merely to rescue a pregame position.
8. Record the action, offer, time, reason, live-trigger result, and final P/L; grade the cash-out process separately from the underlying outcome.

Stale screens, guessed probabilities, unavailable markets, and unverified injury/lineup changes block live action.

## Ticket doctrine

- Prefer a stable anchor, a genuine value position, and a controlled total or lower-variance market.
- Remove unnecessary legs.
- Identify the weakest leg.
- ABC means: A = strongest available plays; B = strongest different-player/different-thesis plays; C = best diversified combination of A and B.

The authoritative card-by-card definitions and removed legacy behavior are in [Protocol Changelog](PROTOCOL_CHANGELOG.md).
