#!/usr/bin/env python3
"""HARD GATE — must pass before any place card / weed / exhaustive.

Usage:
  python3 /cursor/stores/self/betting/run_gate.py
  python3 /cursor/stores/self/betting/run_gate.py --date 20261031

Exit 0 only if GATE_TODAY.json written with status=PASS.
Exit 2 if FAIL. No picks may be published without PASS.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

# Prefer durable agent store; also mirror into repo betting/out for PR/cloud visibility.
STORE_CANDIDATES = [
    Path("/cursor/stores/self/betting"),
    Path(__file__).resolve().parent / "out",
]
ET = ZoneInfo("America/New_York")
UA = {"User-Agent": "Mozilla/5.0 (gate/1.0)"}


def resolve_stores() -> list[Path]:
    stores: list[Path] = []
    for p in STORE_CANDIDATES:
        try:
            p.mkdir(parents=True, exist_ok=True)
            stores.append(p)
        except Exception:
            continue
    if not stores:
        raise RuntimeError("No writable gate store path")
    return stores

# Full counting cats — silent omit = FAIL
NBA_CATS = [
    "minutes",
    "points",
    "totalRebounds",
    "assists",
    "steals",
    "blocks",
    "turnovers",
    "threePointFieldGoalsMade-threePointFieldGoalsAttempted",
]
NHL_CATS = ["shots"]


def get(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def today_yyyymmdd() -> str:
    return datetime.now(ET).strftime("%Y%m%d")


def scoreboard(sport_path: str, date: str, extra: str = ""):
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard?dates={date}{extra}"
    return get(url)


def search_player(name: str, league_hint: str | None = None) -> dict | None:
    q = urllib.parse.quote(name)
    url = f"https://site.web.api.espn.com/apis/common/v3/search?region=us&lang=en&query={q}&limit=5&type=player"
    data = get(url)
    items = data.get("items") or []
    if not items:
        return None
    if league_hint:
        for it in items:
            if (it.get("league") or "").lower() == league_hint.lower() or league_hint.lower() in (
                it.get("defaultLeagueSlug") or ""
            ):
                return it
    return items[0]


def nba_gamelog(aid: str) -> dict:
    d = get(f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{aid}/gamelog")
    names = d.get("names") or []
    missing = [c for c in NBA_CATS if c not in names]
    idx = {c: names.index(c) for c in NBA_CATS if c in names}
    rows = []
    for st in d.get("seasonTypes", []):
        label = st.get("displayName") or ""
        if "pre" in label.lower():
            continue
        for cat in st.get("categories", []):
            for ev in cat.get("events", []):
                vals = ev.get("stats") or []
                row = {"eventId": str(ev.get("eventId"))}
                for c, i in idx.items():
                    row[c] = vals[i] if i < len(vals) else "NOT_FETCHED"
                rows.append(row)
    return {"names": names, "missing_cats": missing, "rows": rows[:12], "n": len(rows)}


def nhl_gamelog(aid: str) -> dict:
    d = get(f"https://site.web.api.espn.com/apis/common/v3/sports/hockey/nhl/athletes/{aid}/gamelog")
    names = [n.lower() for n in (d.get("names") or [])]
    labels = [(n or "").lower() for n in (d.get("displayNames") or [])]
    idx = None
    if "shots" in names:
        idx = names.index("shots")
    else:
        for i, lab in enumerate(labels):
            if "shot" in lab:
                idx = i
                break
    rows = []
    for st in d.get("seasonTypes", []):
        if "pre" in (st.get("displayName") or "").lower():
            continue
        for cat in st.get("categories", []):
            for ev in cat.get("events", []):
                vals = ev.get("stats") or []
                if idx is not None and idx < len(vals):
                    try:
                        rows.append({"eventId": str(ev.get("eventId")), "shots": float(vals[idx])})
                    except Exception:
                        rows.append({"eventId": str(ev.get("eventId")), "shots": "NOT_FETCHED"})
    return {
        "names": names,
        "missing_cats": [] if idx is not None else ["shots"],
        "rows": rows[:15],
        "n": len(rows),
    }


def ncaam_gamelog(aid: str) -> dict:
    """Current RS only (season=2027 => 2026-27). Empty early-season logs are OK."""
    d = get(
        f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/mens-college-basketball/athletes/{aid}/gamelog?season=2027"
    )
    names = d.get("names") or []
    if not names:
        return {"names": [], "missing_cats": [], "rows": [], "n": 0, "skip": "empty_2026_27"}
    missing = [c for c in NBA_CATS if c not in names]
    idx = {c: names.index(c) for c in NBA_CATS if c in names}
    rows = []
    for st in d.get("seasonTypes", []):
        label = st.get("displayName") or ""
        if "pre" in label.lower():
            continue
        for cat in st.get("categories", []):
            for ev in cat.get("events", []):
                vals = ev.get("stats") or []
                row = {"eventId": str(ev.get("eventId"))}
                for c, i in idx.items():
                    row[c] = vals[i] if i < len(vals) else "NOT_FETCHED"
                rows.append(row)
    return {"names": names, "missing_cats": missing, "rows": rows[:12], "n": len(rows)}


def parse_games(sb: dict, sport: str) -> list[dict]:
    out = []
    for e in sb.get("events") or []:
        comp = e["competitions"][0]
        away = next(t for t in comp["competitors"] if t["homeAway"] == "away")
        home = next(t for t in comp["competitors"] if t["homeAway"] == "home")
        odds = (comp.get("odds") or [{}])[0]
        out.append(
            {
                "sport": sport,
                "id": e["id"],
                "name": e.get("shortName") or e.get("name"),
                "status": comp["status"]["type"].get("description"),
                "away": away["team"]["abbreviation"],
                "home": home["team"]["abbreviation"],
                "away_id": away["team"]["id"],
                "home_id": home["team"]["id"],
                "odds": odds.get("details"),
                "ou": odds.get("overUnder"),
            }
        )
    return out


def roster_names(sport: str, team_id: str) -> list[tuple[str, str]]:
    if sport == "nba":
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"
    elif sport == "ncaam":
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{team_id}/roster"
    else:
        url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/teams/{team_id}/roster"
    d = get(url)
    people = []
    athletes = d.get("athletes") or []
    # NBA: flat list; NHL: grouped
    if athletes and isinstance(athletes[0], dict) and "items" in athletes[0]:
        for g in athletes:
            for a in g.get("items") or []:
                people.append((a["displayName"], str(a["id"])))
    else:
        for a in athletes:
            people.append((a["displayName"], str(a["id"])))
    return people


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=today_yyyymmdd(), help="YYYYMMDD in ET slate terms")
    ap.add_argument("--max-nba-players", type=int, default=200, help="cap full sheets per run")
    ap.add_argument(
        "--max-nhl-players",
        type=int,
        default=400,
        help="cap NHL sheets; must cover full slate teams (was 120 → truncated late games)",
    )
    ap.add_argument("--max-ncaam-players", type=int, default=180, help="cap NCAAM featured sheets")
    args = ap.parse_args()
    date = args.date
    started = datetime.now(timezone.utc).isoformat()

    failures: list[str] = []
    sports_present: dict[str, list] = {}

    # 1) slate discovery
    try:
        nba_sb = scoreboard("basketball/nba", date)
        sports_present["NBA"] = parse_games(nba_sb, "nba")
    except Exception as e:
        failures.append(f"NBA scoreboard fetch failed: {e}")
        sports_present["NBA"] = []

    try:
        nhl_sb = scoreboard("hockey/nhl", date)
        sports_present["NHL"] = parse_games(nhl_sb, "nhl")
    except Exception as e:
        failures.append(f"NHL scoreboard fetch failed: {e}")
        sports_present["NHL"] = []

    try:
        ncaaf_sb = scoreboard("football/college-football", date, "&limit=100")
        sports_present["NCAAF"] = parse_games(ncaaf_sb, "ncaaf")
    except Exception as e:
        failures.append(f"NCAAF scoreboard fetch failed: {e}")
        sports_present["NCAAF"] = []

    try:
        nfl_sb = scoreboard("football/nfl", date)
        sports_present["NFL"] = parse_games(nfl_sb, "nfl")
    except Exception as e:
        failures.append(f"NFL scoreboard fetch failed: {e}")
        sports_present["NFL"] = []

    try:
        wnba_sb = scoreboard("basketball/wnba", date)
        sports_present["WNBA"] = parse_games(wnba_sb, "wnba")
    except Exception as e:
        failures.append(f"WNBA scoreboard fetch failed: {e}")
        sports_present["WNBA"] = []

    ncaam_sb: dict = {}
    try:
        ncaam_sb = scoreboard(
            "basketball/mens-college-basketball", date, "&groups=50&limit=300"
        )
        sports_present["NCAAM"] = parse_games(ncaam_sb, "ncaam")
    except Exception as e:
        failures.append(f"NCAAM scoreboard fetch failed: {e}")
        sports_present["NCAAM"] = []
        ncaam_sb = {}

    active = {k: v for k, v in sports_present.items() if v}
    if not active and not failures:
        failures.append("No sports found for date — confirm date or refetch")

    # 2) full-stat sheets for NBA/NHL participants (gate core)
    sheets: dict[str, dict] = {}
    nba_ids: list[tuple[str, str, str]] = []  # name, id, team
    nhl_ids: list[tuple[str, str, str]] = []
    ncaam_ids: list[tuple[str, str, str]] = []

    for g in sports_present.get("NBA") or []:
        for tid, abbr in ((g["away_id"], g["away"]), (g["home_id"], g["home"])):
            try:
                for name, aid in roster_names("nba", tid):
                    nba_ids.append((name, aid, abbr))
            except Exception as e:
                failures.append(f"NBA roster {abbr}: {e}")

    for g in sports_present.get("NHL") or []:
        for tid, abbr in ((g["away_id"], g["away"]), (g["home_id"], g["home"])):
            try:
                for name, aid in roster_names("nhl", tid):
                    nhl_ids.append((name, aid, abbr))
            except Exception as e:
                failures.append(f"NHL roster {abbr}: {e}")

    # NCAAM: featured only (ranked or |spread|<=12) — early season / huge slate
    def _spread_mag(details: str | None) -> float | None:
        if not details:
            return None
        parts = str(details).replace("−", "-").split()
        for p in reversed(parts):
            try:
                return abs(float(p))
            except Exception:
                continue
        return None

    ncaam_featured_teams: set[str] = set()
    for g in sports_present.get("NCAAM") or []:
        # ranks live on scoreboard parse? re-enrich from stored odds only
        mag = _spread_mag(g.get("odds"))
        # always include if we cannot parse spread and name suggests VS ranked later;
        # featured filter applied after enrichment below
        if mag is not None and mag <= 12:
            ncaam_featured_teams.add(g["away_id"])
            ncaam_featured_teams.add(g["home_id"])

    # Enrich featured with ranked teams from raw scoreboard
    try:
        for e in ncaam_sb.get("events") or []:
            comp = e["competitions"][0]
            away = next(t for t in comp["competitors"] if t["homeAway"] == "away")
            home = next(t for t in comp["competitors"] if t["homeAway"] == "home")
            ar = (away.get("curatedRank") or {}).get("current") or 99
            hr = (home.get("curatedRank") or {}).get("current") or 99
            if ar <= 25 or hr <= 25:
                ncaam_featured_teams.add(away["team"]["id"])
                ncaam_featured_teams.add(home["team"]["id"])
            odds = (comp.get("odds") or [{}])[0]
            mag = _spread_mag(odds.get("details"))
            if mag is not None and mag <= 12:
                ncaam_featured_teams.add(away["team"]["id"])
                ncaam_featured_teams.add(home["team"]["id"])
    except Exception as e:
        failures.append(f"NCAAM featured enrich failed: {e}")

    for tid in sorted(ncaam_featured_teams):
        try:
            for name, aid in roster_names("ncaam", tid):
                # team abbr from first matching game
                abbr = next(
                    (
                        g["away"] if g["away_id"] == tid else g["home"]
                        for g in (sports_present.get("NCAAM") or [])
                        if tid in (g["away_id"], g["home_id"])
                    ),
                    tid,
                )
                ncaam_ids.append((name, aid, abbr))
        except Exception as e:
            failures.append(f"NCAAM roster {tid}: {e}")

    # de-dupe preserve order
    def dedupe(seq):
        seen = set()
        out = []
        for x in seq:
            if x[1] in seen:
                continue
            seen.add(x[1])
            out.append(x)
        return out

    nba_ids = dedupe(nba_ids)[: args.max_nba_players]
    nhl_ids = dedupe(nhl_ids)
    ncaam_ids = dedupe(ncaam_ids)[: args.max_ncaam_players]

    # Round-robin NHL by team so late slate games are not truncated by the cap
    # (2026-11-03: default 120 only covered UTA/TOR/WPG/MTL/DET — missed EDM/MIN/etc.)
    def interleave_by_team(seq: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
        buckets: dict[str, list[tuple[str, str, str]]] = {}
        order: list[str] = []
        for item in seq:
            team = item[2]
            if team not in buckets:
                buckets[team] = []
                order.append(team)
            buckets[team].append(item)
        out: list[tuple[str, str, str]] = []
        i = 0
        while True:
            progressed = False
            for team in order:
                if i < len(buckets[team]):
                    out.append(buckets[team][i])
                    progressed = True
            if not progressed:
                break
            i += 1
        return out

    nhl_ids = interleave_by_team(nhl_ids)[: args.max_nhl_players]

    # Prefer known high-usage names first if present — still fetch cap
    # (full roster gate is team coverage; player sheets prove category fetch)

    def fetch_nba(item):
        name, aid, team = item
        try:
            gl = nba_gamelog(aid)
            # No RS log yet / empty schema = deep bench skip, not slate FAIL
            if not gl.get("names"):
                return name, {
                    "sport": "nba",
                    "athlete_id": aid,
                    "team": team,
                    "source": f"espn:site.web.api/nba/athletes/{aid}/gamelog",
                    "missing_cats": [],
                    "n_rs": 0,
                    "rows": [],
                    "ok": True,
                    "skip": "empty_gamelog_schema",
                }
            ok = not gl["missing_cats"]
            return name, {
                "sport": "nba",
                "athlete_id": aid,
                "team": team,
                "source": f"espn:site.web.api/nba/athletes/{aid}/gamelog",
                "missing_cats": gl["missing_cats"],
                "n_rs": gl["n"],
                "rows": gl["rows"],
                "ok": ok,
            }
        except Exception as e:
            err = str(e)
            # 404 on obscure roster entries = skip
            if "404" in err:
                return name, {
                    "sport": "nba",
                    "athlete_id": aid,
                    "team": team,
                    "ok": True,
                    "skip": "http_404",
                    "error": err,
                    "missing_cats": [],
                    "n_rs": 0,
                    "rows": [],
                }
            return name, {
                "sport": "nba",
                "athlete_id": aid,
                "team": team,
                "ok": False,
                "error": err,
                "missing_cats": NBA_CATS[:],
            }

    def fetch_nhl(item):
        name, aid, team = item
        try:
            gl = nhl_gamelog(aid)
            if not gl.get("names") and gl.get("n", 0) == 0:
                return name, {
                    "sport": "nhl",
                    "athlete_id": aid,
                    "team": team,
                    "source": f"espn:site.web.api/nhl/athletes/{aid}/gamelog",
                    "missing_cats": [],
                    "n_rs": 0,
                    "rows": [],
                    "ok": True,
                    "skip": "empty_gamelog",
                }
            ok = not gl["missing_cats"]
            return name, {
                "sport": "nhl",
                "athlete_id": aid,
                "team": team,
                "source": f"espn:site.web.api/nhl/athletes/{aid}/gamelog",
                "missing_cats": gl["missing_cats"],
                "n_rs": gl["n"],
                "rows": gl["rows"],
                "ok": ok,
            }
        except Exception as e:
            err = str(e)
            if "404" in err:
                return name, {
                    "sport": "nhl",
                    "athlete_id": aid,
                    "team": team,
                    "ok": True,
                    "skip": "http_404",
                    "error": err,
                    "missing_cats": [],
                    "n_rs": 0,
                    "rows": [],
                }
            return name, {
                "sport": "nhl",
                "athlete_id": aid,
                "team": team,
                "ok": False,
                "error": err,
                "missing_cats": ["shots"],
            }

    def fetch_ncaam(item):
        name, aid, team = item
        try:
            gl = ncaam_gamelog(aid)
            if not gl.get("names") or gl.get("n", 0) == 0:
                return name, {
                    "sport": "ncaam",
                    "athlete_id": aid,
                    "team": team,
                    "source": f"espn:site.web.api/mbb/athletes/{aid}/gamelog?season=2027",
                    "missing_cats": [],
                    "n_rs": 0,
                    "rows": [],
                    "ok": True,
                    "skip": gl.get("skip") or "empty_2026_27_rs",
                }
            ok = not gl["missing_cats"]
            return name, {
                "sport": "ncaam",
                "athlete_id": aid,
                "team": team,
                "source": f"espn:site.web.api/mbb/athletes/{aid}/gamelog?season=2027",
                "missing_cats": gl["missing_cats"],
                "n_rs": gl["n"],
                "rows": gl["rows"],
                "ok": ok,
            }
        except Exception as e:
            err = str(e)
            if "404" in err:
                return name, {
                    "sport": "ncaam",
                    "athlete_id": aid,
                    "team": team,
                    "ok": True,
                    "skip": "http_404",
                    "error": err,
                    "missing_cats": [],
                    "n_rs": 0,
                    "rows": [],
                }
            return name, {
                "sport": "ncaam",
                "athlete_id": aid,
                "team": team,
                "ok": False,
                "error": err,
                "missing_cats": NBA_CATS[:],
            }

    with ThreadPoolExecutor(20) as ex:
        futs = (
            [ex.submit(fetch_nba, it) for it in nba_ids]
            + [ex.submit(fetch_nhl, it) for it in nhl_ids]
            + [ex.submit(fetch_ncaam, it) for it in ncaam_ids]
        )
        for f in as_completed(futs):
            name, sheet = f.result()
            # avoid NBA/NHL name collisions overwriting — prefix sport if needed
            key = name
            if key in sheets and sheets[key].get("sport") != sheet.get("sport"):
                key = f"{name} [{sheet.get('sport')}]"
            sheets[key] = sheet
            if not sheet.get("ok"):
                failures.append(
                    f"SHEET FAIL {name} ({sheet.get('athlete_id')}): missing={sheet.get('missing_cats')} err={sheet.get('error')}"
                )

    # 3) structural gates
    if sports_present.get("NBA") and not nba_ids:
        failures.append("NBA games present but zero roster ids collected")
    if sports_present.get("NHL") and not nhl_ids:
        failures.append("NHL games present but zero roster ids collected")
    if sports_present.get("NCAAM") and ncaam_featured_teams and not ncaam_ids:
        failures.append("NCAAM featured teams present but zero roster ids collected")

    # Require at least some successful full sheets when that sport is active
    if sports_present.get("NBA"):
        ok_nba = sum(1 for s in sheets.values() if s.get("sport") == "nba" and s.get("ok"))
        if ok_nba < min(10, max(1, len(nba_ids) // 2)):
            failures.append(f"NBA full sheets insufficient: ok={ok_nba} fetched={len(nba_ids)}")
        # category proof: every ok sheet must include blocks key in a row when n>0
        for name, s in sheets.items():
            if s.get("sport") != "nba" or not s.get("ok") or s.get("n_rs", 0) == 0:
                continue
            row0 = (s.get("rows") or [{}])[0]
            for cat in ("points", "totalRebounds", "assists", "steals", "blocks"):
                if cat not in row0 or row0.get(cat) == "NOT_FETCHED":
                    failures.append(f"NBA {name} row missing {cat}")

    status = "PASS" if not failures else "FAIL"
    stores = resolve_stores()
    primary = stores[0]
    sidecar_name = f"GATE_SHEETS_{date}.json"
    sidecar_primary = primary / sidecar_name
    sidecar_primary.write_text(json.dumps(sheets, indent=2))

    gate = {
        "status": status,
        "date": date,
        "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "tz": "America/New_York",
        "sports_active": {k: len(v) for k, v in sports_present.items()},
        "games": sports_present,
        "sheets_ok": sum(1 for s in sheets.values() if s.get("ok")),
        "sheets_total": len(sheets),
        "failures": failures,
        "sheets_path": str(sidecar_primary),
        "sheets_index": {
            name: {
                "athlete_id": s.get("athlete_id"),
                "team": s.get("team"),
                "sport": s.get("sport"),
                "ok": s.get("ok"),
                "n_rs": s.get("n_rs"),
                "missing_cats": s.get("missing_cats"),
                "source": s.get("source"),
            }
            for name, s in sheets.items()
        },
        "rules": [
            "No place card / weed / exhaustive without status=PASS",
            "Full NBA cats required: MIN/PTS/REB/AST/STL/BLK/TO/3P",
            "NCAAM gated: slate discovery + featured roster sheets (rank<=25 or |spread|<=12)",
            "NCAAM early-season: empty 2026-27 logs OK; no prior-year as SAFE counting",
            "BANGERS board required in delivery after gate",
            "Weed cannot contradict from-scratch KEEP/PRIMARY",
            "Show athlete_id + source on every cited player",
        ],
        "ncaam_featured_team_ids": sorted(ncaam_featured_teams),
        "ncaam_sheets": sum(1 for s in sheets.values() if s.get("sport") == "ncaam"),
    }

    status_txt = (
        f"{status} date={date} sheets_ok={gate['sheets_ok']}/{gate['sheets_total']} "
        f"failures={len(failures)} utc={gate['finished_utc']}\n"
        + ("\n".join(failures[:30]) if failures else "no failures\n")
    )
    payload = json.dumps(gate, indent=2)
    written = []
    for store in stores:
        (store / "GATE_TODAY.json").write_text(payload)
        (store / "GATE_STATUS.txt").write_text(status_txt)
        # mirror sheets sidecar into each store
        if store != primary:
            (store / sidecar_name).write_text(json.dumps(sheets, indent=2))
        written.append(str(store / "GATE_TODAY.json"))

    print(f"GATE {status} → {', '.join(written)}")
    print(f"sheets {gate['sheets_ok']}/{gate['sheets_total']} active={gate['sports_active']}")
    if failures:
        print("FAILURES:")
        for f in failures[:40]:
            print(" -", f)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
