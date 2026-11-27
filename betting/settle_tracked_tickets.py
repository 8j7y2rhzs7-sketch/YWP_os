#!/usr/bin/env python3
"""Grade TRACK-YYYYMMDD-tickets.json from ESPN live/final scores.

Usage:
  python3 betting/settle_tracked_tickets.py
  python3 betting/settle_tracked_tickets.py --date 20261127
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path(__file__).resolve().parent
UA = {"User-Agent": "Mozilla/5.0 YWP-settle-tracked"}
ET = ZoneInfo("America/New_York")


def get(url: str, timeout: int = 25) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def nba_box_player(event_id: str, athlete_id: str) -> dict | None:
    s = get(
        f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}"
    )
    for side in (s.get("boxscore") or {}).get("players") or []:
        for st in side.get("statistics") or []:
            for ath in st.get("athletes") or []:
                a = ath.get("athlete") or {}
                if str(a.get("id")) == str(athlete_id):
                    stats = dict(zip(st.get("keys") or [], ath.get("stats") or []))
                    return {
                        "name": a.get("displayName"),
                        "stats": stats,
                        "minutes": stats.get("minutes") or stats.get("MIN"),
                    }
    return None


def nhl_box_sog(event_id: str, athlete_id: str) -> float | None:
    s = get(
        f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event={event_id}"
    )
    for side in (s.get("boxscore") or {}).get("players") or []:
        for st in side.get("statistics") or []:
            keys = st.get("keys") or []
            for ath in st.get("athletes") or []:
                a = ath.get("athlete") or {}
                if str(a.get("id")) == str(athlete_id):
                    stats = dict(zip(keys, ath.get("stats") or []))
                    for k in ("sog", "shots", "shotsOnGoal", "SOG"):
                        if k in stats and stats[k] not in (None, ""):
                            try:
                                return float(stats[k])
                            except Exception:
                                pass
                    # sometimes labels
                    labels = st.get("labels") or []
                    raw = dict(zip(labels, ath.get("stats") or []))
                    for k in ("SOG", "S", "Shots"):
                        if k in raw:
                            try:
                                return float(raw[k])
                            except Exception:
                                pass
    return None


def ncaam_final(event_id: str) -> dict | None:
    s = get(
        f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={event_id}"
    )
    comps = (s.get("header") or {}).get("competitions") or []
    if not comps:
        return None
    c = comps[0]
    status = (c.get("status") or {}).get("type") or {}
    teams = {}
    for comp in c.get("competitors") or []:
        abbr = (comp.get("team") or {}).get("abbreviation")
        teams[abbr] = {
            "score": int(float(comp.get("score") or 0)),
            "homeAway": comp.get("homeAway"),
            "winner": comp.get("winner"),
        }
    return {
        "completed": bool(status.get("completed")),
        "detail": status.get("detail"),
        "teams": teams,
    }


def nfl_scoreboard(date: str) -> list[dict]:
    sb = get(
        f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={date}"
    )
    return sb.get("events") or []


def find_nfl(events: list[dict], needle: str) -> dict | None:
    for e in events:
        name = (e.get("shortName") or e.get("name") or "").upper()
        if all(p in name for p in needle.upper().replace("@", " ").split()):
            return e
    # DEN PIT
    for e in events:
        name = (e.get("shortName") or "").upper()
        if "DEN" in name and "PIT" in name:
            return e
    return None


def grade_spread(fav_abbr: str, line: float, teams: dict) -> tuple[str, str]:
    """line is fav spread e.g. -3.5 meaning fav -3.5."""
    # find fav and dog scores
    if fav_abbr not in teams:
        # try aliases
        for k in teams:
            if fav_abbr.upper() in k.upper():
                fav_abbr = k
                break
    if fav_abbr not in teams:
        return "PENDING", "fav not in box"
    fav = teams[fav_abbr]
    dog = next(v for k, v in teams.items() if k != fav_abbr)
    margin = fav["score"] - dog["score"]
    # fav -3.5 covers if margin > 3.5
    need = abs(line)
    hit = margin > need
    return ("HIT" if hit else "MISS"), f"{fav_abbr} {fav['score']}-{dog['score']} margin={margin}"


def grade_ml(abbr: str, teams: dict) -> tuple[str, str]:
    if abbr not in teams:
        for k in teams:
            if abbr.upper() in k.upper():
                abbr = k
                break
    if abbr not in teams:
        return "PENDING", "team missing"
    t = teams[abbr]
    if t.get("winner") is True:
        return "HIT", f"{abbr} win {t['score']}"
    if t.get("winner") is False:
        return "MISS", f"{abbr} lose {t['score']}"
    # fallback compare
    other = next(v for k, v in teams.items() if k != abbr)
    if t["score"] > other["score"]:
        return "HIT", f"{abbr} {t['score']}-{other['score']}"
    if t["score"] < other["score"]:
        return "MISS", f"{abbr} {t['score']}-{other['score']}"
    return "PENDING", "tie/unfinished"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="20261127")
    args = ap.parse_args()
    path = OUT / f"TRACK-{args.date}-tickets.json"
    if not path.exists():
        raise SystemExit(f"missing {path}")
    track = json.loads(path.read_text())
    now = datetime.now(ET).isoformat()

    # Resolve NFL DEN@PIT event once
    nfl_events = nfl_scoreboard(args.date)
    denpit = find_nfl(nfl_events, "DEN PIT")

    # NBA/NHL event ids from today's gate if present
    gate = None
    for p in (
        Path("/cursor/stores/self/betting/GATE_TODAY.json"),
        OUT / "out" / "GATE_TODAY.json",
    ):
        if p.exists():
            gate = json.loads(p.read_text())
            break

    def event_id(sport_key: str, match: str) -> str | None:
        if not gate:
            return None
        for g in (gate.get("games") or {}).get(sport_key) or []:
            if match in (g.get("name") or ""):
                return g.get("id")
        return None

    for ticket in track["tickets"]:
        for leg in ticket["legs"]:
            if leg.get("result") in ("HIT", "MISS", "VOID"):
                continue
            sport = leg["sport"]
            try:
                if sport == "ncaam" and leg.get("event_id"):
                    fin = ncaam_final(str(leg["event_id"]))
                    if not fin or not fin.get("completed"):
                        leg["result"] = "PENDING"
                        leg["actual"] = (fin or {}).get("detail") or "not final"
                        continue
                    pick = leg["pick"]
                    if leg["market"] == "ML":
                        abbr = pick.split()[0]
                        res, actual = grade_ml(abbr, fin["teams"])
                    else:
                        # "BAY -3.5"
                        parts = pick.replace("−", "-").split()
                        abbr = parts[0]
                        line = float(parts[1])
                        res, actual = grade_spread(abbr, line, fin["teams"])
                    leg["result"] = res
                    leg["actual"] = actual
                elif sport == "nba":
                    eid = leg.get("event_id")
                    if not eid:
                        for g in (gate or {}).get("games", {}).get("NBA") or []:
                            if g.get("name") == leg.get("event"):
                                eid = g.get("id")
                                break
                    if not eid or not leg.get("athlete_id"):
                        continue
                    box = nba_box_player(str(eid), str(leg["athlete_id"]))
                    # check game final
                    summ = get(
                        f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={eid}"
                    )
                    completed = (
                        ((summ.get("header") or {}).get("competitions") or [{}])[0]
                        .get("status", {})
                        .get("type", {})
                        .get("completed")
                    )
                    if not completed:
                        leg["result"] = "PENDING"
                        leg["actual"] = "game not final"
                        continue
                    if not box:
                        leg["result"] = "VOID"
                        leg["actual"] = "player not in box (DNP?)"
                        continue
                    stats = box["stats"]
                    if leg["market"] == "AST":
                        val = float(stats.get("assists") or stats.get("AST") or 0)
                    elif leg["market"] == "3PT":
                        # try threes made
                        val = None
                        for k in ("threePointFieldGoalsMade", "3PM", "fg3m"):
                            if stats.get(k) not in (None, ""):
                                val = float(stats[k])
                                break
                        if val is None:
                            # sometimes "3PT" like "2-5"
                            raw = stats.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted") or stats.get("3PT")
                            if raw and "-" in str(raw):
                                val = float(str(raw).split("-")[0])
                            else:
                                val = 0.0
                    else:
                        continue
                    line = float(leg["line"])
                    leg["result"] = "HIT" if val > line else "MISS"
                    leg["actual"] = f"{val} (need >{line}) min={box.get('minutes')}"
                elif sport == "nhl":
                    eid = leg.get("event_id")
                    if not eid:
                        for g in (gate or {}).get("games", {}).get("NHL") or []:
                            if g.get("name") == leg.get("event"):
                                eid = g.get("id")
                                break
                    if not eid or not leg.get("athlete_id"):
                        continue
                    summ = get(
                        f"https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event={eid}"
                    )
                    completed = (
                        ((summ.get("header") or {}).get("competitions") or [{}])[0]
                        .get("status", {})
                        .get("type", {})
                        .get("completed")
                    )
                    if not completed:
                        leg["result"] = "PENDING"
                        leg["actual"] = "game not final"
                        continue
                    sog = nhl_box_sog(str(eid), str(leg["athlete_id"]))
                    if sog is None:
                        leg["result"] = "PENDING"
                        leg["actual"] = "SOG not parsed"
                        continue
                    line = float(leg["line"])
                    leg["result"] = "HIT" if sog > line else "MISS"
                    leg["actual"] = f"{sog} SOG (need >{line})"
                elif sport == "nfl" and denpit:
                    c = (denpit.get("competitions") or [{}])[0]
                    st = (c.get("status") or {}).get("type") or {}
                    if not st.get("completed"):
                        leg["result"] = "PENDING"
                        leg["actual"] = st.get("detail") or "not final"
                        continue
                    teams = {}
                    for comp in c.get("competitors") or []:
                        abbr = (comp.get("team") or {}).get("abbreviation")
                        teams[abbr] = {
                            "score": int(float(comp.get("score") or 0)),
                            "winner": comp.get("winner"),
                            "homeAway": comp.get("homeAway"),
                        }
                    if leg["market"] == "TOTAL":
                        total = sum(t["score"] for t in teams.values())
                        line = float(leg["line"])
                        hit = total < line  # under
                        leg["result"] = "HIT" if hit else "MISS"
                        leg["actual"] = f"total={total} vs U{line}"
                    elif leg["market"] == "ML":
                        res, actual = grade_ml("DEN", teams)
                        leg["result"] = res
                        leg["actual"] = actual
                    elif leg["market"] == "RUSH_YD":
                        # parse leaders / box
                        s = get(
                            f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={denpit['id']}"
                        )
                        rush = None
                        for cat in (s.get("boxscore") or {}).get("players") or []:
                            for stt in cat.get("statistics") or []:
                                if (stt.get("name") or "").lower() not in (
                                    "rushing",
                                    "rushingYards",
                                ) and "rush" not in (stt.get("name") or "").lower():
                                    # still check labels
                                    pass
                                keys = stt.get("keys") or []
                                labels = stt.get("labels") or []
                                for ath in stt.get("athletes") or []:
                                    nm = ((ath.get("athlete") or {}).get("displayName") or "")
                                    if "Warren" not in nm:
                                        continue
                                    stats = dict(zip(keys, ath.get("stats") or []))
                                    # yards often 'yards' or index
                                    for k in ("yards", "YDS", "rushingYards"):
                                        if stats.get(k) not in (None, ""):
                                            rush = float(stats[k])
                                            break
                                    if rush is None and ath.get("stats"):
                                        # ESPN rushing: CAR, YDS, AVG, TD, LONG
                                        lab = dict(zip(labels, ath.get("stats") or []))
                                        if "YDS" in lab:
                                            rush = float(lab["YDS"])
                        if rush is None:
                            leg["result"] = "PENDING"
                            leg["actual"] = "Warren rush not found"
                        else:
                            line = float(leg["line"])
                            leg["result"] = "HIT" if rush > line else "MISS"
                            leg["actual"] = f"{rush} rush yds (need >{line})"
            except Exception as e:
                leg["result"] = "PENDING"
                leg["actual"] = f"error: {e}"

        # ticket rollup
        results = [lg["result"] for lg in ticket["legs"]]
        if any(r == "MISS" for r in results):
            ticket["status"] = "LOST"
        elif all(r in ("HIT", "VOID") for r in results) and any(r == "HIT" for r in results):
            ticket["status"] = "WON" if all(r == "HIT" for r in results) else "WON_WITH_VOID"
        elif all(r == "HIT" for r in results):
            ticket["status"] = "WON"
        else:
            ticket["status"] = "OPEN"

    track["status"] = (
        "DONE"
        if all(t.get("status") in ("WON", "LOST", "WON_WITH_VOID") for t in track["tickets"])
        else "OPEN"
    )
    track["last_settled_et"] = now
    path.write_text(json.dumps(track, indent=2))

    # human summary
    lines = [
        f"TRACK SETTLE {args.date} @ {now}",
        f"overall={track['status']}",
        "",
    ]
    for t in track["tickets"]:
        lines.append(f"=== {t['id']} {t['name']} → {t.get('status', 'OPEN')} ===")
        for lg in t["legs"]:
            lines.append(
                f"  {lg['result']:7} {lg['pick']}  | {lg.get('actual')}"
            )
        lines.append("")
    txt = OUT / f"TRACK-{args.date}-tickets.txt"
    txt.write_text("\n".join(lines))
    print(txt.read_text())
    print(f"wrote {path}")
    print(f"wrote {txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
