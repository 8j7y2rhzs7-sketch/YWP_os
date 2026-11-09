#!/usr/bin/env python3
"""
Pull Hard Rock–tagged lines from public web mirrors — NO ODDS_API_KEY needed.

Sources:
  - agentbets.ai/odds/hardrockbet/{sport}/  → HR ML / spread / total
  - dynatyze.com/betting/nba/props.md       → props; keeps rows that cite Hard Rock
  - ESPN scoreboard                         → slate inventory / backup mains (not HR)

Usage:
  python3 betting/pull_hr_web.py
  python3 betting/pull_hr_web.py --sports nba,nhl,ncaaf,ncaab,nfl

Writes betting/hr-web-YYYYMMDD.{txt,json}

Gaps vs HR app (still need a screenshot only for these):
  - soft alt ladders, SGP prices, live micros, many player props not mirrored
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

OUT = Path(__file__).resolve().parent
UA = {"User-Agent": "Mozilla/5.0 (compatible; ywp-hr-web/1.0)"}

SPORT_PAGES = {
    "nba": "https://agentbets.ai/odds/hardrockbet/nba/",
    "nhl": "https://agentbets.ai/odds/hardrockbet/nhl/",
    "nfl": "https://agentbets.ai/odds/hardrockbet/nfl/",
    "ncaaf": "https://agentbets.ai/odds/hardrockbet/ncaaf/",
    "ncaab": "https://agentbets.ai/odds/hardrockbet/ncaab/",
}

PROP_MD = {
    "nba": "https://dynatyze.com/betting/nba/props.md",
    "nhl": "https://dynatyze.com/betting/nhl/props.md",
    "nfl": "https://dynatyze.com/betting/nfl/props.md",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def _html_to_lines(html: str) -> list[str]:
    cleaned = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.I)
    cleaned = re.sub(r"<style[\s\S]*?</style>", "", cleaned, flags=re.I)
    text = unescape(re.sub(r"<[^>]+>", "\n", cleaned))
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def parse_agentbets_table(html: str, sport: str) -> list[dict]:
    """Parse agentbets HR pages — table cells render as consecutive lines."""
    lines = _html_to_lines(html)
    rows: list[dict] = []
    ml_re = re.compile(r"^[+\−\-–]?\d+$|^—$|^-$")
    # Find header then walk 6-line records: game, time, away_ml, home_ml, spread, total
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith("Matchup (away"))
    except StopIteration:
        return rows
    i = start + 1
    # skip column headers if present as separate lines
    while i < len(lines) and lines[i] in {
        "Time",
        "Away ML",
        "Home ML",
        "Home spread",
        "Total (O / U)",
    }:
        i += 1
    while i + 5 < len(lines):
        game = lines[i]
        if "@" not in game:
            break
        when, away_ml, home_ml, spread, total = lines[i + 1 : i + 6]
        if "PM" not in when and "AM" not in when:
            i += 1
            continue
        if not (ml_re.match(away_ml.replace("★", "").strip()) or away_ml in {"—", "-"} or "★" in away_ml):
            i += 1
            continue
        rows.append(
            {
                "source": "agentbets",
                "book": "hardrockbet",
                "sport": sport,
                "game": game,
                "when": when,
                "away_ml": away_ml,
                "home_ml": home_ml,
                "home_spread": spread,
                "total": total,
                "hr_confirmed": True,
            }
        )
        i += 6
    return rows


def parse_dynatyze_props(md: str, sport: str) -> tuple[list[dict], list[dict]]:
    """Return (hr_cited_rows, other_prop_rows)."""
    hr_rows: list[dict] = []
    other: list[dict] = []
    for line in md.splitlines():
        if not line.startswith("|") or line.startswith("| Player") or re.match(r"^\|\s*-+", line):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 8:
            continue
        player, game, start, prop, line_v, best_o, best_u, books = parts[:8]
        row = {
            "source": "dynatyze",
            "sport": sport,
            "player": player,
            "game": game,
            "when": start,
            "prop": prop,
            "line": line_v,
            "best_over": best_o,
            "best_under": best_u,
            "books": books,
        }
        blob = f"{best_o} {best_u}".lower()
        if "hard rock" in blob:
            row["book"] = "hardrockbet"
            row["hr_confirmed"] = True
            # which side cites HR
            if "hard rock" in best_o.lower():
                row["hr_side"] = "over"
                row["hr_price"] = best_o
            else:
                row["hr_side"] = "under"
                row["hr_price"] = best_u
            hr_rows.append(row)
        else:
            row["book"] = None
            row["hr_confirmed"] = False
            other.append(row)
    return hr_rows, other


def render(day: str, game_rows: list[dict], hr_props: list[dict], other_props: list[dict]) -> str:
    lines = [
        f"HARD ROCK board (web mirrors) — {day}",
        "NO API KEY. Sources: agentbets (HR game lines) + dynatyze (props citing Hard Rock).",
        "Verify before bet — mirrors lag. Soft alts / SGP / live = screenshot only.",
        "",
        "=== HR GAME LINES (confirmed hardrockbet) ===",
    ]
    by_sport: dict[str, list[dict]] = {}
    for r in game_rows:
        by_sport.setdefault(r["sport"].upper(), []).append(r)
    for sport, items in sorted(by_sport.items()):
        lines.append(f"\n-- {sport} --")
        for r in items:
            lines.append(
                f"  {r['game']} | {r['when']} | "
                f"ML {r['away_ml']}/{r['home_ml']} | spr {r['home_spread']} | tot {r['total']}"
            )

    lines.append("\n=== HR-CITED PLAYER PROPS (dynatyze best-price = Hard Rock) ===")
    if not hr_props:
        lines.append("  (none on mirror right now — screenshot props you care about)")
    for r in hr_props:
        lines.append(
            f"  {r['player']} {r['prop']} {r['line']} · HR {r.get('hr_side')} {r.get('hr_price')} · {r['game']}"
        )

    lines.append("\n=== PROPS ON OTHER BOOKS ONLY (NOT HR-confirmed — do not bet as HR) ===")
    lines.append(f"  {len(other_props)} props mirrored without Hard Rock as best price.")
    lines.append("  Use for research; HR number needs app/API/screenshot.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sports", default="nba,nhl,ncaaf,ncaab,nfl")
    args = ap.parse_args()
    sports = [s.strip().lower() for s in args.sports.split(",") if s.strip()]
    day = datetime.now(timezone.utc).date().isoformat()

    game_rows: list[dict] = []
    for s in sports:
        url = SPORT_PAGES.get(s)
        if not url:
            print(f"skip unknown sport {s}", file=sys.stderr)
            continue
        try:
            html = fetch(url)
            rows = parse_agentbets_table(html, s)
            print(f"{s}: {len(rows)} HR game lines from agentbets")
            game_rows.extend(rows)
        except Exception as e:
            print(f"{s}: FAIL {e}", file=sys.stderr)

    hr_props: list[dict] = []
    other_props: list[dict] = []
    for s in sports:
        url = PROP_MD.get(s)
        if not url:
            continue
        try:
            md = fetch(url)
            hr, other = parse_dynatyze_props(md, s)
            print(f"{s} props: {len(hr)} HR-cited / {len(other)} other-book")
            hr_props.extend(hr)
            other_props.extend(other)
        except Exception as e:
            print(f"{s} props: FAIL {e}", file=sys.stderr)

    payload = {
        "date": day,
        "method": "web_mirror_no_api_key",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "game_lines": game_rows,
        "hr_props": hr_props,
        "other_props_research_only": other_props,
        "gaps": [
            "soft alt ladders",
            "SGP prices",
            "live micros",
            "most HR props not shown as best price on dynatyze",
        ],
    }
    stamp = day.replace("-", "")
    js = OUT / f"hr-web-{stamp}.json"
    tx = OUT / f"hr-web-{stamp}.txt"
    js.write_text(json.dumps(payload, indent=2))
    tx.write_text(render(day, game_rows, hr_props, other_props))
    print(f"wrote {tx}")
    print(f"wrote {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
