---
name: betting-run
description: >-
  Hard-gated multi-sport betting run (NBA/NHL/NFL/NCAAF/WNBA/MLB). Use when the
  user asks to run today, exhaustive, place card, weed a slip, BANGERS board,
  steals/SOG/MLs, or check yesterday then run today. Enforces THREE GATES
  (stats → posted lines → HR floor) before any parlay lock.
---

# Betting run (THREE GATES → parlay lock)

## When to use
User wants a daily card, exhaustive board, slip weed, sport MLs, steals, SOG, or "run today". Invoke this end-to-end. No shortcuts.

## THE WAY — three gates before every parlay lock
See `betting/THREE_GATES.md`. **This is mandatory.**

1. **GATE 1 — Stats** — `python3 betting/require_gate.py` (exit 0). Else `run_gate.py` then require again. RS-only L7/L10, full cats, athlete ids. Soft floors = research only.
2. **GATE 2 — Posted lines** — `python3 betting/pull_posted_mains.py` then `grade_posted_card.py`. If `ODDS_API_KEY` set, also `pull_hr_odds.py`. No invented soft alts as bet instructions.
3. **GATE 3 — HR floor** — Confirm lowest available / on-slip / hardrockbet number. Re-grade **that** line (e.g. Wemby REB 7.5 not 6.5; Randle PTS 12.5 not 9.5). User-stated HR low = ground truth.

**Parlay lock only from legs that clear all three.** Tag: `G1·G2·G3 · LINE · KEEP|RISK-KEEP · source`

## After gates — card build
4. **From-scratch / BANGERS / SAFE / PRIMARY** — using Gate 2/3 numbers only on actionable lists.
5. **STL / SOG / by-game / BAN**
6. **Weed last** (if slip) — KEEP / RISK-KEEP / CUT vs Gate 3 line; rebuild cleaned slip.
7. **Completion block**

## Card shape (exhaustive / run-today)
```
THREE GATES: G1 PASS · G2 posted-mains · G3 HR floors cited
SAFE 3–4 (posted/HR numbers only)
PRIMARY
BANGERS (4–8, required)
STL / NHL SOG / other
BY GAME
BAN
PARLAY LOCK (all legs G1+G2+G3)
```

## Weed shape
Every leg: Gate 1 hit rate · Gate 2 posted · Gate 3 HR/on-slip number · KEEP / RISK-KEEP / CUT  
Then **Clean rebuild**. CUT = banned from blessed slip.

## Stats display
`Trae Young (id 4277905) AST L5: … | MIN/PTS/REB/AST/STL/BLK … | source espn gamelog`

## Anti-patterns (failed task)
- Soft-floor bet instruction not on HR (Wemby O6.5 when HR low is 7.5)
- Skipping any of the three gates
- SAFE-only card / missing BANGERS when exhaustive asked
- Screenshot spam instead of posted-mains pull
- Claiming gate without PASS file

## Completion block
```
DONE CHECK
- G1 require_gate: PASS|FAIL
- G2 posted-mains: yes|no (path=…)
- G3 HR floors used: yes|no (list sources)
- GATE_TODAY.json date=… status=…
- BANGERS section: yes|no
- athlete_ids shown: yes|no
- parlay lock all legs 3-gated: yes|no
```

## User prompt cheatsheet
See `betting/HOW_TO_PROMPT.md`.
