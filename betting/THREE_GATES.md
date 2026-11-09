# THREE GATES → PARLAY LOCK

**Locked 2026-11-07 — this is the way.**
No parlay lock ships unless all three gates pass for every leg.

---

## GATE 1 — Stats (RS hit rate)
`python3 betting/require_gate.py` → PASS  
Sheets: RS-only L7/L10 (never preseason). Full cats + athlete id.  
Internal soft floors may be graded here for research — **not bet instructions**.

## GATE 2 — Posted book lines
`python3 betting/pull_posted_mains.py` (+ `pull_hr_odds.py` if `ODDS_API_KEY`)  
`python3 betting/grade_posted_card.py`  
Know what books actually list. Consensus mains ≈ HR. **No inventing O6.5/O9.5 ghosts.**

## GATE 3 — HR floor (lowest available)
Confirm the number Hard Rock actually offers for that market:
- user-stated low (e.g. Wemby REB **7.5**, Randle PTS **12.5**), or
- HR screenshot / Odds API hardrockbet row, or
- on-slip line from the user’s bet slip  

**Re-grade that exact number.** Soft KEEP that isn’t on HR = drop or swap player — never “hunt lower.”

---

## Parlay lock rule
A leg is LOCK-eligible only if:
1. Gate 1 clears (or RISK-KEEP with explicit miss), **and**
2. Gate 2 has a posted line for that player/stat, **and**
3. Gate 3 number is the one on HR (lowest or on-slip) and still KEEP/RISK-KEEP at that number.

Tag every locked leg: `G1 · G2 · G3 · LINE · KEEP|RISK-KEEP · source`

If any gate fails → CUT that leg. Rebuild from legs that clear all three.
