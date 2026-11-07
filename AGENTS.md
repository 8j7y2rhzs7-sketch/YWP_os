# Agent notes (YWP_os)

## Betting runs
- Skill: `.cursor/skills/betting-run/SKILL.md` — invoke for any daily card / exhaustive / slip weed.
- Always-on rule: `.cursor/rules/betting-hard-gate.mdc` — no card without gate PASS; full chat detail + matchup weed mandatory.
- Gate: `python3 betting/run_gate.py` then `python3 betting/require_gate.py`.
- Artifacts: `GATE_TODAY.json`, `GATE_SHEETS_YYYYMMDD.json`, `GATE_STATUS.txt` under `/cursor/stores/self/betting/` and mirrored to `betting/out/`.
- User playbook: `betting/HOW_TO_PROMPT.md`.
- Locked process prose: `betting/HARD_RULES.md` (esp. **Locked 2026-11-07** — chat delivery, matchup List1/List2, parlay review with opponents).
- Prose "Locked" notes alone are not a gate. If PASS files are missing, the gate was not run.
