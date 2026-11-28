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
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
STORE = Path("/cursor/stores/self/betting")
UA = {"User-Agent": "Mozilla/5.0 YWP-grade-posted-card"}
STAT_FIELD = {
    "PTS": "points",
    "REB": "totalRebounds",
    "AST": "assists",
    "STL": "steals",
    "BLK": "blocks",
    "3PT": "threes",
    "SOG": "shots",
}
BINARY_STATS = {"STL", "BLK"}


def _http_get(url: str, timeout: int = 25) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _is_binary(stat: str, line: float) -> bool:
    if stat in BINARY_STATS:
        return True
    if stat == "3PT" and float(line) <= 0.5:
        return True
    return False


def fetch_injury_map(day: str) -> dict[str, dict]:
    """name_norm -> {status, fantasy, out, gtd, raw_status} from ESPN summaries."""
    meta = None
    for p in (STORE / "GATE_TODAY.json", OUT / "out" / "GATE_TODAY.json"):
        if p.exists():
            try:
                meta = json.loads(p.read_text())
                break
            except Exception:
                continue
    games = []
    if meta and meta.get("date") == day.replace("-", ""):
        for sport in ("NBA", "NHL"):
            games.extend(meta.get("games", {}).get(sport) or [])
    out: dict[str, dict] = {}
    for g in games:
        eid = g.get("id")
        sport = (g.get("sport") or "").lower()
        if sport == "nba":
            url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={eid}"
        elif sport == "nhl":
            url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event={eid}"
        else:
            continue
        try:
            s = _http_get(url)
        except Exception:
            continue
        for tb in s.get("injuries") or []:
            team = (tb.get("team") or {}).get("abbreviation")
            for inj in tb.get("injuries") or []:
                name = (inj.get("athlete") or {}).get("displayName")
                if not name:
                    continue
                st = (inj.get("status") or "").lower()
                fant = (
                    ((inj.get("details") or {}).get("fantasyStatus") or {}).get(
                        "abbreviation"
                    )
                    or ""
                ).upper()
                is_out = st == "out" or fant in ("OUT", "OFS") or "out" in st
                is_gtd = (
                    fant in ("GTD", "DTD", "Q")
                    or "day-to-day" in st
                    or "doubtful" in st
                    or "questionable" in st
                )
                # Out always wins over GTD fantasy tag
                tag = "OUT" if is_out else ("GTD" if is_gtd else "TAGGED")
                out[_norm(name)] = {
                    "name": name,
                    "team": team,
                    "status": inj.get("status"),
                    "fantasy": fant,
                    "tag": tag,
                    "out": is_out,
                    "gtd": (not is_out) and is_gtd,
                }
    # persist for audits
    try:
        stamp = day.replace("-", "")
        (OUT / f"injuries-{stamp}.json").write_text(
            json.dumps(list(out.values()), indent=2)
        )
        (STORE / f"injuries-{stamp}.json").write_text(
            json.dumps(list(out.values()), indent=2)
        )
    except Exception:
        pass
    return out


def status_for(name: str, inj: dict[str, dict]) -> str:
    hit = inj.get(_norm(name))
    if not hit:
        return "CLEAR"
    return hit.get("tag") or "TAGGED"


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
    # Prefer GATE_TODAY → sheets_path (correct slate), then newest GATE_SHEETS_*.
    for meta_path in (STORE / "GATE_TODAY.json", OUT / "out" / "GATE_TODAY.json"):
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except Exception:
            continue
        sp = Path(meta.get("sheets_path") or "")
        if sp.exists():
            return json.loads(sp.read_text())
        day = meta.get("date")
        if day:
            for alt in (STORE / f"GATE_SHEETS_{day}.json", OUT / "out" / f"GATE_SHEETS_{day}.json"):
                if alt.exists():
                    return json.loads(alt.read_text())
    cands = list(STORE.glob("GATE_SHEETS_*.json")) + list((OUT / "out").glob("GATE_SHEETS_*.json"))
    if not cands:
        raise SystemExit("no GATE_SHEETS found — run require_gate / run_gate first")
    cands.sort(key=lambda p: p.stat().st_mtime)
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
    inj = fetch_injury_map(day)

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
        st = status_for(name, inj)
        binary = _is_binary(m["stat"], float(m["line"]))
        vals = g.get("vals") or []
        line = float(m["line"])
        cush = min((v - line) for v in vals) if vals else None
        # Form KEEP is not playable KEEP until ACTIVE + non-hook scrub
        playable = g["call"]
        ban_reason = None
        if st == "OUT":
            playable = "BAN_OUT"
            ban_reason = "OUT/inactive — never SAFE/PRIMARY/CLEAN"
        elif st == "GTD":
            playable = "BAN_GTD"
            ban_reason = "GTD/Q — HOLD until ACTIVE confirm"
        elif g["call"] == "KEEP" and binary:
            playable = "KEEP_BINARY"
            ban_reason = "binary (STL/BLK/O0.5 3PT) — add only, not CLEAN spine"
        elif g["call"] == "KEEP" and cush is not None and cush < 1.0:
            playable = "KEEP_HOOK"
            ban_reason = f"hook cush_min={cush} — PRIMARY max unless OUT-driven"
        graded.append(
            {
                **m,
                "sheet_name": name,
                **g,
                "inj_status": st,
                "binary": binary,
                "cush_min": cush,
                "playable": playable,
                "ban_reason": ban_reason,
            }
        )

    # Raw form buckets (audit)
    keep_form = [g for g in graded if g["call"] == "KEEP"]
    risk_keep = [g for g in graded if g["call"] == "RISK-KEEP"]
    risk = [g for g in graded if g["call"] == "RISK"]
    cut = [g for g in graded if g["call"] == "CUT"]
    # Playable KEEP = CLEAR + non-binary (hook flagged separately)
    keep = [g for g in graded if g["playable"] == "KEEP"]
    keep_hook = [g for g in graded if g["playable"] == "KEEP_HOOK"]
    keep_binary = [g for g in graded if g["playable"] == "KEEP_BINARY"]
    ban_status = [g for g in graded if g["playable"] in ("BAN_OUT", "BAN_GTD")]

    def sort_key(g):
        cush = g.get("cush_min")
        cush_rank = -(cush if cush is not None else -99)
        return (
            cush_rank,
            -(g["hits"] / g["n"] if g["n"] else 0),
            g["stat"],
            g["sheet_name"],
        )

    lines = [
        f"POSTED-MAIN CARD — {day}",
        "Source: Betravon consensus mains + GATE RS sheets. Soft floors NOT listed.",
        "Scrub: OUT/GTD demoted · binary (STL/BLK/O0.5 3PT) not CLEAN spine · hook cush<1 flagged.",
        f"Graded {len(graded)} / unmatched {len(unmatched)} / injuries_tagged={len(inj)}",
        "",
        "=== BAN (OUT / GTD — form KEEP means nothing) ===",
    ]
    if not ban_status:
        lines.append("  (none tagged)")
    for g in sorted(ban_status, key=lambda x: (x["playable"], x["sheet_name"])):
        lines.append(
            f"  {g['playable']}  {g['hits']}/{g['n']}  {g['sheet_name']} O{g['line']} {g['stat']}  "
            f"inj={g['inj_status']}  — {g['ban_reason']}"
        )

    lines.append("\n=== KEEP PLAYABLE (ACTIVE · non-binary · cush≥1) ===")
    if not keep:
        lines.append("  (none — slate thin at posted mains after scrub)")
    for g in sorted(keep, key=sort_key):
        lines.append(
            f"  {g['hits']}/{g['n']}  {g['sheet_name']} O{g['line']} {g['stat']}  "
            f"{g.get('team')} vs {g.get('opponent')}  id={g.get('athlete_id')}  "
            f"cush_min={g.get('cush_min')}  L={g['vals']}"
        )

    lines.append("\n=== KEEP HOOK (ACTIVE · clear · cush<1 — PRIMARY max, not SAFE spine) ===")
    for g in sorted(keep_hook, key=sort_key):
        lines.append(
            f"  {g['hits']}/{g['n']}  {g['sheet_name']} O{g['line']} {g['stat']}  "
            f"cush_min={g.get('cush_min')}  L={g['vals']}  id={g.get('athlete_id')}"
        )

    lines.append("\n=== KEEP BINARY (add only — never CLEAN/SAFE identity) ===")
    for g in sorted(keep_binary, key=sort_key):
        lines.append(
            f"  {g['hits']}/{g['n']}  {g['sheet_name']} O{g['line']} {g['stat']}  "
            f"L={g['vals']}  id={g.get('athlete_id')}"
        )

    lines.append("\n=== FORM KEEP RAW (pre-scrub audit) ===")
    for g in sorted(keep_form, key=sort_key):
        lines.append(
            f"  {g['hits']}/{g['n']}  {g['sheet_name']} O{g['line']} {g['stat']}  "
            f"playable={g['playable']} inj={g['inj_status']} binary={g['binary']} cush={g.get('cush_min')}"
        )

    lines.append("\n=== RISK-KEEP (one miss at POSTED main) ===")
    for g in sorted(risk_keep, key=sort_key):
        if g["inj_status"] in ("OUT", "GTD"):
            continue
        lines.append(
            f"  {g['hits']}/{g['n']}  {g['sheet_name']} O{g['line']} {g['stat']}  "
            f"miss={g['misses']}  id={g.get('athlete_id')}"
        )
    lines.append("\n=== RISK (≈70%+ at POSTED main) ===")
    for g in sorted(risk, key=sort_key)[:40]:
        if g["inj_status"] in ("OUT", "GTD"):
            continue
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
            if g["n"] and g["hits"] / g["n"] < 0.85:
                lines.append(
                    f"  {g['hits']}/{g['n']}  {g['sheet_name']} O{g['line']} {g['stat']}  miss={g['misses']}"
                )

    # CLEAN SLIP: playable KEEP first, then hooks if empty — never OUT/GTD/binary
    lines.append("\n=== CLEAN SLIP (scrubbed — no OUT/GTD/binary spines) ===")
    picked = []
    used_players = set()
    pool = sorted(keep, key=sort_key) + sorted(keep_hook, key=sort_key)
    for g in pool:
        if g["sheet_name"] in used_players:
            continue
        if g["playable"] == "KEEP_HOOK" and len(picked) < 2 and keep:
            # prefer real KEEP before filling with hooks
            continue
        picked.append(g)
        used_players.add(g["sheet_name"])
        if len(picked) >= 6:
            break
    # if still thin, allow hooks
    if len(picked) < 3:
        for g in sorted(keep_hook, key=sort_key):
            if g["sheet_name"] in used_players:
                continue
            picked.append(g)
            used_players.add(g["sheet_name"])
            if len(picked) >= 4:
                break
    if not picked:
        lines.append("  (no scrubbed KEEP — use RISK-KEEP short card + weather sides; do NOT promote binary/OUT)")
        for g in sorted(risk_keep, key=sort_key)[:5]:
            if g["inj_status"] in ("OUT", "GTD") or g.get("binary"):
                continue
            lines.append(
                f"  {g['hits']}/{g['n']}  {g['sheet_name']} O{g['line']} {g['stat']}  inj={g['inj_status']}"
            )
    else:
        for i, g in enumerate(picked, 1):
            tag = "" if g["playable"] == "KEEP" else f"  [{g['playable']}]"
            lines.append(
                f"  {i}. {g['sheet_name']} O{g['line']} {g['stat']}  "
                f"({g['hits']}/{g['n']})  cush={g.get('cush_min')}  "
                f"{g.get('team')} vs {g.get('opponent')}{tag}"
            )

    lines.append(
        "\nDONE: No soft floors. OUT/GTD never on CLEAN. Binary ≠ SAFE spine. "
        "Hook clears = PRIMARY max. If a KEEP number is missing on HR, skip — do not invent a lower alt."
    )

    payload = {
        "date": day,
        "graded": graded,
        "keep": keep,
        "keep_hook": keep_hook,
        "keep_binary": keep_binary,
        "ban_status": ban_status,
        "keep_form_raw": keep_form,
        "risk_keep": risk_keep,
        "risk": risk,
        "cut_n": len(cut),
        "unmatched_n": len(unmatched),
        "injuries_n": len(inj),
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
