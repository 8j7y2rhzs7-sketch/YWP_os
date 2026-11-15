# Accuracy Rules (from season-wide scan)

Locked from `analyze_season_trends.py` · Universe ~423 NBA / ~500+ NHL sheeted players · RS only.

These upgrade THREE_GATES. Gate order still G1 → G2 → G3. These change **how G1 grades**.

## Dual-window KEEP (new)

A line is spine-KEEP only if **both**:
1. **L7** hit ≥ 6/7 (or 5/5 if n=5)
2. **Season** hit ≥ **75%** at that exact line

If L7 is 7/7 but season ≤70% → **TRAP** → shave until season ≥75%, or CUT.

## Minutes master variable

League avg correlations (MIN → stat):
| Stat | corr(MIN, stat) |
|------|-----------------|
| PTS  | **0.53** |
| REB  | **0.42** |
| AST  | **0.35** |
| 3PT  | **0.31** |
| STL/BLK | ~0.20 |

Rules:
- L7 avg MIN **&lt; 24** → demote to RISK / skip spine
- Prefer **28+ mpg** stables
- If player has ≥3 games with MIN &lt; 22 this season → **cliff tag** — no spine without confirmed minutes

## Drift shave

If L7 mean − season mean ≥ **+3** on PTS/REB/AST → shave **one extra step** beyond the normal book floor (hot streak premium).

## Soft floors still banned

Even at 7/7: REB/AST/STL ≤1.5 · 3PT ≤0.5 · SOG ≤1.5  
Season scan found **600+** fake-firm soft clears — juice traps, not edges.

## No-kill spine (agent ↔ app align)

See `betting/no_kill_ticket.py` + `betting/ALIGN-AGENT-APP.md`.

Spine legs only if:
1. L7 ≥ 6/7 (5/7 is **never** spine)
2. Avg clear margin ≥ **1.5** (kills exact-clear ticket-killers)
3. L7 avg MIN ≥ 24
4. Soft floors pad-only (max 1), never spine

Backend: Official core_3/4/5 + tickets A/B/C use `safe_pool` (miss_by_one &lt; 0.55), same as cash_builder/fortress.

## STL / BLK = research only

League avg season hit:
- STL O0.5 ≈ 46% · STL O1.5 ≈ **17%**
- BLK O0.5 ≈ 29% · BLK O1.5 ≈ **9%**

Never parlay spine.

## Same-game stacking

| Pair | avg corr |
|------|----------|
| PTS–3PT | 0.66 |
| MIN–PTS | 0.53 |
| PTS–REB | 0.28 |
| AST–REB | 0.22 |
| PTS–AST | **0.19** |
| REB–STL | 0.06 |

PTS+AST on the same player is **not** one risk — both legs must pass dual-window independently.

## NHL SOG

Skaters: prefer **O2.5** floors; O3.5 rarely holds ≥85% season.  
Never use goalie shots-faced as SOG props.

## NCAAM (separate)

Not in sheet universe. Keep: skip spreads ≥20.5 for parlays (early-season cover trap).

## Run

```bash
python3 betting/analyze_season_trends.py
```
