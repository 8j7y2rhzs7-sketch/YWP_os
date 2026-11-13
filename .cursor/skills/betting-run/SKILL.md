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
3. **From-scratch** — RS-only L10/L5 with full cats (NBA: MIN/PTS/REB/AST/STL/BLK/TO). Athlete id on every boarded player.
4. **BANGERS board** — required. Dual-cat bigs, third SOG, PTS+thief stacks, MLs worth juice — not buried.
5. **SAFE / PRIMARY** — cush rules; no Mobley-class stretch-big SAFE; AST SAFE cush≥2; no hook spines.
6. **STL / SOG / by-game / BAN**
7. **Matchup weed (mandatory)** — every SAFE + RISK clear vs tonight's opponent D (PTS/REB/AST/3PT/STL/SOG allow + OUT/short notes). Output **LIST 1 DIFFICULT** and **LIST 2 BETTER** with full detail in chat.
8. **Weed last** (if slip) — KEEP / RISK-KEEP / CUT; rebuild cleaned slip in the reply. Same full-stat + opponent depth.
9. **Completion block** (required in the reply)

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
For **every leg**: hit rate vs posted line · full cats · opponent D for that category · OUT/role note · KEEP / RISK-KEEP / CUT.
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

## Completion block (paste at end of every run)
```
DONE CHECK
- require_gate: PASS|FAIL (paste one-line output)
- GATE_TODAY.json date=… status=…
- sheets_path=…
- BANGERS section: yes|no
- athlete_ids shown: yes|no
- task shape matched user ask: yes|no
```
If any line is FAIL/no, do not present the card as finished — fix first.

## User prompt cheatsheet (tell user / follow when they paste)
See `betting/HOW_TO_PROMPT.md`.
