# YWP OS Architecture

## Runtime boundaries

| Layer | Responsibility | Must not do |
|---|---|---|
| Expo app | Presentation, user choices, secure token storage, client-side loading/error states | Store provider secrets or invent missing sports data |
| API | Auth, authorization, contracts, persistence, audit trail | Trust client-provided user IDs or bankroll ownership |
| Provider adapter | Normalize live sports, odds, lineup, injury, and weather data | Make betting decisions |
| Decision engine | Deterministic edge, confidence, variance, and gate calculation | Fetch mutable external data during a calculation |
| Ticket builder | Diversification, ABC cards, tiering, correlation and thesis controls | Hide weak legs to improve displayed payout |
| Lock Check | Compare original snapshot with current snapshot immediately before placement | Rebuild a ticket without a material reason |
| Result/live audit | Immutably record settlement, CLV, Miss-by-1, process/variance, triggers, and cash-out action | Rewrite the original recommendation or confuse outcome with process |
| Learning engine | Grade outcomes, calibration, failure patterns, gradual weight proposals | Change production weights from a single result |
| Brand system | Load supplied art, theme tokens, native icon/splash, and data-driven share graphics | Replace the original brand with generated placeholders or use historical card content as live data |

## Canonical pipeline

1. Provider data is normalized to `CandidateInput`.
2. Validation rejects missing or stale fields.
3. The engine derives implied probability, adjusted probability, edge, expected value, confidence, and risk.
4. Constitutional and QA gates can downgrade or force `SKIP`.
5. Recommendations are persisted with the normalized input and SHA-256 input hash.
6. Ticket Builder constructs every official, special, Stay Away, and ABC card while limiting correlation and repeated theses.
7. The selected ticket is saved as a draft.
8. Lock Check compares the stored snapshot with the latest provider snapshot and verifies bankroll/exposure.
9. A user may place only after acknowledging any warning; `CHANGE_REQUIRED` and `SKIP` remain blocking.
10. The result, process/variance grades, CLV, signed miss distance, live/cash-out audit, assumptions, and error analysis enter the learning ledger.
11. The learning engine may create a bounded proposal after adequate repeated evidence; only an administrator can approve it, and every applied proposal remains versioned and reversible.

## Provider contract

A provider adapter returns candidates containing its own timestamp, source name, probability/model input, data-quality score, variance score, reason codes, verification flags, and invalidation conditions. YWP never silently fills an unavailable field with a fabricated value.

All verification flags are fail-closed: omitted flags are `false`. Demo adapters set their synthetic verification explicitly; live adapters must do the same from licensed source data.

## Decision determinism

For the same normalized provider snapshot, protocol version, and approved model weights, the official recommendation and cards are the same for every user. Personal risk profiles affect bankroll stake guidance only. This prevents a preference toggle from rewriting the official board while still allowing conservative or aggressive exposure within hard bankroll caps.

Recommendation records store the normalized input and SHA-256 hash. The decision engine never fetches mutable external data mid-calculation, and Lock Check uses a separate fresh snapshot immediately before placement.

## Security model

- Passwords use Argon2 through `pwdlib`.
- Access and refresh JWTs include issuer, audience, subject, type, JTI, issued-at, and expiry claims.
- Refresh tokens are hashed in the database and rotated after use.
- Every protected query is scoped to the authenticated user.
- Audit records capture security- and decision-relevant changes without storing plaintext passwords or tokens.
