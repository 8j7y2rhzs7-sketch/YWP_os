#!/usr/bin/env python3
"""
Pull Hard Rock–posted lines from The Odds API for today's card.

Usage:
  export ODDS_API_KEY=...   # or set in Cursor / env secrets — never paste in chat
  python3 betting/pull_hr_odds.py
  python3 betting/pull_hr_odds.py --sports nba,nhl,nfl,ncaaf
  python3 betting/pull_hr_odds.py --no-props          # game lines only (cheaper)
  python3 betting/pull_hr_odds.py --date 2026-11-06

Writes:
  betting/hr-lines-YYYYMMDD.json
  betting/hr-lines-YYYYMMDD.txt

Rule: only rows tagged book=hardrockbet are actionable KEEP candidates.
Other books in the JSON are research / missing-on-HR markers only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

BASE = "https://api.the-odds-api.com"
HR_BOOK = "hardrockbet"

SPORTS = {
    "nba": "basketball_nba",
    "nhl": "icehockey_nhl",
    "nfl": "americanfootball_nfl",
    "ncaaf": "americanfootball_ncaaf",
    "ncaab": "basketball_ncaab",
    "mlb": "baseball_mlb",
}

PROP_MARKETS = {
    "nba": (
        "player_points,player_rebounds,player_assists,"
        "player_threes,player_steals,player_blocks"
    ),
    "nhl": "player_shots_on_goal,player_points,player_assists,player_goals",
    "nfl": (
        "player_pass_yds,player_rush_yds,player_reception_yds,"
        "player_receptions,player_pass_tds,player_rush_attempts"
    ),
    "ncaaf": "player_pass_yds,player_rush_yds,player_reception_yds,player_receptions",
    "ncaab": "player_points,player_rebounds,player_assists",
    "mlb": "batter_hits,batter_total_bases,pitcher_strikeouts",
}

OUT = Path(__file__).resolve().parent


def _key() -> str:
    key = os.environ.get("ODDS_API_KEY") or os.environ.get("YWP_ODDS_API_KEY") or ""
    if not key:
        print(
            "ODDS_API_KEY is not set.\n"
            "Add it in Cursor Secrets / your env (the-odds-api.com free key works).\n"
            "Do not paste the key into chat.",
            file=sys.stderr,
        )
        sys.exit(2)
    return key


def _get(path: str, params: dict) -> tuple[object, dict]:
    q = urllib.parse.urlencode({"apiKey": _key(), **params})
    url = f"{BASE}{path}?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "ywp-hr-pull/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            data = json.loads(resp.read().decode())
            return data, headers
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        raise RuntimeError(f"HTTP {e.code} {path}: {body}") from e


def _hr_markets(bookmakers: list) -> list[dict]:
    for b in bookmakers or []:
        if b.get("key") == HR_BOOK:
            return b.get("markets") or []
    return []


def _flatten_game(sport: str, event: dict) -> list[dict]:
    rows = []
    home = event.get("home_team", "")
    away = event.get("away_team", "")
    eid = event.get("id", "")
    start = event.get("commence_time", "")
    markets = _hr_markets(event.get("bookmakers") or [])
    if not markets:
        rows.append(
            {
                "sport": sport,
                "event_id": eid,
                "game": f"{away} @ {home}",
                "start": start,
                "book": None,
                "market": "MISSING_ON_HR",
                "note": "event on Odds API but no hardrockbet bookmaker payload",
            }
        )
        return rows
    for m in markets:
        mkey = m.get("key", "")
        for o in m.get("outcomes") or []:
            rows.append(
                {
                    "sport": sport,
                    "event_id": eid,
                    "game": f"{away} @ {home}",
                    "start": start,
                    "book": HR_BOOK,
                    "market": mkey,
                    "name": o.get("name"),
                    "description": o.get("description"),
                    "point": o.get("point"),
                    "price": o.get("price"),
                }
            )
    return rows


def pull_sport(sport: str, want_props: bool) -> tuple[list[dict], dict]:
    sport_key = SPORTS[sport]
    data, headers = _get(
        f"/v4/sports/{sport_key}/odds",
        {
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american",
            "bookmakers": HR_BOOK,
        },
    )
    meta = {
        "remaining": headers.get("x-requests-remaining"),
        "used": headers.get("x-requests-used"),
    }
    if not isinstance(data, list):
        return [], meta

    rows: list[dict] = []
    for event in data:
        rows.extend(_flatten_game(sport, event))

    if want_props and sport in PROP_MARKETS:
        for event in data:
            eid = event.get("id")
            if not eid:
                continue
            try:
                pdata, pheaders = _get(
                    f"/v4/sports/{sport_key}/events/{eid}/odds",
                    {
                        "regions": "us",
                        "markets": PROP_MARKETS[sport],
                        "oddsFormat": "american",
                        "bookmakers": HR_BOOK,
                    },
                )
                meta["remaining"] = pheaders.get("x-requests-remaining", meta.get("remaining"))
            except RuntimeError as exc:
                rows.append(
                    {
                        "sport": sport,
                        "event_id": eid,
                        "game": f"{event.get('away_team')} @ {event.get('home_team')}",
                        "book": HR_BOOK,
                        "market": "PROPS_ERROR",
                        "note": str(exc)[:200],
                    }
                )
                continue
            if isinstance(pdata, dict):
                rows.extend(_flatten_game(sport, pdata))

    return rows, meta


def render_txt(rows: list[dict], day: str, meta: dict) -> str:
    lines = [
        f"HARD ROCK lines via The Odds API — {day}",
        f"requests remaining≈{meta.get('remaining')} used≈{meta.get('used')}",
        "ONLY hardrockbet rows are actionable. Screenshots still win ties.",
        "",
    ]
    by_game: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("market") in {"MISSING_ON_HR", "PROPS_ERROR"}:
            key = r.get("game") or "unknown"
            by_game.setdefault(key, []).append(r)
            continue
        if r.get("book") != HR_BOOK:
            continue
        key = f"{r.get('sport','').upper()} | {r.get('game')}"
        by_game.setdefault(key, []).append(r)

    for game, items in sorted(by_game.items()):
        lines.append(f"=== {game} ===")
        for r in items:
            if r.get("market") == "MISSING_ON_HR":
                lines.append("  (no Hard Rock bookmaker on Odds API for this event)")
                continue
            if r.get("market") == "PROPS_ERROR":
                lines.append(f"  props error: {r.get('note')}")
                continue
            desc = r.get("description") or ""
            name = r.get("name") or ""
            point = r.get("point")
            price = r.get("price")
            mkt = r.get("market")
            who = f"{desc} " if desc else ""
            pt = f" {point}" if point is not None else ""
            lines.append(f"  {mkt}: {who}{name}{pt} ({price})")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Pull Hard Rock lines from The Odds API")
    ap.add_argument("--sports", default="nba,nhl,nfl,ncaaf", help="comma list")
    ap.add_argument("--no-props", action="store_true", help="skip player props (saves quota)")
    ap.add_argument("--date", default=None, help="label date YYYY-MM-DD (default today UTC)")
    args = ap.parse_args()

    day = args.date or datetime.now(timezone.utc).date().isoformat()
    sports = [s.strip().lower() for s in args.sports.split(",") if s.strip()]
    for s in sports:
        if s not in SPORTS:
            print(f"unknown sport {s}; choose from {sorted(SPORTS)}", file=sys.stderr)
            return 2

    all_rows: list[dict] = []
    meta: dict = {}
    for s in sports:
        print(f"pulling {s} (HR{' + props' if not args.no_props else ''})...", flush=True)
        rows, m = pull_sport(s, want_props=not args.no_props)
        meta = m
        all_rows.extend(rows)
        hr_n = sum(1 for r in rows if r.get("book") == HR_BOOK)
        miss = sum(1 for r in rows if r.get("market") == "MISSING_ON_HR")
        print(f"  {s}: {hr_n} HR outcomes, {miss} events missing HR")

    payload = {
        "date": day,
        "book": HR_BOOK,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": meta,
        "rows": all_rows,
    }
    js = OUT / f"hr-lines-{day.replace('-', '')}.json"
    tx = OUT / f"hr-lines-{day.replace('-', '')}.txt"
    js.write_text(json.dumps(payload, indent=2))
    tx.write_text(render_txt(all_rows, day, meta))
    print(f"wrote {js}")
    print(f"wrote {tx}")
    print("Hard Rock cash cards must cite these numbers (or a live HR screenshot).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
