---
name: betting-run
description: >-
  Hard-gated multi-sport betting run (NBA/NHL/NFL/NCAAF/WNBA/MLB). Use when the
  user asks to run today, exhaustive, place card, weed a slip, BANGERS board,
  steals/SOG/MLs, or check yesterday then run today. Enforces require_gate →
  full sheets → scratch → BANGERS → SAFE → weed last.
---

# Betting run (hard-gated)

## When to use
User wants a daily card, exhaustive board, slip weed, sport MLs, steals, SOG, or "run today". Invoke this end-to-end. No shortcuts.

## Non-negotiable order
1. **Gate** — `python3 betting/require_gate.py` (exit 0). Else `python3 betting/run_gate.py` then require again.
2. **Read gate** — `GATE_TODAY.json` + sheets path. Note sports active.
3. **Venue + weather (mandatory)** — `python3 betting/pull_game_conditions.py`. For every boarded/weeded game state **venue · city · indoor/outdoor · home/away/neutral**. Outdoor NFL/NCAAF: temp, wind/gust, precip%, condition. **Pass-hostile** (≤40°F or precip≥40% or gust≥20 or rain/snow) → demote pass/rec overs; prefer rush, Under, soft sides. Never publish an outdoor football card/slip without this block.
4. **From-scratch** — RS-only L10/L5 with full cats (NBA: MIN/PTS/REB/AST/STL/BLK/TO). Athlete id on every boarded player.
5. **BANGERS board** — required. Dual-cat bigs, third SOG, PTS+thief stacks, MLs worth juice — not buried.
6. **SAFE / PRIMARY** — cush rules; no Mobley-class stretch-big SAFE; AST SAFE cush≥2; no hook spines.
7. **STL / SOG / by-game / BAN** — BY GAME must include venue/weather one-liner for outdoor football.
8. **Matchup weed (mandatory)** — every SAFE + RISK clear vs tonight's opponent D (PTS/REB/AST/3PT/STL/SOG allow + OUT/short notes) **+ location/weather**. Output **LIST 1 DIFFICULT** and **LIST 2 BETTER** with full detail in chat.
9. **Weed last** (if slip) — KEEP / RISK-KEEP / CUT; rebuild cleaned slip in the reply. Same full-stat + opponent depth + weather/venue on every outdoor leg.
10. **Completion block** (required in the reply)

## Delivery (locked 2026-11-07 — never make user ask twice)
- Paste **full lists in chat**. No GitHub links, no "see file", no truncated "etc".
- Every pick line: `HitRate  Player Over Line STAT — TEAM vs OPP — OPP allows X STAT/g (rank note)`
- Standouts / decision tickets only after the full lists (or when user asks).
- Do not add unsolicited extras. Match the ask.

## Card shape (exhaustive / run-today)
```
GATE: PASS date=YYYYMMDD sheets_ok=N/M
YDAY (if asked)
SAFE 3–4
PRIMARY
BANGERS (4–8, required)
STL / NHL SOG / other
BY GAME
BAN (true bans only)
LIST 1 DIFFICULT (full detail in chat)
LIST 2 BETTER (full detail in chat)
CLEAN SLIPS: SAFE · MIX · UPSIDE
```

## Weed shape (user parlay / screenshot)
For **every leg**: hit rate vs posted line · full cats · opponent D for that category · OUT/role note · **venue/home-away/weather if outdoor** · KEEP / RISK-KEEP / CUT.
Then **Clean rebuild** list in chat. CUT = banned from blessed slip.

## Stats display
When citing a player, show a compact full row + id:
`Trae Young (id 4277905) AST L5: … | MIN/PTS/REB/AST/STL/BLK … | source espn gamelog`

## Anti-patterns (failed task)
- SAFE-only card
- Weed CUTs that contradict scratch KEEP/PRIMARY
- Missing BLK/PTS because scraper truncated
- Claiming gate without PASS file
- Taking credit for user-found legs
- Answering a different question than asked
- Outdoor NFL/NCAAF card or slip without venue + weather (locked 2026-11-26)
- Pass/rec SAFE spines in pass-hostile weather
- Form/posted KEEP promoted to SAFE/CLEAN while OUT/GTD (Reaves) (locked 2026-11-27)
- Binary O0.5 3PT / STL/BLK as SAFE or CLEAN slip identity (locked 2026-11-27)
- Hook cush&lt;1 clears sold as SAFE3 spine (locked 2026-11-27)
- Leaving pass overs RISK-KEEP on pass-hostile slate until user asks about weather (TNF)

## Completion block (paste at end of every run)
```
DONE CHECK
- require_gate: PASS|FAIL (paste one-line output)
- GATE_TODAY.json date=… status=…
- sheets_path=…
- game_conditions: PASS|FAIL|N/A (outdoor football must be PASS; paste pass_hostile list)
- BANGERS section: yes|no
- athlete_ids shown: yes|no
- task shape matched user ask: yes|no
```
If any line is FAIL/no, do not present the card as finished — fix first.

## User prompt cheatsheet (tell user / follow when they paste)
See `betting/HOW_TO_PROMPT.md`.
