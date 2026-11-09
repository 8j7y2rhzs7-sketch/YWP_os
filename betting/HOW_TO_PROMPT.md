# How to get exactly what you want

Chat memory does not enforce process. Use these prompts + **THREE GATES** (`betting/THREE_GATES.md`).

## THE WAY — parlay lock
```
Lock a parlay through all three gates.
G1 require_gate → G2 pull_posted_mains + grade_posted_card → G3 HR floors (lowest/on-slip).
Only legs that clear all three. Soft floors internal only.
```

## Daily run
```
Run /betting-run end-to-end for today.
Order: G1 require_gate → G2 posted mains → G3 HR floors → scratch → BANGERS → SAFE → by-game → PARLAY LOCK.
Reply only after GATE_TODAY.json = PASS.
Every locked number must be posted/HR — no soft-floor ghosts.
Show athlete id + full MIN/PTS/REB/AST/STL/BLK for every boarded player.
No SAFE-only card.
Done only if completion block shows all three gates PASS/yes.
```

## Exhaustive
```
/betting-run exhaustive for today. Include BANGERS. Same three-gate rules.
```

## Slip weed
```
Weed this slip with three-gate rules.
G1 hit rate · G2 posted · G3 on-slip/HR line → KEEP / RISK-KEEP / CUT.
Rebuild the cleaned slip in the reply.
```
(Paste screenshot, leg list, or HR lowest available.)

## Drift correction
```
Stop. You skipped a gate. Run THREE_GATES 1→2→3 and restart.
```

## Verify yourself
1. G1: `python3 betting/require_gate.py` → PASS
2. G2: `betting/posted-mains-YYYYMMDD.json` exists; grades use those lines
3. G3: every lock leg cites HR low / on-slip / hardrockbet source
4. Spot-check one athlete id on ESPN gamelog

## Custom Mode tip
Attach the `betting-run` skill (or this file) in a Custom Mode so every turn keeps the three gates — don’t rely on chat memory.
