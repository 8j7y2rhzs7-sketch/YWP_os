# HARD RULES — locked process

## ENFORCED GATE (not prose) — 2026-10-31
Previous "Locked" sections were text-only. User caught that nothing was implemented.
**Real gate now:**
- `python3 /cursor/stores/self/betting/run_gate.py` → `GATE_TODAY.json`
- `python3 /cursor/stores/self/betting/require_gate.py` must exit 0 before any card
- Proof files: `GATE_TODAY.json`, `GATE_SHEETS_YYYYMMDD.json`, `GATE_STATUS.txt`, `GATE_README.txt`
If those files are missing, any claim that a gate exists is false.


## Daily run order
1. Identify every sport with games today (NBA, NFL, NHL, MLB, WNBA, NCAAF, soccer if posted).
2. For each sport, exhaustive boards with **sport-specific** grading.
3. **Regular season only for L10/L5 — never mix preseason into hit rates.**
4. Main-first + ladders; HR playable only (no PP soft ghosts).
5. Role-aware stitch; when unsure → CUR_ONLY.
6. Separated lists by sport first; then mix if asked.

## Locked — NFL ≠ NBA grading
- NFL: MATCHUP → script → role → then L10. Never L10-first.
- Do not lead with juice ghosts (Young 189.5 class). Soft alt missing → climb to posted line and re-grade.
- Mix parlays stay on. Do not nuke mix because one NFL spine was dumb.
- Kill-class: QB pass OVER as floor; juiced NBA PTS above real floor; Kap-class O2.5 SOG as spine.

## Locked — NBA openers / soft floors
1. Prefer REB/AST floors over star PTS when new offense / rust.
2. Soft AST needs primary creator confirmed; cush ≥1.5–2 when n thin (Barnes hook lesson).
3. Soft REB only for glass identity — not non-glass wing/guard.
4. Never label PRA "safest."
5. Same player new team = re-grade category (facilitator → AST/REB before PTS).
6. Glass spine needs cushion; exact-main glass ≠ A−.
7. Amen-class soft PTS keepable when L10 clean; Amen REB mid-line = add not replace for true glass (Sengun).

## Locked — WNBA Finals
1. Stokes REB O5.5/O6.5 only — never O7.5 spine.
2. Canada drop to O4.5 after G4 miss; O5.5 not spine.
3. No dual-REB-only ticket — mix AST/PTS.
4. Soft Finals PTS can die even after series clears (Gabby).

## Locked — MLB WS
1. Split hit floors across both sides; everyday C/1B > star vs ace.
2. No K+under as identity; soft U without cushion = skip.
3. Dog +1.5 often better ticket identity than chalk ML.

## Locked 2026-10-25 — mix works, dumb spines kill
- Pipeline fine. Kill Young-class QB volume, Kap O2.5 SOG, juiced PTS.
- Mix shape: NBA counting / soft PTS floor + NHL star SOG O1.5 + optional one NFL skill.
- Soft AST cush ≥2 or drop a tier when n thin.

## Locked 2026-10-26 — AM n=3 ghosts + yday grade
**Incident:** AM board branded Gobert O8.5 / Hali O6.5 / Trae O8.5 as 3/3 KEEP off tiny sample. Full RS sample killed Gobert O8.5; Hali/Trae needed a tier drop. Yday card: NBA SAFE3 **2/3** (Davion AST→2), PRIMARY8 **7/8**, WNBA SAFE3 **2/3** (Gabby→9), MIX6 **4/6**, MLB SAFE3 **2/3** (Caminero 0H).

### Rules
1. **Never spine a 3/3 early-season floor without checking the rest of the open RS sample (n≥5 when available).**
2. **Climb down a full tier when full-sample clear drops under 80%.**
3. **REGULAR SEASON ONLY.** Preseason rows in ESPN gamelog must be stripped. (Mitchell/LaMelo false CUT from preseason mix — user caught it.)
4. **Facilitator AST floors can die on scoring nights.** Davion O3.5 AST → 2 with 21 PTS / 2 threes. Scoring ≠ dimes. Prefer cush ≥2 or secondary creator confirmation before SAFE.
5. **Finals / series soft PTS still missable.** Gabby O14.5 series-cleared then printed 9 in G5. Don't treat series min as a lock.
6. **Rate-bans ≠ "will miss tonight."** Gobert/Hali 6.5/Trae 8.5/Stokes 7.5 can cash; bans are process/sample. Keep them off spines anyway.
7. **BAN that saved:** Canada O5.5 AST (5) · Charles O4.5 REB (4). Keep those bans.
8. **Amen REB mid-line = add, not HOU boards spine.** Amen O6.5 → 5; Sengun O6.5 → 9. True glass first.
9. **Confirm DNP/OUT before tip** (Chet DNP killed NEXT leg).
10. **Caminero-class hit floors still 0-fer live** in WS — split floors, don't over-concentrate one side's bats only if building multi-leg.

## HR playable
- If the soft floor isn't on the book, climb to nearest posted line and re-grade. Rebuild from available markets (WNBA G5: only Gabby of series SGP4 was posted → HR swap card).


## Applied 2026-10-27 run
- Used RS-only floors, AST cush≥2 for SAFE, faded BKN/SAC dog blowout spines, NHL SOG O1.5 default, Contreras+MIL+1.5 for WS G4 clinch.


## Locked 2026-10-27 — Derrick White O0.5 STL (bad player pick, not category ban)
**Incident:** User asked for steals. Agent filled with White / Thybulle / Champagnie-class. White printed **0 STL**. User roast = wrong player, not "never do steals."
**User clarification 10/28:** *"The steals that I put went through you that have to find the right match up and player."* When user asks for steals, **do the work** — matchup + right thief. Don't dump O0.5 clears or ban the category after one miss.
### Rules
1. **Steals stay on when the user asks.** Agent owns matchup + player selection. Category is not banned.
2. **Matchup first:** prefer thieves facing high-TO teams / soft handle / pace-up. Don't rank by "O0.5 cleared 3/3" alone.
3. **Right player:** usage / known POA identity (Daniels, Hart, Mitchell, Caruso, Amen, Cade, Castle, Maxey, Suggs-class). If the user wouldn't name him cold, he needs an explicit matchup case — not a spine.
4. **White / Champagnie / Thybulle-class = process ban as spines.** Rate-clearing role defenders without usage identity don't carry steal tickets.
5. **O0.5 STL is variance** — binary night-to-night. Cap steal legs (usually 2–3 on a dedicated steal card; 1–2 inside a mix). Never a 4–6 leg steal stack of soft names.
6. **Yday grade reminder:** Hart O0.5 HIT(5). White/Thybulle/Champagnie/Fox/Reaves 0. Hart was the right archetype; White was the wrong fill.


## Applied 2026-10-28 run
- Yday: counting 7/8 (Hart REB miss); STL stack bloodbath → White rule already locked.
- Today spines: Gobert/KAT/Wemby REB + Cade/Luka/Jokic/Reaves/Fox AST. No STL. Amen O4.5 add only (not O6.5). Hart O3.5 max after yday 4.
- NHL: Hughes / Draisaitl / McDavid O1.5 SOG.
- WS G5: MIL +1.5 (leads 3-1); Contreras O0.5 H floor only.


## Locked 2026-10-28 — Brunson 3PM matchup (same lesson as steals)
**Incident:** Brunson O0.5/3PM on yday threes card. He's a real shooter. vs DET he went **0-5** (all 25–26 ft pull-up/jumpers in PBP), still scored 23 on 13-16 FT. User: matchup made it hard — correct.
### Rules
1. **Shooter identity ≠ auto 3PM spine.** Same as steals: when user asks for threes, find the **right matchup + right player**.
2. **Fade / downgrade pull-up guards vs length + elite POA** (DET Ausar/Cade class). Volume can still clear (Brunson got 5 attempts) and the make still dies.
3. **Read the script:** FT hunt / paint gravity nights can keep PTS alive while 3PM floors die. Don't treat PTS cash as 3PM cover.
4. **Process:** for 3PM boards, check who contests the shooter before SAFE — not just L10 make rate.

## Applied 2026-10-28 AM refresh
- OUT scrub: Caruso/Cason/Suggs off steal card → Amen/Bam/Castle.
- SAFE still Gobert O8.5 / KAT O9.5 / Wemby O6.5 + Cade/Luka/Jokic/Reaves/Fox AST.
- Threes matchup-first: Luka/Castle/Mitchell over Brunson SAFE.
- NHL Hughes/Draisaitl/McDavid · WS MIL+1.5 + Contreras O0.5 H.


## Locked 2026-10-28 grade → applied 10/29
1. **Short-minutes glass kills.** Gobert O8.5 → 4 in 20 MIN. Minutes/foul/blowout check before glass SAFE.
2. **GTD = no spine until ACTIVE.** Luka DNP-back voided AST spine — confirm before tip.
3. **Series-perfect hit floors still 0-fer** (Frelick 4/4 then 0). Keep split sides; don't over-stack one contact bat.
4. **Hart STL variance real** — 5 yday then 0. Matchup thieves OK; not a must-stack.
5. **Amen O4.5 REB hook (4)** — mid-line REB still add-only.

## Locked 2026-10-30 — "lost by 1" ticket kill pattern
**User:** every ticket loses by 1 player — feels intentional.
**Not sabotage — bad process.** Same failure repeats: juiced climbs + hook-cush spines as ticket identity.

### Last night receipts (Oct 29)
- **Stokes O7.5 REB → 7** — lost by 1. We said CUT → O6.5. O6.5 would have HIT. Climb killed the slip.
- **Canada O5.5 AST → 2** — locked ban as spine; still on the +1200 SGP. Dead.
- **Stokes O4.5 PTS → 0** — we said CUT (Finals PTS 2/5). Dead.
- **Harden O4.5 AST → 4** — hook miss on a PRIMARY we left live.
- Rest of NBA core mostly cashed (Sabonis 15, JJ 8, Allen 8, Daniels/Mitchell STL, Kaprizov/Connor SOG).

### Pattern across the week
Amen O4.5→4 · Hart REB hooks · Stokes O7.5→7 · Harden O4.5→4 · Canada O5.5 kept after CUT.
The "1 player" is usually the **climb we weeded** or a **soft-cush PRIMARY** that prints the line.

### Rules (hard)
1. **CUT means banned from the ticket.** If weed says drop Stokes 7.5 / Canada 5.5, do not leave it on any SGP we bless. Rebuild the slip in the reply.
2. **No hook spines.** SAFE/PRIMARY needs cushion that still cashes if they print the line number (O7.5 needs real path to 9+, not "cleared 4/5 with a 7"). Prefer full tier down.
3. **AST SAFE cush ≥2** stays; **exact-main with cush ≤1.5 = NEXT only**, never ticket identity.
4. **Finals/alt climbs that fail the weed get a KILL list in the place card** — not LEAN.
5. When user sends a slip, reply with a **cleaned alternate slip** (legs to remove + replacement), not only KEEP/CUT table.


## Locked 2026-10-29 only-ticket — Mobley O7.5 sole killer
**User only ticket yday:** SGPMAX 9 (+418). **7 hit · 1 void (Dejounte) · 1 miss (Mobley O7.5 → 4).** Rest of card cashed.
### Rules
1. **Mobley / stretch-big glass ≠ auto SAFE** off early 4/4 when the player also runs facilitator usage. Role script can flip (4 REB / 7 AST). Prefer true center glass (Allen) as the CLE REB spine.
2. **Don't must-stack two CLE bigs (Mobley+Allen) on one SGP.** One glass spine. Allen was the right one (8).
3. **Thin early RS glass (n=4) stays NEXT unless cushion is huge and role is pure rebounder.**
4. GTD still voided Dejounte — ACTIVE check before tip stays mandatory.


## Applied 2026-10-30 run
- Yday only-ticket Mobley sole killer locked.
- SAFE: KAT O9.5 / Bam O5.5 / Cade O5.5 — pure glass + creator, no stretch-big, no hooks.
- Embiid O6.5 not 7.5 · Jokic O4.5 not 6.5 · Gobert NEXT tier-down after short minutes.
- Sengun GTD banned · NHL Hughes/Connor/Reinhart O1.5 · WNBA G7 tomorrow.


## Locked 2026-10-31 — over-weed after lost-by-1 (user cashed our CUTs)
**Incident:** User SGPMAX 10 cashed (+576). Agent weeded Perfetti + Kessler REB/BLK off the ticket. All three cashed (Perfetti SOG; Kessler 13 REB / 5 BLK). Core KEEP legs also cashed. User: tailored away from agent CUTs to win; feels set up to fail when following weed.

### Rules
1. **Weed cannot contradict from-scratch KEEP/PRIMARY.** If scratch grades clear ≥80% with no L5 miss, flag risk — do not CUT unless injury/DNP/true climb (print-at-or-below line in form).
2. **Correlation ≠ ban.** Same-game 3rd SOG / dual-cat stack = construction note + optional trim, not automatic removal of a PRIMARY that clears.
3. **Lost-by-1 rule stays narrow:** only true climbs / hook spines with a miss or print-at-line in form (Bam O6.5 with a 6). Do not expand to every cush~1.5 PRIMARY that is otherwise clean.
4. **When user cashes a CUT, agent owns the over-weed in the postmortem** — update process, don't call it luck.
5. **Tailor-friendly weed format:** KEEP / RISK-KEEP (why) / CUT (only true bans). Never pretend RISK-KEEP is a CUT.

### Applied
- Yday over-weed logged. Congrats on the cash.
- Next weed uses KEEP / RISK-KEEP / CUT only.


## Locked 2026-10-31 — agent never surfaces the cash (user finds it alone)
**User:** never gets the good stuff from the agent — always has to find Kessler/Perfetti/AD/Diabate/ML-class plays themselves. Agent only serves SAFE floors then over-weeds the upside the user already found.

### Rules
1. **Every exhaustive / run-today MUST include a BANGERS board** (HR-playable upside), not only SAFE3/PRIMARY. Bangers = clean form + real path to juice: dual-cat bigs (REB+BLK), third star SOG, known thief + PTS stack, home ML dogs/picks the market underrates, soft alts that still clear L5.
2. **SAFE is the floor, not the whole card.** Lead with SAFE, but always publish 4–8 BANGERS with form/cush so the user does not have to dig alone.
3. **Do not hide PRIMARY/BANGERS behind CUT language.** Use KEEP / RISK-KEEP / CUT. RISK-KEEP stays on the published board.
4. **Stop only-serving cush glass + O1.5 SOG.** That package is necessary but not sufficient — user already knows it. Add the next tier unprompted.
5. **Credit:** if the user found it, say so. Never retrofit agent ownership onto their ticket.

### Card shape (mandatory)
- SAFE 3–4
- PRIMARY
- **BANGERS** (new — required)
- STL / SOG / by-game
- BAN (true bans only)
- Clean slips: SAFE · MIX (SAFE+banger) · UPSIDE


## Locked 2026-10-31 — full-stat check + do the task as specified
**User:** after thousands of hours, agent still skips full stats and fails to execute the card exactly as instructed (SAFE-only, incomplete categories, weed contradicting scratch, missing BANGERS, dropped legs).

### Non-negotiable before any place card / weed
1. **Pull full counting categories for every boarded player:** PTS, REB, AST, STL, BLK, 3PM, TO when relevant — not REB/AST/STL only. Kessler-class dies when BLK is never fetched.
2. **RS-only L10/L5 + minutes** on every SAFE/PRIMARY/BANGER. No vibe grades.
3. **From-scratch first, weed second.** Weed cannot invent CUTs scratch did not earn.
4. **Deliver the requested shape exactly:** if user says exhaustive / bangers / steals / MLs / weed — each section present, not a SAFE3 summary pretending to be the ask.
5. **HR playable only** with posted lines; climb + regrade, never ghost floors.
6. **After delivery self-check:** Did I omit a category, contradict scratch, skip BANGERS, or answer a different question than asked? If yes, fix before sending.

### Failure modes that are no longer acceptable
- Shipping SAFE glass/SOG as the whole product
- Cutting PRIMARY clears for "correlation story"
- Missing BLK/PTS/3PM because the scraper only stored reb/ast/stl
- Taking credit for user-found legs
- Partial exhaustive that dies mid-board


## Locked 2026-10-31 — illegitimate-stats / show the sheet
**User:** watches agent take shortcuts; asks for stats and gets wrong/incomplete info; cannot trust app if sourcing is illegitimate.

### Facts
- Stats source is ESPN public gamelog/scoreboard APIs (real feed). The illegitimacy was **agent truncation** — storing reb/ast/stl/pts only and presenting that as a full check.
- BLK/MIN/3P/TO were available and dropped. That is a shortcut, not a source failure.

### Rules
1. **Show the sheet:** when user asks stats or a pick is boarded, display MIN/PTS/REB/AST/STL/BLK/TO (and 3P when relevant) with source + id + n.
2. **Never silent-omit.** If a category was not fetched, print `NOT FETCHED` — do not pretend it was checked.
3. **Floors must persist full counting cats** before SAFE/PRIMARY/BANGERS publish.
4. **No vibe citations.** Every number in a reply traces to a fetched row.


## Locked 2026-10-31 — stats were literally wrong (user verified)
**User:** not only incomplete — checked agent stats and they were wrong. Trust broken.

### Agent response
- Do not argue. User verification stands.
- Known ways agent emits wrong numbers: preseason mixed into RS; wrong athlete/team label on right form; category omitted then implied checked; form arrays pasted onto wrong player; stale /tmp boards presented as live; hit-rate math off shown form.
- Oct 30 spot-check: some published L5s matched ESPN after stripping the played game — that does not erase prior wrong sheets.

### Rules
1. **Every stat block ships with athlete id + source endpoint** so user can open the same feed.
2. **If user says a number is wrong, treat as incident:** re-fetch, diff, log file, correct the board — no debate.
3. **No stale boards.** Refetch at start of every run/weed; timestamp the sheet.
4. **One player = one id.** Never copy form arrays between players.


## Locked 2026-11-01 — roster team verify
**Incident:** Boarded LeBron O3.5 AST on TOR@LAL; LeBron is **PHI**. Gate sheets tagged stale team=LAL.
### Rules
1. Before boarding any player, confirm **current team** from ESPN `teamRelationships` / roster — not memory, not yesterday's sheet team field alone.
2. If player's team is **not in today's slate**, he is auto-CUT from the day card.
3. Same-player new team = full re-grade (already locked) — also means **wrong-game board = hard fail**.


## Locked 2026-11-02 — silent DNP / ACTIVE gate
**Incident:** Haliburton boarded SAFE O4.5 AST 11/1; not in IND box score (DNP) despite no OUT tag. SAFE3/MIX voided.
**Also:** Franz O14.5→14 and Randle O5.5→5 (lost-by-1 hooks) on PRIMARY.
### Rules
1. **ACTIVE confirm before SAFE.** Roster presence ≠ playing. Check projected starters / game-day report / prior silent DNPs.
2. **Yday silent DNP → next game RISK only until ACTIVE.**
3. Hook rule reaffirmed — tier down after printing the number.

## Locked 2026-11-02 — soft-floor glass > high-average glass (Sabonis incident)
**Incident:** Sabonis O10.5/O12.5 REB boarded SAFE/PRIMARY/MIX spine. Printed **7 REB in 31 MIN** (SAC@DAL final). Same night the card already had **Kessler O4.5** (L5 15/13/9/8/7) and **Bam O4.5** as PRIMARY — softer floors, better L5 clears relative to line. User trusted process, moved fast, didn't notice the weak spine vs better options on the same board. Feels like a setup; it was **ranking by raw average, not by line safety**.

### Receipts
- Sabonis L5=[14,15,14,15,19] → marketed as SAFE because avg/cush vs O10.5 looked huge.
- Kessler O4.5 / Bam O4.5 / Allen O5.5 / Carter O4.5 were on the card with softer posted lines — those are the SAFE-class floors.
- Climbing Sabonis to O12.5 for "value" made it worse as ticket identity.

### Rules (hard)
1. **SAFE glass = softest true-glass line that clears, not the highest REB average.** Rank candidates by (clear rate vs posted line, min cushion, role), then average.
2. **If O4.5–O6.5 true glass exists on the slate (Kessler/Bam/Allen/Carter-class), that outranks O10.5+ glass for SAFE3/MIX spines.** High-line glass (Sabonis/KAT O10.5+) = PRIMARY/BANGER only unless no soft-floor glass is posted.
3. **Every high-line glass SAFE must ship a SAFER ALT on the same reply** (name + line). If the alt is clearly safer, board the alt as SAFE — not the vanity average.
4. **Never make Sabonis-class O10.5+ the only glass spine** on a multi-leg when softer floors are available.
5. **L10/L5 comparison is vs the posted line**, not vs each other raw. A 7-reb floor that clears O4.5 5/5 beats a 15-reb average that must clear O12.5.

### Applied
- Sabonis O10.5+ demoted from auto-SAFE habit.
- Next NBA glass SAFE preference: soft floors first (O4.5–O6.5 true centers), then mid, then high-line.
