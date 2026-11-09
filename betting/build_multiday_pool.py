#!/usr/bin/env python3
"""Build a 2–3 day 6/7+ shave pool (NBA/NHL + fold in NFL day-1).

Usage:
  python3 betting/build_multiday_pool.py
  python3 betting/build_multiday_pool.py --dates 20261109,20261110,20261111

Writes:
  betting/multiday-pool-YYYYMMDD-YYYYMMDD.{txt,json}
  betting/multiday-punch-YYYYMMDD-YYYYMMDD.txt
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path(__file__).resolve().parent
STORE = Path("/cursor/stores/self/betting")
ET = ZoneInfo("America/New_York")
UA = {"User-Agent": "Mozilla/5.0 (multiday-pool/1.0)"}

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

# Soft floors — never promote into punch spine
SOFT = {
    "PTS": 4.5,   # allow down to 4.5; below = soft-ish for spine
    "REB": 1.5,
    "AST": 1.5,
    "STL": 1.5,
    "BLK": 0.5,
    "3PT": 0.5,
    "SOG": 1.5,
}

# Practical book-ladder max drops from a research "posted" (~L7 median - 0.5)
BOOK_DROP = {"PTS": 10.0, "REB": 4.0, "AST": 3.0, "3PT": 1.0, "STL": 1.0, "BLK": 1.0, "SOG": 1.5}


def get(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def scoreboard(sport_path: str, date: str):
    return get(f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard?dates={date}")


def parse_games(sb: dict, sport: str) -> list[dict]:
    out = []
    for e in sb.get("events") or []:
        c = (e.get("competitions") or [{}])[0]
        away = home = None
        away_id = home_id = None
        for t in c.get("competitors") or []:
            abbr = t.get("team", {}).get("abbreviation")
            tid = str(t.get("team", {}).get("id") or t.get("id") or "")
            if t.get("homeAway") == "away":
                away, away_id = abbr, tid
            else:
                home, home_id = abbr, tid
        odds = ou = None
        for o in c.get("odds") or []:
            odds = o.get("details")
            ou = o.get("overUnder")
            break
        out.append(
            {
                "sport": sport,
                "id": e.get("id"),
                "name": e.get("shortName") or e.get("name"),
                "status": (e.get("status") or {}).get("type", {}).get("description"),
                "when": (e.get("status") or {}).get("type", {}).get("shortDetail"),
                "away": away,
                "home": home,
                "away_id": away_id,
                "home_id": home_id,
                "odds": odds,
                "ou": ou,
            }
        )
    return out


def roster_names(league: str, team_id: str) -> list[tuple[str, str, str]]:
    """Return (name, id, position_abbr)."""
    path = "basketball/nba" if league == "nba" else "hockey/nhl"
    d = get(f"https://site.api.espn.com/apis/site/v2/sports/{path}/teams/{team_id}/roster")
    people = []
    athletes = d.get("athletes") or []
    if athletes and isinstance(athletes[0], dict) and "items" in athletes[0]:
        for g in athletes:
            group_pos = ((g.get("position") or {}).get("abbreviation") if isinstance(g.get("position"), dict) else None) or ""
            for a in g.get("items") or []:
                if a.get("displayName") and a.get("id"):
                    pos = ((a.get("position") or {}).get("abbreviation") if isinstance(a.get("position"), dict) else None) or group_pos
                    people.append((a["displayName"], str(a["id"]), pos or ""))
    else:
        for a in athletes:
            if a.get("displayName") and a.get("id"):
                pos = ((a.get("position") or {}).get("abbreviation") if isinstance(a.get("position"), dict) else None) or ""
                people.append((a["displayName"], str(a["id"]), pos or ""))
    return people


def _rows_from_gamelog(d: dict, cats: list[str]) -> tuple[list[dict], list[str]]:
    names = d.get("names") or []
    missing = [c for c in cats if c not in names]
    idx = {c: names.index(c) for c in cats if c in names}
    rows = []
    for st in d.get("seasonTypes", []):
        label = (st.get("displayName") or "").lower()
        if "pre" in label:
            continue
        for cat in st.get("categories", []):
            for ev in cat.get("events", []):
                stats = ev.get("stats") or []
                row = {"eventId": ev.get("eventId"), "gameDate": ev.get("gameDate")}
                for c, i in idx.items():
                    if i < len(stats):
                        row[c] = stats[i]
                rows.append(row)
    # most recent first
    rows.sort(key=lambda r: r.get("gameDate") or "", reverse=True)
    return rows, missing


def nba_sheet(aid: str) -> dict:
    d = get(f"https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{aid}/gamelog")
    rows, missing = _rows_from_gamelog(d, NBA_CATS)
    return {"sport": "nba", "athlete_id": aid, "missing_cats": missing, "n_rs": len(rows), "rows": rows, "ok": True}


def nhl_sheet(aid: str) -> dict:
    d = get(f"https://site.web.api.espn.com/apis/common/v3/sports/hockey/nhl/athletes/{aid}/gamelog")
    rows, missing = _rows_from_gamelog(d, NHL_CATS)
    return {"sport": "nhl", "athlete_id": aid, "missing_cats": missing, "n_rs": len(rows), "rows": rows, "ok": True}


def fnum(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).split(":")[0]) if isinstance(v, str) and ":" in v else float(v)
    except Exception:
        return None


def threes(row: dict) -> float | None:
    raw = row.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted")
    if raw is None:
        return None
    try:
        return float(str(raw).split("-")[0])
    except Exception:
        return None


def vals_for(rec: dict, stat: str, n: int = 7) -> list[float]:
    rows = list(rec.get("rows") or [])[:n]
    out = []
    for r in rows:
        if stat == "PTS":
            v = fnum(r.get("points"))
        elif stat == "REB":
            v = fnum(r.get("totalRebounds"))
        elif stat == "AST":
            v = fnum(r.get("assists"))
        elif stat == "STL":
            v = fnum(r.get("steals"))
        elif stat == "BLK":
            v = fnum(r.get("blocks"))
        elif stat == "3PT":
            v = threes(r)
        elif stat == "SOG":
            v = fnum(r.get("shots"))
        elif stat == "MIN":
            v = fnum(r.get("minutes"))
        else:
            v = None
        if v is not None:
            out.append(v)
    return out


def is_soft(stat: str, line: float) -> bool:
    floor = SOFT.get(stat)
    if floor is None:
        return line < 0
    return line <= floor


def walk_67(vals: list[float], stat: str, start: float | None = None) -> dict | None:
    """Walk down from a high research line; first 6/7+ above soft = clear_at."""
    n = len(vals)
    if n < 5:
        return None
    s = sorted(vals)
    med = s[len(s) // 2]
    research = round((med - 0.5) * 2) / 2
    if research < 0.5:
        research = 0.5
    # Start high enough to find the *highest* clearing line (up to book-drop above research)
    hi = round((max(vals) - 0.5) * 2) / 2
    cap = round((research + BOOK_DROP.get(stat, 3.0)) * 2) / 2
    line = start if start is not None else min(hi, max(research, cap))
    first_67 = None
    deepest_67 = None
    first_nn = None
    deepest_nn = None
    floor_stop = SOFT.get(stat, 0) + 0.5  # first non-soft

    while line >= floor_stop - 1e-9:
        if is_soft(stat, line):
            break
        h = sum(1 for v in vals if v > line)
        ok67 = (n >= 7 and h >= 6) or (n == 6 and h >= 6) or (n == 5 and h >= 5)
        if ok67:
            if first_67 is None:
                first_67 = (line, h)
            deepest_67 = (line, h)
        if h == n and n >= 5:
            if first_nn is None:
                first_nn = (line, h)
            deepest_nn = (line, h)
        line = round((line - 0.5) * 2) / 2

    if first_67 is None:
        return None

    # Kind at the clear_at line
    h0, n0 = first_67[1], n
    if h0 == n0 and n0 >= 7:
        kind = "7/7"
    elif h0 == n0 and n0 == 6:
        kind = "6/6"
    elif h0 == n0 and n0 == 5:
        kind = "5/5"
    else:
        kind = "6/7"

    return {
        "research_posted": research,
        "clear_at": first_67[0],
        "clear_hits": first_67[1],
        "deep_67": deepest_67[0],
        "nn_at": first_nn[0] if first_nn else None,
        "nn_deep": deepest_nn[0] if deepest_nn else None,
        "kind": kind,
        "n": n,
        "vals": vals,
        "band": f"O{deepest_67[0]}–O{first_67[0]}",
        "drop": round(research - first_67[0], 1),
    }


def fetch_injuries_for_games(games: list[dict]) -> dict[str, dict]:
    """Map normalized player name -> {status, team, fantasy}."""
    out: dict[str, dict] = {}
    for g in games:
        eid = g.get("id")
        if not eid:
            continue
        sport = g.get("sport")
        if sport == "nba":
            url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={eid}"
        elif sport == "nhl":
            url = f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event={eid}"
        else:
            continue
        try:
            s = get(url)
        except Exception:
            continue
        for tb in s.get("injuries") or []:
            team = (tb.get("team") or {}).get("abbreviation")
            for inj in tb.get("injuries") or []:
                name = (inj.get("athlete") or {}).get("displayName")
                if not name:
                    continue
                status = (inj.get("status") or "").lower()
                fant = ((inj.get("details") or {}).get("fantasyStatus") or {}).get("abbreviation") or ""
                key = name.lower()
                out[key] = {
                    "status": inj.get("status"),
                    "fantasy": fant,
                    "team": team,
                    "out": status in ("out",) or fant in ("OUT", "OFS") or "out" in status,
                    "gtd": fant in ("GTD", "DTD", "Q")
                    or "day-to-day" in status
                    or "doubtful" in status
                    or "questionable" in status,
                }
    return out


def load_cached_sheets(date: str) -> dict | None:
    for p in (STORE / f"GATE_SHEETS_{date}.json", OUT / "out" / f"GATE_SHEETS_{date}.json"):
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                continue
    return None


def fetch_day(date: str, max_nba: int = 220, max_nhl: int = 120) -> dict:
    """Return {games, sheets_by_key} for one date. Prefer cache."""
    games = {"NBA": [], "NHL": [], "NFL": []}
    try:
        games["NBA"] = parse_games(scoreboard("basketball/nba", date), "nba")
    except Exception:
        pass
    try:
        games["NHL"] = parse_games(scoreboard("hockey/nhl", date), "nhl")
    except Exception:
        pass
    try:
        games["NFL"] = parse_games(scoreboard("football/nfl", date), "nfl")
    except Exception:
        pass

    cached = load_cached_sheets(date)
    sheets: dict[str, dict] = {}
    if cached:
        # attach team from cache; filter later by minutes
        for name, rec in cached.items():
            if isinstance(rec, dict) and rec.get("ok"):
                sheets[name] = rec
        return {"date": date, "games": games, "sheets": sheets, "source": "cache"}

    # Build roster list for teams on slate
    jobs = []
    for g in games["NBA"]:
        for tid, abbr in ((g["away_id"], g["away"]), (g["home_id"], g["home"])):
            if not tid:
                continue
            try:
                for name, aid, pos in roster_names("nba", tid):
                    jobs.append(("nba", name, aid, abbr, g["name"], pos))
            except Exception:
                continue
    for g in games["NHL"]:
        for tid, abbr in ((g["away_id"], g["away"]), (g["home_id"], g["home"])):
            if not tid:
                continue
            try:
                for name, aid, pos in roster_names("nhl", tid):
                    if pos == "G":
                        continue  # goalie shots-faced ≠ skater SOG props
                    jobs.append(("nhl", name, aid, abbr, g["name"], pos))
            except Exception:
                continue

    # dedupe
    seen = set()
    uniq = []
    for j in jobs:
        if j[2] in seen:
            continue
        seen.add(j[2])
        uniq.append(j)
    nba = [j for j in uniq if j[0] == "nba"][:max_nba]
    nhl = [j for j in uniq if j[0] == "nhl"][:max_nhl]
    work = nba + nhl

    def one(j):
        sport, name, aid, team, game, pos = j
        try:
            rec = nba_sheet(aid) if sport == "nba" else nhl_sheet(aid)
            rec["team"] = team
            rec["game"] = game
            rec["name"] = name
            rec["pos"] = pos
            return name, rec
        except Exception as e:
            return name, {"ok": False, "error": str(e), "athlete_id": aid, "team": team, "game": game, "pos": pos}

    with ThreadPoolExecutor(max_workers=24) as ex:
        futs = [ex.submit(one, j) for j in work]
        for fut in as_completed(futs):
            name, rec = fut.result()
            sheets[name] = rec

    # persist cache for reuse
    STORE.mkdir(parents=True, exist_ok=True)
    (STORE / f"GATE_SHEETS_{date}.json").write_text(json.dumps(sheets))
    (OUT / "out").mkdir(parents=True, exist_ok=True)
    (OUT / "out" / f"GATE_SHEETS_{date}.json").write_text(json.dumps(sheets))
    return {"date": date, "games": games, "sheets": sheets, "source": "live"}


def grade_day(day: dict, injuries: dict[str, dict] | None = None) -> list[dict]:
    """Produce 6/7+ clears for one day. OUT players dropped; GTD tagged."""
    date = day["date"]
    injuries = injuries or {}
    # map team -> game name
    team_game = {}
    all_games = []
    for sport in ("NBA", "NHL"):
        for g in day["games"].get(sport) or []:
            team_game[(sport.lower(), g["away"])] = g
            team_game[(sport.lower(), g["home"])] = g
            all_games.append(g)

    clears = []
    for name, rec in day["sheets"].items():
        if not isinstance(rec, dict) or not rec.get("ok"):
            continue
        inj = injuries.get(name.lower())
        if inj and inj.get("out"):
            continue
        sport = rec.get("sport")
        team = rec.get("team")
        mins = vals_for(rec, "MIN", 7) if sport == "nba" else []
        avg_min = sum(mins) / len(mins) if mins else 0
        if sport == "nba" and avg_min < 20:
            continue
        if sport == "nba" and len(vals_for(rec, "PTS", 7)) < 5:
            continue
        if sport == "nhl" and (rec.get("pos") == "G" or len(vals_for(rec, "SOG", 10)) < 5):
            continue
        # Cached sheets may include goalies — drop absurd SOG (shots-faced)
        if sport == "nhl":
            sog_probe = vals_for(rec, "SOG", 7)
            if sog_probe and (sum(sog_probe) / len(sog_probe)) >= 10:
                continue

        gmeta = team_game.get((sport, team)) or {}
        game = rec.get("game") or gmeta.get("name") or "?"
        stats = ["PTS", "REB", "AST", "3PT"] if sport == "nba" else ["SOG"]

        for stat in stats:
            vals = vals_for(rec, stat, 7 if sport == "nba" else 10)
            if sport == "nhl":
                vals7 = vals[:7]
                vals = vals7 if len(vals7) >= 5 else vals
            w = walk_67(vals, stat)
            if not w:
                continue
            if is_soft(stat, w["clear_at"]):
                continue
            # Require a real punchable number (not micro)
            if stat in ("REB", "AST") and w["clear_at"] < 2.5:
                continue
            if stat == "PTS" and w["clear_at"] < 5.5:
                continue
            if stat == "3PT" and w["clear_at"] < 1.0:
                continue
            if stat == "SOG" and (w["clear_at"] < 2.0 or w["clear_at"] > 5.5):
                continue

            score = (w["clear_hits"] / w["n"]) * 100
            score += min(avg_min, 36) * 0.15
            if w["kind"] in ("7/7", "6/6", "5/5", "10/10"):
                score += 8
            score -= max(0, w["drop"]) * 0.4
            gtd = bool(inj and inj.get("gtd"))
            if gtd:
                score -= 25  # demote game-time decisions
            clears.append(
                {
                    "date": date,
                    "sport": sport.upper(),
                    "game": game,
                    "when": gmeta.get("when"),
                    "player": name,
                    "id": rec.get("athlete_id"),
                    "team": team,
                    "stat": stat,
                    "avg_min": round(avg_min, 1),
                    "score": round(score, 2),
                    "gtd": gtd,
                    "inj_status": (inj or {}).get("status"),
                    **w,
                }
            )
    clears.sort(key=lambda r: (-r["score"], r["drop"], r["player"]))
    return clears


def load_nfl_67() -> list[dict]:
    p = OUT / "nfl-shave-67-20261109.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text())
    out = []
    for r in d.get("passes") or d.get("passes_ranked") or []:
        f = r.get("first_67") or [None, None]
        deep = r.get("deepest_67") or [None, None]
        kind = r.get("kind") or (f"{f[1]}/{r['n']}" if f and f[1] else "?")
        out.append(
            {
                "date": "20261109",
                "sport": "NFL",
                "game": "BUF @ MIN",
                "when": "11/9 - 8:15 PM EST",
                "player": r["player"],
                "id": r.get("id"),
                "team": r.get("team"),
                "stat": r["stat"],
                "avg_min": None,
                "research_posted": r.get("posted"),
                "clear_at": f[0],
                "clear_hits": f[1],
                "deep_67": deep[0],
                "nn_at": r.get("first_nn"),
                "nn_deep": r.get("deep_nn"),
                "kind": kind,
                "n": r["n"],
                "vals": r.get("vals"),
                "band": f"O{deep[0]}–O{f[0]}" if f and deep else "",
                "drop": r.get("drop_from_posted") or r.get("drop"),
                "score": 100.0,  # already filtered 6/7+
            }
        )
    return out


def fmt_date(yyyymmdd: str) -> str:
    return f"{yyyymmdd[4:6]}/{yyyymmdd[6:8]}"


def render(dates: list[str], by_day: dict[str, list], games: dict) -> tuple[str, str]:
    all_clears = []
    for d in dates:
        all_clears.extend(by_day.get(d) or [])

    lines = []
    lines.append("═" * 68)
    lines.append(f"MULTI-DAY 6/7+ POOL · {fmt_date(dates[0])}–{fmt_date(dates[-1])} · America/New_York")
    lines.append("Idea: spread risk across days · pick the BEST from each slate · more punches, same rigor")
    lines.append("Rule: clear_at = highest line that still hits 6/7 or 7/7 (soft floors banned)")
    lines.append("G2/G3: confirm posted/HR before betting — research_posted is L7-median estimate when book missing")
    lines.append("═" * 68)

    # slate sizes
    lines.append("")
    lines.append("── SLATE ──")
    for d in dates:
        g = games.get(d) or {}
        nba = len(g.get("NBA") or [])
        nhl = len(g.get("NHL") or [])
        nfl = len(g.get("NFL") or [])
        n = len(by_day.get(d) or [])
        lines.append(f"  {fmt_date(d)}  NBA {nba} · NHL {nhl} · NFL {nfl}  →  {n} clears @ 6/7+")

    # best of each day
    lines.append("")
    lines.append("══ BEST OF EACH DAY (top punches) ══")
    for d in dates:
        clears = by_day.get(d) or []
        lines.append(f"\n▶ {fmt_date(d)}")
        if not clears:
            lines.append("  (no clears yet)")
            continue
        # diversify: top by score but max 2 per player
        def rank_key(r):
            return (
                0 if not r.get("gtd") else 1,
                0 if r["kind"] in ("7/7", "5/5", "6/6") else 1,
                -r["score"],
            )

        by_sport: dict[str, list] = {}
        for r in clears:
            by_sport.setdefault(r["sport"], []).append(r)
        for s in by_sport:
            by_sport[s].sort(key=rank_key)
        sport_order = [s for s in ("NFL", "NBA", "NHL") if s in by_sport]
        idxs = {s: 0 for s in sport_order}
        seen_p = {}
        shown = 0
        while shown < 14 and any(idxs[s] < len(by_sport[s]) for s in sport_order):
            progressed = False
            for s in sport_order:
                while idxs[s] < len(by_sport[s]):
                    r = by_sport[s][idxs[s]]
                    idxs[s] += 1
                    if seen_p.get(r["player"], 0) >= 2:
                        continue
                    if r["stat"] in ("REB", "AST") and r["clear_at"] <= 2.5 and (r.get("avg_min") or 30) < 28:
                        continue
                    seen_p[r["player"]] = seen_p.get(r["player"], 0) + 1
                    nn = f" · 7/7@O{r['nn_at']}" if r.get("nn_at") and r["kind"] == "6/7" else ""
                    amin = f" · {r['avg_min']}mpg" if r.get("avg_min") else ""
                    gtd = " · GTD" if r.get("gtd") else ""
                    lines.append(
                        f"  {r['kind']:4}  {r['player']:<22} {r['stat']:<7} clear O{r['clear_at']:<5} "
                        f"band {r['band']:<14} {r['sport']} {r['game']}{amin}{nn}{gtd}"
                    )
                    lines.append(
                        f"        L={r['vals']}  research~O{r['research_posted']}  id={r.get('id')}"
                    )
                    shown += 1
                    progressed = True
                    break
                if shown >= 14:
                    break
            if not progressed:
                break

    # cross-day master punch (top 25 overall, diversify by day)
    lines.append("")
    lines.append("══ CROSS-DAY MASTER PUNCH (diversified) ══")
    lines.append("Grab 2–4 from each day → bigger ticket, risk split across tips")
    per_day_cap = {d: 0 for d in dates}
    master = []
    seen_ps = set()
    for r in sorted(all_clears, key=lambda x: -x["score"]):
        key = (r["player"], r["stat"], r["date"])
        if key in seen_ps:
            continue
        if per_day_cap[r["date"]] >= 8:
            continue
        # prefer perfect / small drop
        seen_ps.add(key)
        per_day_cap[r["date"]] += 1
        master.append(r)
        if len(master) >= 24:
            break

    for i, r in enumerate(master, 1):
        lines.append(
            f"  {i:>2}. [{fmt_date(r['date'])}] {r['kind']:4} {r['player']:<20} {r['stat']:<7} "
            f"O{r['clear_at']}  {r['sport']} {r['game']}"
        )

    # full by day boards
    lines.append("")
    lines.append("══ FULL CLEAR BOARDS BY DAY ══")
    for d in dates:
        clears = by_day.get(d) or []
        lines.append(f"\n── {fmt_date(d)} ({len(clears)} clears) ──")
        for r in clears[:40]:
            lines.append(
                f"  {r['kind']:4} {r['player']:<22} {r['stat']:<5} O{r['clear_at']:<5} "
                f"{r['band']:<14} {r['game']:<12} L={r['vals']}"
            )
        if len(clears) > 40:
            lines.append(f"  … +{len(clears)-40} more in JSON")

    # how to use
    lines.append("")
    lines.append("══ HOW TO USE ══")
    lines.append("1. Build separate slips per day OR one multi-day parlay (books that allow it).")
    lines.append("2. From each day take the top 2–4 that are actually posted on HR.")
    lines.append("3. Prefer kind 7/7 / 5/5 / 6/6; use 6/7 when the shave is small (drop ≤3).")
    lines.append("4. Re-check injuries morning-of; GTD stars can kill a leg.")
    lines.append("5. Soft floors stay banned even if they go 7/7.")

    full = "\n".join(lines) + "\n"

    # short punch card
    punch = []
    punch.append(f"MULTI-DAY PUNCH · {fmt_date(dates[0])}–{fmt_date(dates[-1])}")
    punch.append("Best 8 per day · confirm HR · soft banned\n")
    for d in dates:
        punch.append(f"▶ {fmt_date(d)}")
        clears = by_day.get(d) or []
        def rank_key(r):
            return (
                0 if not r.get("gtd") else 1,
                0 if r["kind"] in ("7/7", "5/5", "6/6") else 1,
                -r["score"],
            )

        # Mix sports so one slate doesn't drown the punch (NFL day-1 especially)
        by_sport: dict[str, list] = {}
        for r in clears:
            by_sport.setdefault(r["sport"], []).append(r)
        for s in by_sport:
            by_sport[s].sort(key=rank_key)

        mixed: list[dict] = []
        # round-robin sports, prefer NFL/NBA/NHL order
        sport_order = [s for s in ("NFL", "NBA", "NHL") if s in by_sport]
        idxs = {s: 0 for s in sport_order}
        seen_p: dict[str, int] = {}
        while len(mixed) < 10 and any(idxs[s] < len(by_sport[s]) for s in sport_order):
            progressed = False
            for s in sport_order:
                while idxs[s] < len(by_sport[s]):
                    r = by_sport[s][idxs[s]]
                    idxs[s] += 1
                    if seen_p.get(r["player"], 0) >= 2:
                        continue
                    # skip micro-adjacent REB/AST 2.5 unless perfect and high mpg
                    if r["stat"] in ("REB", "AST") and r["clear_at"] <= 2.5 and r.get("avg_min", 30) < 28:
                        continue
                    seen_p[r["player"]] = seen_p.get(r["player"], 0) + 1
                    mixed.append(r)
                    progressed = True
                    break
            if not progressed:
                break

        for r in mixed:
            gtd = " GTD" if r.get("gtd") else ""
            punch.append(
                f"  {r['kind']:4} {r['player']} {r['stat']} O{r['clear_at']}  ({r['sport']} {r['game']})  band {r['band']}{gtd}"
            )
        punch.append("")
    short = "\n".join(punch)
    return full, short


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dates",
        default="",
        help="comma YYYYMMDD (default: today + next 2 ET)",
    )
    args = ap.parse_args()
    if args.dates:
        dates = [x.strip() for x in args.dates.split(",") if x.strip()]
    else:
        from datetime import timedelta

        base = datetime.now(ET).date()
        dates = [(base + timedelta(days=i)).strftime("%Y%m%d") for i in range(3)]

    print(f"Building multi-day pool for {dates} …")
    by_day: dict[str, list] = {}
    games_meta: dict[str, dict] = {}
    raw_days = []

    for d in dates:
        print(f"  fetching {d} …")
        day = fetch_day(d)
        raw_days.append(day)
        games_meta[d] = day["games"]
        slate_games = (day["games"].get("NBA") or []) + (day["games"].get("NHL") or [])
        print(f"    injuries for {len(slate_games)} games …")
        injuries = fetch_injuries_for_games(slate_games)
        out_n = sum(1 for v in injuries.values() if v.get("out"))
        gtd_n = sum(1 for v in injuries.values() if v.get("gtd"))
        print(f"    injury map {len(injuries)} (OUT {out_n} · GTD {gtd_n})")
        clears = grade_day(day, injuries)
        # fold NFL into days that have NFL (Mon)
        if day["games"].get("NFL"):
            nfl = [x for x in load_nfl_67() if x["date"] == d]
            have = {(c["player"], c["stat"]) for c in clears if c["sport"] == "NFL"}
            for x in nfl:
                if (x["player"], x["stat"]) not in have:
                    x = dict(x)
                    x["gtd"] = False
                    clears.append(x)
            clears.sort(key=lambda r: -r["score"])
        by_day[d] = clears
        print(f"    sheets={len(day['sheets'])} source={day['source']} clears={len(clears)}")

    full, short = render(dates, by_day, games_meta)
    tag = f"{dates[0]}-{dates[-1]}"
    (OUT / f"multiday-pool-{tag}.txt").write_text(full)
    (OUT / f"multiday-punch-{tag}.txt").write_text(short)
    payload = {
        "dates": dates,
        "generated_at": datetime.now(ET).isoformat(),
        "by_day": by_day,
        "games": games_meta,
        "counts": {d: len(by_day[d]) for d in dates},
    }
    (OUT / f"multiday-pool-{tag}.json").write_text(json.dumps(payload, indent=2))
    print(short)
    print(f"\nWrote betting/multiday-pool-{tag}.txt + punch + json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
