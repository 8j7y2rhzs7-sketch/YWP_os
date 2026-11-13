# How to get exactly what you want

Chat memory does not enforce process. Use these prompts + the repo skill/rule/gate.

## Daily run (default — agent should not need this prompt)
```
Run /betting-run end-to-end for today.
Order: require_gate → full sheets → scratch → BANGERS → SAFE → by-game → MATCHUP WEED (List1 difficult / List2 better, FULL DETAIL IN CHAT) → weed last.
Reply only after GATE_TODAY.json = PASS.
Show athlete id + full MIN/PTS/REB/AST/STL/BLK for every boarded player.
Every pick line includes opponent + what that D allows.
Paste full lists in chat — no file links, no truncated boards.
No SAFE-only card. Nothing extra unless asked.
Done only if completion block is all PASS/yes.
```

## Exhaustive
```
/betting-run exhaustive for today. Include BANGERS + full matchup List1/List2 in chat. Same gate rules.
```

## Slip weed / parlay review
```
Weed this slip with /betting-run rules.
Every leg: L7/L10 vs line + opponent D for that category + OUT/role.
KEEP / RISK-KEEP / CUT only.
CUT only if from-scratch fails (injury/DNP/true climb).
Rebuild the cleaned slip in the reply (full detail in chat).
```
(Paste screenshot or leg list. Agent must not wait to be told to add opponents/stats.)

## Drift correction (short)
```
Stop. You skipped the gate. Run require_gate.py and restart from step 1.
```

## Verify yourself
1. `python3 betting/require_gate.py` → must print PASS
2. Open `betting/out/GATE_TODAY.json` or `/cursor/stores/self/betting/GATE_TODAY.json`
3. Reply must include **BANGERS** + completion block
4. Spot-check one athlete id on ESPN gamelog

## Custom Mode tip
Attach the `betting-run` skill (or this file) in a Custom Mode so every turn keeps the checklist — don’t rely on “you remember from last month.”
