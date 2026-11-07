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
2. **Posted lines (no screenshot loop)** — `python3 betting/pull_posted_mains.py` (Betravon consensus mains). If `ODDS_API_KEY` is set, also `python3 betting/pull_hr_odds.py` for hardrockbet tags. Soft floors stay **internal only**.
3. **Grade at posted** — `python3 betting/grade_posted_card.py`. Actionable KEEP/RISK-KEEP must use the **posted main number**, not a softer invent.
4. **Read gate** — `GATE_TODAY.json` + sheets path. Note sports active.
5. **From-scratch** — RS-only L10/L5 with full cats (NBA: MIN/PTS/REB/AST/STL/BLK/TO). Athlete id on every boarded player.
6. **BANGERS board** — required. Dual-cat bigs, third SOG, PTS+thief stacks, MLs worth juice — not buried.
7. **SAFE / PRIMARY** — cush rules; no Mobley-class stretch-big SAFE; AST SAFE cush≥2; no hook spines. Tag every leg `POSTED · LINE · source`.
8. **STL / SOG / by-game / BAN**
9. **Weed last** (if slip) — KEEP / RISK-KEEP / CUT vs **posted/on-slip line**; rebuild cleaned slip. Never tell user to hunt unposted soft alts.
10. **Completion block** (required in the reply)

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
CLEAN SLIPS: SAFE · MIX · UPSIDE
```

## Weed shape
| Leg | Call | Why |
KEEP / RISK-KEEP / CUT only. Then **Clean rebuild** list. CUT = banned from blessed slip.

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
