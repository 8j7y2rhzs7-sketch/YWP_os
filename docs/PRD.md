# YWP OS — Product Requirements Document (PRD)

**Product:** YWP OS (Decision Engine)  
**Owner:** YWP  
**Status:** Living document (reflects shipped product as of API **3.3.17**)  
**Audience:** Product, engineering, compliance, partners (e.g. Whop), reviewers  

---

## 1. Purpose

YWP OS is a **sports decision-support platform**. It helps subscribed users:

1. Load a live priced slate (Run) or sportsbook-style menu (Sheet).
2. Grade candidates with a deterministic decision engine (PLAY / LEAN / WATCH / SKIP).
3. Build tickets under bankroll and correlation rules.
4. Lock-check before placement awareness.
5. Settle outcomes and learn without silently rewriting the protocol.

It is **not** a sportsbook, payment rail for wagers, or guarantee of profit. Outputs are decision artifacts for capital preservation and edge measurement.

---

## 2. Goals

| Priority | Goal |
|---|---|
| P0 | Official recommendations are deterministic, auditable, and fail-closed when research is incomplete. |
| P0 | Users cannot access paid product surfaces without valid subscription entitlement. |
| P0 | Secrets, tokens, and provider keys never ship in the mobile client. |
| P1 | Sheet behaves like a selectable sportsbook menu; only PLAY/LEAN build tickets. |
| P1 | Hive learns from settled outcomes without exposing identity or inventing fake research. |
| P2 | Multi-sport coverage expands only when a certified price + fact path exists. |

### Non-goals

- Placing bets with books on behalf of the user.
- Guaranteeing wins or “locks.”
- Scraping unlicensed HTML as primary research.
- Letting personal risk preferences rewrite the official board grades.

---

## 3. Users & access

| Persona | Needs |
|---|---|
| Subscriber (Whop / app account) | Run slate, Sheet, tickets, Sync Scores, Learning / Hive progress. |
| Prospective user | See paywall / checkout; no protected API data. |
| Operator / admin | Deploy API, rotate secrets, review learning proposals (human approval for weight changes). |

**Access model**

- Email/password auth with short-lived access JWT + rotating refresh tokens.
- Whop subscription gate for app access when `WHOP_SUBSCRIPTION_REQUIRED=true`.
- Every protected query scoped to the authenticated user.

---

## 4. Product surfaces (requirements)

### 4.1 Home / Controls

- Show protocol status, download link for Android APK when configured.
- Display (not invent) API connectivity and subscription state.

### 4.2 Run (raw slate)

- User selects sport + date and refreshes a **raw candidate list** from live providers.
- Candidates must include real sportsbook prices when markets exist; never fabricate odds.
- Surface research readiness honestly (`VERIFIED` / `PARTIAL` / `DEMO`).
- **Strict Mode:** incomplete research → engine grades SKIP for official PLAY/LEAN (fail-closed).
- MLB may wait on confirmed lineups closer to first pitch (expected).
- KBO uses Odds-backed research (ESPN has no `baseball/kbo` path).

### 4.3 Sheet (sportsbook menu)

- Load a full selectable board (h2h / spreads / totals + sport props where supported).
- User selects legs → Check grades **selected** legs only.
- Only PLAY/LEAN legs may build a ticket; SKIP stays graded without becoming an official card.
- Load stays fast (book menu); model overlay is Check-path / soft-fail only.

### 4.4 Tickets & Lock Check

- Draft tickets from cleared recommendations.
- Lock Check compares stored snapshot vs current provider snapshot before place awareness.
- Bankroll / exposure rules must block unsafe construction.

### 4.5 Settlement & Learning

- Sync Scores settles locked tickets and board / Sheet learning universe where supported (MLB auto-settle primary).
- Outcomes feed personal learning + Hive calibration.
- Production model weights do not silently mutate from one result; proposals are bounded and auditable.

### 4.6 Hive

- Capture anonymized prediction/outcome rows for calibration.
- Bounded probability blend only on mature evidence.
- Self-improvement invents tactics within caps; promotion requires measured improvement; never overrides research SKIP gates.

### 4.7 Platforms

- Android APK (primary paid delivery today via GitHub Releases / Whop file link).
- iOS / web paths exist in repo; distribution may lag Android.

---

## 5. Functional requirements (summary)

| ID | Requirement |
|---|---|
| FR-1 | System SHALL persist recommendations with model version, protocol version, reason codes, and input hash. |
| FR-2 | System SHALL NOT invent independent model probability from sportsbook implied odds alone. |
| FR-3 | System SHALL gate paid Odds calls for out-of-season sports using the free sports catalog when available. |
| FR-4 | System SHALL show priced plays even when research is PARTIAL, while blocking official PLAY/LEAN until verified (sport-scoped checklists apply). |
| FR-5 | Sheet SHALL capture customer selections for Hive learning including SKIP, and settle those outcomes when Sync Scores runs. |
| FR-6 | Soccer SHALL include major European leagues and UCL/UEL (not MLS-only). |
| FR-7 | Demo mode SHALL label synthetic data and MUST NOT be silently substituted in production. |

---

## 6. Security requirements

| ID | Requirement |
|---|---|
| SEC-1 | Passwords SHALL be hashed with a modern KDF (Argon2 via `pwdlib`); plaintext passwords SHALL never be logged or stored. |
| SEC-2 | Access tokens SHALL be short-lived JWTs with issuer, audience, subject, type, JTI, iat, and exp claims. |
| SEC-3 | Refresh tokens SHALL be stored hashed, rotated on use, and revocable. |
| SEC-4 | Provider API keys (`ODDS_API_KEY`, Whop secrets, JWT secret) SHALL live only in server environment / secret store — never in the mobile binary or public docs. |
| SEC-5 | API SHALL authorize every ticket, recommendation, bankroll, and learning read/write to the authenticated user (no client-supplied user id trust). |
| SEC-6 | CORS SHALL allow only configured origins (Whop + app/dev hosts). |
| SEC-7 | Production SHALL require subscription entitlement checks when Whop gating is enabled. |
| SEC-8 | Error reports and logs SHALL avoid secrets, full tokens, and raw password fields; app version and safe diagnostics only. |
| SEC-9 | Webhooks (Whop) SHALL verify signatures when a webhook secret is configured. |
| SEC-10 | Admin / provision endpoints SHALL require a provision secret or equivalent operator control. |
| SEC-11 | Transport SHALL use HTTPS for production API and downloads. |
| SEC-12 | Dependency and container deploys SHALL not embed `.env` files with live secrets into public git. |

### Threat notes (product intent)

- Treat the mobile app as hostile for secret storage.
- Treat recommendation payloads as user-owned data; do not leak across accounts.
- Fail closed on research/auth rather than inventing “helpful” data.

---

## 7. Data privacy requirements

| ID | Requirement |
|---|---|
| PRV-1 | Collect only data needed to operate auth, subscriptions, decisions, tickets, settlement, and learning. |
| PRV-2 | Hive learning events SHALL store a **contributor key** (HMAC / anonymized), not raw email, in learning aggregates. |
| PRV-3 | Hive feature flags SHALL be allowlisted; free-text PII, emails, stakes, and private notes MUST be stripped. |
| PRV-4 | Consent / policy for Hive SHALL be configurable (`YWP_HIVE_REQUIRE_CONSENT`); product copy MUST match the live setting. |
| PRV-5 | User passwords, refresh token plaintext, and provider keys MUST NOT appear in Hive, analytics, or share cards. |
| PRV-6 | Share cards / exports SHALL contain decision artifacts the user chose to share — not account credentials or other users’ data. |
| PRV-7 | Retention: operational DB rows (users, tickets, recommendations, results, Hive events) persist for product learning; deletion / export requests SHALL be supportable by operator process (document runbook as product matures). |
| PRV-8 | Third parties: The Odds API (prices/scores), MLB Stats API / ESPN / NHL / Open-Meteo (facts), Whop (entitlement/checkout), Render/hosting (infra). No selling of personal betting history to advertisers. |
| PRV-9 | Location: timezone is user profile preference for slate dating; precise GPS is not required for core product. |
| PRV-10 | Minors: product is intended for adults in jurisdictions where sports wagering decision tools are lawful; do not market to minors. |

### Data classes

| Class | Examples | Handling |
|---|---|---|
| Account | Email, password hash, Whop user id, risk profile, timezone | Private; user-scoped |
| Decision | Candidates, recommendations, tickets, lock checks | Private; user-scoped |
| Learning | Results, process grades, Hive anonymized events | Private / aggregated |
| Secrets | JWT secret, Odds key, Whop keys | Server-only |
| Public | Health (no secrets), public APK download URL | Public |

---

## 8. Compliance & responsible use

- YWP OS provides **analysis and decision support**, not wager placement.
- Users remain responsible for complying with local gambling laws and book terms.
- Official outputs must remain honest about SKIP / research gaps (no dark-pattern “always a play”).
- Demo data must be labeled and never mixed into production learning as live truth.

---

## 9. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | Production API health endpoint reports version, DB status, and Odds configured flag (no secrets). |
| NFR-2 | Heavy routes (slate, analyze, market-board) MUST tolerate Render cold starts (client timeouts ≥ 90s where applicable). |
| NFR-3 | Odds credit spend MUST be gated (in-season catalog, caches, soccer/KBO caps) to avoid silent empty slates. |
| NFR-4 | Decision engine MUST be deterministic for the same normalized snapshot + protocol + approved weights. |
| NFR-5 | Mobile branding / boot MUST match Decision Engine brand system for release APKs. |

---

## 10. Success metrics

- Subscribers can complete: refresh slate → analyze → ticket → lock awareness → settle → see learning.
- Official PLAY/LEAN rate reflects research quality (not forced fills).
- Hive maturity / mapped outcomes increase without PII leaks in flags.
- Zero production incidents of secret exposure in client or logs.
- Sheet Load success without 503 for normal MLB/soccer boards.

---

## 11. Out of scope / future

- Full auto-settle for all non-MLB sports.
- Table tennis (no Odds backbone today).
- Tennis (feasible later via multi-tournament Odds keys).
- Automatic user self-serve GDPR delete UI (operator process first).

---

## 12. Related documents

- `docs/ARCHITECTURE.md` — runtime boundaries & security model  
- `docs/DATA_SOURCES.md` / `TRUSTED_SOURCES.md` — certified providers  
- `docs/HIVE_SELF_IMPROVEMENT.md` — Hive safety rules  
- `docs/WHOP_PAID_DELIVERY.md` — paid Android delivery  
- `docs/YWP_RULES.md` — protocol / QA doctrine  

---

## 13. Approval

| Role | Sign-off |
|---|---|
| Product | __________________ Date ______ |
| Engineering | __________________ Date ______ |
| Security / Privacy review | __________________ Date ______ |

*This PRD is the product requirement baseline. Material changes to auth, Hive consent, data retention, or provider trust MUST update this document in the same change set.*
