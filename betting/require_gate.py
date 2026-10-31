#!/usr/bin/env python3
"""Refuse work unless GATE_TODAY.json status=PASS for today's ET date."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

STORE_CANDIDATES = [
    Path("/cursor/stores/self/betting"),
    Path(__file__).resolve().parent / "out",
]
ET = ZoneInfo("America/New_York")


def today() -> str:
    return datetime.now(ET).strftime("%Y%m%d")


def gate_paths() -> list[Path]:
    return [p / "GATE_TODAY.json" for p in STORE_CANDIDATES]


def check(date: str | None = None) -> tuple[bool, str]:
    date = date or today()
    existing = [p for p in gate_paths() if p.exists()]
    if not existing:
        return False, "GATE_TODAY.json missing — run: python3 betting/run_gate.py"
    # Prefer newest mtime
    gate_path = max(existing, key=lambda p: p.stat().st_mtime)
    try:
        g = json.loads(gate_path.read_text())
    except Exception as e:
        return False, f"GATE_TODAY.json unreadable ({gate_path}): {e}"
    if g.get("date") != date:
        return False, f"GATE date {g.get('date')} != today {date} — re-run betting/run_gate.py"
    if g.get("status") != "PASS":
        fails = g.get("failures") or []
        return False, f"GATE FAIL ({len(fails)}): " + "; ".join(fails[:5])
    return True, f"PASS date={date} sheets_ok={g.get('sheets_ok')}/{g.get('sheets_total')} path={gate_path}"


def main() -> int:
    ok, msg = check()
    print(msg)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
