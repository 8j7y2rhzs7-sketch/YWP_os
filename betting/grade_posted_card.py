#!/usr/bin/env python3
"""
Grade GATE sheets against posted mains only (no soft-floor bet instructions).

Usage:
  python3 betting/pull_posted_mains.py
  python3 betting/grade_posted_card.py

Writes betting/posted-card-YYYYMMDD.{txt,json}
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
STORE = Path("/cursor/stores/self/betting")
STAT_FIELD = {
    "PTS": "points",
    "REB": "totalRebounds",
    "AST": "assists",
    "STL": "steals",
    "BLK": "blocks",
    "3PT": "threes",
    "SOG": "shots",
}


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = s.replace(".", "").replace("'", "").replace("'", "")
    s = re.sub(r"\s+", " ", s).strip()
    # drop suffixes Jr/Sr/II/III for matching
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", s).strip()
    return s


def _threes(row: dict) -> float:
    raw = row.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted") or "0-0"
    try:
        return float(str(raw).split("-")[0])
    except Exception:
        return 0.0


def _val(row: dict, stat: str) -> float | None:
    if stat == "3PT":
        return _threes(row)
    key = STAT_FIELD.get(stat)
    if not key:
        return None
    v = row.get(key)
    if v is None or v == "":
        return None
    try:
        return float(v)
    except Exception:
        return None


def load_sheets() -> dict:
    for p in (
        STORE / "GATE_SHEETS_20261107.json",
        OUT / "out" / "GATE_SHEETS_20261107.json",
        STORE / "GATE_TODAY.json",
    ):
        if p.name == "GATE_TODAY.json" and p.exists():
            meta = json.loads(p.read_text())
            sp = Path(meta.get("sheets_path", ""))
            if sp.exists():
                return json.loads(sp.read_text())
        elif p.exists() and "SHEETS" in p.name:
            return json.loads(p.read_text())
    # fallback any GATE_SHEETS
    cands = list(STORE.glob("GATE_SHEETS_*.json")) + list((OUT / "out").glob("GATE_SHEETS_*.json"))
    if not cands:
        raise SystemExit("no GATE_SHEETS found — run require_gate / run_gate first")
    cands.sort()
    return json.loads(cands[-1].read_text())


def sheet_index(sheets: dict) -> dict[str, tuple[str, dict]]:
    idx = {}
    for name, rec in sheets.items():
        if not isinstance(rec, dict) or not rec.get("ok"):
            continue
        idx[_norm(name)] = (name, rec)
    return idx


def grade_one(rec: dict, stat: str, line: float, n: int = 7) -> dict:
    rows = list(rec.get("rows") or [])
    # most recent first in sheets; take first n RS
    sample = rows[:n]
    vals = []
    for r in sample:
        v = _val(r, stat)
        if v is not None:
            vals.append(v)
    if not vals:
        return {"hits": 0, "n": 0, "vals": [], "call": "SKIP"}
    hits = sum(1 for v in vals if v > line)
    nn = len(vals)
    rate = hits / nn if nn else 0
    if nn >= 5 and hits == nn:
        call = "KEEP"
    elif nn >= 5 and hits >= nn - 1:
        call = "RISK-KEEP"
    elif nn >= 5 and rate >= 0.7:
        call = "RISK"
    else:
        call = "CUT"
    return {
        "hits": hits,
        "n": nn,
        "vals": vals,
        "misses": [v for v in vals if v <= line],
        "call": call,
        "athlete_id": rec.get("athlete_id"),
        "team": rec.get("team"),
    }


def main() -> int:
    day = datetime.now(timezone.utc).date().isoformat()
    stamp = day.replace("-", "")
    mains_path = OUT / f"posted-mains-{stamp}.json"
    if not mains_path.exists():
        raise SystemExit(f"missing {mains_path} — run pull_posted_mains.py first")
    mains = json.loads(mains_path.read_text())["rows"]
    sheets = load_sheets()
    idx = sheet_index(sheets)

    graded = []
    unmatched = []
    for m in mains:
        key = _norm(m["player"])
        hit = idx.get(key)
        if not hit:
            # try last-name+first token
            parts = key.split()
            if len(parts) >= 2:
                alt = f"{parts[0]} {parts[-1]}"
                hit = idx.get(alt)
            if not hit:
                unmatched.append(m)
                continue
        name, rec = hit
        # NHL SOG: take L10; NBA counting: L7
        n = 10 if m["stat"] == "SOG" else 7
        g = grade_one(rec, m["stat"], float(m["line"]), n=n)
        graded.append(
            {
                **m,
                "sheet_name": name,
                **g,
            }
        )

    keep = [g for g in graded if g["call"] == "KEEP"]
    risk_keep = [g for g in graded if g["call"] == "RISK-KEEP"]
    risk = [g for g in graded if g["call"] == "RISK"]
    cut = [g for g in graded if g["call"] == "CUT"]

    def sort_key(g):
        return (-(g["hits"] / g["n"] if g["n"] else 0), g["stat"], g["sheet_name"])

    lines = [
        f"POSTED-MAIN CARD — {day}",
        "Source: Betravon consensus mains + GATE RS sheets. Soft floors NOT listed.",
        f"Graded {len(graded)} / unmatched {len(unmatched)}",
        "",
        "=== KEEP (perfect clear at POSTED main) ===",
    ]
    for g in sorted(keep, key=sort_key):
        lines.append(
            f"  {g['hits']}/{g['n']}  {g['sheet_name']} O{g['line']} {g['stat']}  "
            f"{g.get('team')} vs {g.get('opponent')}  id={g.get('athlete_id')}  "
            f"L={g['vals']}"
        )
    lines.append("\n=== RISK-KEEP (one miss at POSTED main) ===")
    for g in sorted(risk_keep, key=sort_key):
        lines.append(
            f"  {g['hits']}/{g['n']}  {g['sheet_name']} O{g['line']} {g['stat']}  "
            f"miss={g['misses']}  id={g.get('athlete_id')}"
        )
    lines.append("\n=== RISK (≈70%+ at POSTED main) ===")
    for g in sorted(risk, key=sort_key)[:40]:
        lines.append(
            f"  {g['hits']}/{g['n']}  {g['sheet_name']} O{g['line']} {g['stat']}  miss={g['misses']}"
        )
    lines.append("\n=== CUT at POSTED main (do not bet) ===")
    lines.append(f"  {len(cut)} props fail at book main — including soft-floor favorites.")
    # highlight slip-relevant cuts
    watch = ("jokic", "wagner", "alexander-walker", "hartenstein", "wemby", "wembanyama", "sharpe", "randle")
    for g in sorted(cut, key=sort_key):
        blob = _norm(g["sheet_name"])
        if any(w in blob for w in watch) or g["stat"] in ("SOG",):
            if g["hits"] / g["n"] < 0.85:
                lines.append(
                    f"  {g['hits']}/{g['n']}  {g['sheet_name']} O{g['line']} {g['stat']}  miss={g['misses']}"
                )

    # clean slips from KEEP only
    lines.append("\n=== CLEAN SLIP (KEEP @ posted mains only) ===")
    # diversify: max 2 per game-ish, prefer mix of cats
    picked = []
    used_players = set()
    for g in sorted(keep, key=sort_key):
        if g["sheet_name"] in used_players:
            continue
        if g["stat"] in ("STL",) and len(picked) < 6:
            # steals ok as add not spine — skip for first 4
            if len(picked) < 4:
                continue
        picked.append(g)
        used_players.add(g["sheet_name"])
        if len(picked) >= 8:
            break
    if not picked:
        lines.append("  (no perfect KEEP at posted mains — use RISK-KEEP short card)")
        for g in sorted(risk_keep, key=sort_key)[:5]:
            lines.append(
                f"  {g['hits']}/{g['n']}  {g['sheet_name']} O{g['line']} {g['stat']}"
            )
    else:
        for i, g in enumerate(picked, 1):
            lines.append(
                f"  {i}. {g['sheet_name']} O{g['line']} {g['stat']}  "
                f"({g['hits']}/{g['n']})  {g.get('team')} vs {g.get('opponent')}"
            )

    lines.append(
        "\nDONE: No soft floors. If a KEEP number is missing on HR, skip that leg — "
        "do not invent a lower alt."
    )

    payload = {
        "date": day,
        "graded": graded,
        "keep": keep,
        "risk_keep": risk_keep,
        "risk": risk,
        "cut_n": len(cut),
        "unmatched_n": len(unmatched),
        "clean_slip": picked,
    }
    tx = OUT / f"posted-card-{stamp}.txt"
    js = OUT / f"posted-card-{stamp}.json"
    tx.write_text("\n".join(lines))
    js.write_text(json.dumps(payload, indent=2))
    print(tx.read_text())
    print(f"\nwrote {tx}")
    print(f"wrote {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
