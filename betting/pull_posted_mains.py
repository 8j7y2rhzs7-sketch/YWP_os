#!/usr/bin/env python3
"""
Pull consensus POSTED MAIN prop lines from Betravon (no API key, no screenshots).

These are the numbers books actually list — not soft floors. Use as the
default actionable board when ODDS_API_KEY / Hard Rock feed is unavailable.
When ODDS_API_KEY is set, prefer pull_hr_odds.py for hardrockbet-tagged rows.

Usage:
  python3 betting/pull_posted_mains.py
  python3 betting/pull_posted_mains.py --sports nba,nhl

Writes:
  betting/posted-mains-YYYYMMDD.{txt,json}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
UA = {"User-Agent": "Mozilla/5.0 (compatible; ywp-posted-mains/1.0)"}

NBA_STATS = ("points", "rebounds", "assists", "threes", "steals", "blocks")
NHL_STATS = ("shots-on-goal",)
URLS = {
    "nba": "https://www.betravon.com/nba/player-props/{stat}",
    "nhl": "https://www.betravon.com/nhl/player-props/{stat}",
}
STAT_LABEL = {
    "points": "PTS",
    "rebounds": "REB",
    "assists": "AST",
    "threes": "3PT",
    "steals": "STL",
    "blocks": "BLK",
    "shots-on-goal": "SOG",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_betravon(html: str) -> list[dict]:
    m = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', html, flags=re.S
    )
    if not m:
        return []
    data = json.loads(m.group(1))
    rows = (
        data.get("props", {})
        .get("pageProps", {})
        .get("data", {})
        .get("rows", [])
    )
    return rows if isinstance(rows, list) else []


def pull_sport(sport: str, stats: tuple[str, ...]) -> list[dict]:
    out: list[dict] = []
    base = URLS[sport]
    for stat in stats:
        url = base.format(stat=stat)
        try:
            html = fetch(url)
            rows = parse_betravon(html)
        except Exception as e:
            print(f"{sport}/{stat}: FAIL {e}", file=sys.stderr)
            continue
        print(f"{sport}/{stat}: {len(rows)} posted mains")
        for r in rows:
            line = r.get("line")
            if line is None:
                continue
            out.append(
                {
                    "source": "betravon",
                    "sport": sport,
                    "player": r.get("player"),
                    "slug": r.get("slug"),
                    "team": r.get("team"),
                    "opponent": r.get("opponent"),
                    "is_home": r.get("isHome"),
                    "game_time": r.get("gameTime"),
                    "stat": STAT_LABEL.get(stat, stat.upper()),
                    "stat_slug": stat,
                    "line": float(line),
                    "books": r.get("books"),
                    "l10_n": r.get("l10n"),
                    "l10_over": r.get("l10over"),
                    "posted_kind": "MAIN",
                    "hr_confirmed": False,
                }
            )
    return out


def render(day: str, rows: list[dict]) -> str:
    lines = [
        f"POSTED MAINS (Betravon consensus) — {day}",
        "These are book-posted mains across ~12–14 books — NOT soft floors.",
        "Actionable when ODDS_API_KEY / HR feed missing. Soft alts = internal only.",
        "Optional upgrade: set ODDS_API_KEY → python3 betting/pull_hr_odds.py for hardrockbet tags.",
        "",
    ]
    by: dict[str, list[dict]] = {}
    for r in rows:
        key = f"{r['sport'].upper()} {r.get('team','?')}@{r.get('opponent','?')} · {r['player']}"
        by.setdefault(key, []).append(r)
    for key in sorted(by):
        lines.append(key)
        for r in sorted(by[key], key=lambda x: (x["stat"], x["line"])):
            lines.append(
                f"  {r['stat']} O{r['line']}  books={r.get('books')}  "
                f"betravon_L10={r.get('l10_over')}/{r.get('l10_n')}"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sports", default="nba,nhl")
    args = ap.parse_args()
    sports = [s.strip().lower() for s in args.sports.split(",") if s.strip()]
    day = datetime.now(timezone.utc).date().isoformat()
    rows: list[dict] = []
    for sport in sports:
        if sport == "nba":
            rows.extend(pull_sport("nba", NBA_STATS))
        elif sport == "nhl":
            rows.extend(pull_sport("nhl", NHL_STATS))
        else:
            print(f"skip {sport}", file=sys.stderr)

    stamp = day.replace("-", "")
    payload = {
        "date": day,
        "method": "betravon_posted_mains",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n": len(rows),
        "rows": rows,
        "note": "Consensus mains ≈ what HR shows. Soft floors stay internal.",
    }
    js = OUT / f"posted-mains-{stamp}.json"
    tx = OUT / f"posted-mains-{stamp}.txt"
    js.write_text(json.dumps(payload, indent=2))
    tx.write_text(render(day, rows))
    print(f"wrote {tx} ({len(rows)} lines)")
    print(f"wrote {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
