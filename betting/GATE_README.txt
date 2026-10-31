HARD GATE (real implementation)

Text "locks" are not gates. These scripts are:

  python3 betting/run_gate.py
      → GATE_TODAY.json + GATE_SHEETS_YYYYMMDD.json + GATE_STATUS.txt
      → writes to /cursor/stores/self/betting/ and betting/out/
      → exit 0 only on PASS

  python3 betting/require_gate.py
      → exit 0 only if GATE_TODAY.json is PASS for today's ET date

RULE: No place card / exhaustive / weed until require_gate.py exits 0.

Also in repo:
  .cursor/rules/betting-hard-gate.mdc   (alwaysApply)
  .cursor/skills/betting-run/SKILL.md   (full playbook)
  betting/HOW_TO_PROMPT.md              (user prompt cheatsheet)
  AGENTS.md                             (cloud agent pointer)
