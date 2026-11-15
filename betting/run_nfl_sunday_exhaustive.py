#!/usr/bin/env python3
"""NFL Sunday exhaustive — every game, every offense player, every prop cat.

Usage:
  python3 betting/run_nfl_sunday_exhaustive.py --date 20261115

Writes:
  betting/out/GATE_SHEETS_NFL_{date}.json
  betting/posted-mains-nfl-{date}.{json,txt}
  betting/NFL-EXHAUSTIVE-{date}.{txt,json}
  mirrors GATE_TODAY when --write-gate
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OUT = Path(__file__).resolve().parent
STORE = Path("/cursor/stores/self/betting")
ET = ZoneInfo("America/New_York")
UA = {"User-Agent": "Mozilla/5.0 (nfl-exhaustive/1.0)"}

OFFENSE_POS = {"QB", "RB", "FB", "WR", "TE"}
PROP_KEYS = {
    "PASS_YD": "passingYards",
    "PASS_TD": "passingTouchdowns",
    "RUSH_YD": "rushingYards",
    "RUSH_ATT": "rushingAttempts",
    "REC": "receptions",
    "REC_YD": "receivingYards",
    "REC_TD": "receivingTouchdowns",
    "TARGETS": "receivingTargets",
}
# Walk posted down until 6/7 — stop at soft floor
SOFT = {
    "PASS_YD": 149.5,
    "PASS_TD": 0.5,
    "RUSH_YD": 5.5,
    "RUSH_ATT": 2.5,
    "REC": 0.5,
    "REC_YD": 8.5,
    "REC_TD": 0.5,
    "TARGETS": 1.5,
}
SHAVE_STEP = {
    "PASS_YD": 1.0,
    "PASS_TD": 1.0,
    "RUSH_YD": 1.0,
    "RUSH_ATT": 1.0,
    "REC": 1.0,
    "REC_YD": 1.0,
    "REC_TD": 1.0,
    "TARGETS": 1.0,
}
BETRAVON = {
    "passing-yards": "PASS_YD",
    "rushing-yards": "RUSH_YD",
    "receiving-yards": "REC_YD",
    "receptions": "REC",
}


def get(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def get_text(url: str, timeout: int = 45) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def scoreboard(date: str) -> list[dict]:
    sb = get(f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={date}")
    out = []
    for e in sb.get("events") or []:
        comp = e["competitions"][0]
        away = next(t for t in comp["competitors"] if t["homeAway"] == "away")
        home = next(t for t in comp["competitors"] if t["homeAway"] == "home")
        odds = (comp.get("odds") or [{}])[0]
        out.append(
            {
                "sport": "nfl",
                "id": e["id"],
                "name": e.get("shortName") or e.get("name"),
                "date": e.get("date"),
                "status": comp["status"]["type"].get("description"),
                "away": away["team"]["abbreviation"],
                "home": home["team"]["abbreviation"],
                "away_id": away["team"]["id"],
                "home_id": home["team"]["id"],
                "odds": odds.get("details"),
                "ou": odds.get("overUnder"),
                "spread_home": None,
            }
        )
        # parse spread from details e.g. "HOU -4.5"
        det = odds.get("details") or ""
        m = re.match(r"([A-Z]+)\s+([+-]?\d+(?:\.\d+)?)", det)
        if m:
            fav, line = m.group(1), float(m.group(2))
            out[-1]["fav"] = fav
            out[-1]["spread"] = line
    return out


def roster_offense(team_id: str, abbr: str) -> list[dict]:
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/roster"
    d = get(url)
    people = []
    for g in d.get("athletes") or []:
        group = (g.get("position") or "").lower()
        if group not in ("offense", "injuredreserveorout"):
            continue
        for a in g.get("items") or []:
            pos = ((a.get("position") or {}).get("abbreviation") or "").upper()
            if pos not in OFFENSE_POS:
                continue
            injuries = a.get("injuries") or []
            inj = None
            if injuries:
                inj = {
                    "status": (injuries[0].get("status") or ""),
                    "type": (injuries[0].get("type") or {}).get("description")
                    or (injuries[0].get("description") or ""),
                }
            status_group = group
            people.append(
                {
                    "name": a["displayName"],
                    "athlete_id": str(a["id"]),
                    "team": abbr,
                    "pos": pos,
                    "roster_group": status_group,
                    "injury": inj,
                }
            )
    return people


def nfl_gamelog(aid: str) -> dict:
    d = get(f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{aid}/gamelog")
    names = d.get("names") or []
    idx = {c: i for i, c in enumerate(names)}
    rows = []
    for st in d.get("seasonTypes", []):
        if "pre" in (st.get("displayName") or "").lower():
            continue
        for cat in st.get("categories", []):
            for ev in cat.get("events", []):
                vals = ev.get("stats") or []
                row = {"eventId": str(ev.get("eventId"))}
                for key, col in PROP_KEYS.items():
                    if col in idx and idx[col] < len(vals):
                        try:
                            row[key] = float(vals[idx[col]])
                        except Exception:
                            row[key] = "NOT_FETCHED"
                    else:
                        row[key] = None  # position doesn't have this cat
                rows.append(row)
    present = [k for k, col in PROP_KEYS.items() if col in idx]
    return {
        "names": names,
        "present_cats": present,
        "rows": rows[:12],
        "n": len(rows),
        "source": f"espn:site.web.api/nfl/athletes/{aid}/gamelog",
    }


def pull_betravon() -> list[dict]:
    rows_out = []
    for slug, label in BETRAVON.items():
        url = f"https://www.betravon.com/nfl/player-props/{slug}"
        try:
            html = get_text(url)
        except Exception as e:
            print(f"betravon {slug}: FAIL {e}", file=sys.stderr)
            continue
        m = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', html, flags=re.S
        )
        if not m:
            print(f"betravon {slug}: no NEXT_DATA", file=sys.stderr)
            continue
        data = json.loads(m.group(1))
        rows = (
            data.get("props", {}).get("pageProps", {}).get("data", {}).get("rows", [])
            or []
        )
        print(f"betravon {slug}: {len(rows)} posted")
        for r in rows:
            if r.get("line") is None:
                continue
            rows_out.append(
                {
                    "source": "betravon",
                    "sport": "nfl",
                    "player": r.get("player"),
                    "team": r.get("team"),
                    "opponent": r.get("opponent"),
                    "is_home": r.get("isHome"),
                    "game_time": r.get("gameTime"),
                    "stat": label,
                    "stat_slug": slug,
                    "line": float(r["line"]),
                    "books": r.get("books"),
                    "l10_n": r.get("l10n"),
                    "l10_over": r.get("l10over"),
                }
            )
    return rows_out


def hit_rate(vals: list[float], line: float) -> tuple[int, int]:
    n = len(vals)
    h = sum(1 for v in vals if v > line)
    return h, n


def grade_label(h: int, n: int) -> str:
    if n <= 0:
        return "SKIP"
    if n < 4:
        return "SKIP"
    # KEEP needs 6/7 or better; 5/5 ok; 5/6 RISK-KEEP
    if n >= 7 and h >= 6:
        return "KEEP"
    if n == 6 and h >= 5:
        return "KEEP" if h == 6 else "RISK-KEEP"
    if n == 5 and h >= 5:
        return "KEEP"
    if n == 5 and h == 4:
        return "RISK-KEEP"
    if n >= 7 and h == 5:
        return "RISK-KEEP"
    if n >= 7 and h == 4:
        return "RISK"
    return "CUT"


def shave_to_67(vals: list[float], posted: float, stat: str) -> dict:
    soft = SOFT.get(stat, 0.5)
    step = SHAVE_STEP.get(stat, 1.0)
    best = None
    line = posted
    while line >= soft - 1e-9:
        h, n = hit_rate(vals, line)
        lab = grade_label(h, n)
        if lab in ("KEEP",) and (best is None or line > best["line"]):
            # first KEEP from top — keep walking for deepest; record first KEEP
            if best is None:
                best = {"line": line, "hits": h, "n": n, "label": lab}
            # prefer highest KEEP (least shave) as primary; track deepest too
        if lab == "KEEP":
            if best is None or line > best["line"]:
                best = {"line": line, "hits": h, "n": n, "label": lab}
            deepest = {"line": line, "hits": h, "n": n, "label": lab}
        line = round(line - step, 1)
        if line < soft:
            break
    # recompute deepest KEEP
    deepest = None
    line = posted
    first_keep = None
    while line >= soft - 1e-9:
        h, n = hit_rate(vals, line)
        if grade_label(h, n) == "KEEP":
            if first_keep is None:
                first_keep = {"line": line, "hits": h, "n": n, "label": "KEEP"}
            deepest = {"line": line, "hits": h, "n": n, "label": "KEEP"}
        line = round(line - step, 1)
        if line < soft:
            break
    h0, n0 = hit_rate(vals, posted)
    return {
        "posted": posted,
        "g_main": grade_label(h0, n0),
        "hits_main": h0,
        "n": n0,
        "first_67": first_keep,
        "deepest_67": deepest,
        "soft_floor": soft,
        "can_67": first_keep is not None,
    }


def norm_name(s: str) -> str:
    s = (s or "").lower().replace(".", "").replace("'", "").replace("-", " ")
    for suf in (" jr", " sr", " iii", " ii", " iv"):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return " ".join(s.split())


def soft_spread(raw: float) -> float | None:
    """Ban raw -9.5+; offer soft alt. Also soft mid-hooks."""
    if raw is None:
        return None
    a = abs(raw)
    if a >= 10:
        return 5.5
    if a >= 9.5:
        return 3.0
    if a >= 8.0:
        return 3.0
    if a >= 6.5:
        return 3.0
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="20261115")
    ap.add_argument("--write-gate", action="store_true")
    ap.add_argument("--max-players", type=int, default=520)
    args = ap.parse_args()
    date = args.date
    started = datetime.now(timezone.utc).isoformat()
    now_et = datetime.now(ET).strftime("%a %m/%d %I:%M %p ET")

    print(f"=== NFL EXHAUSTIVE {date} · {now_et} ===")
    games = scoreboard(date)
    print(f"games: {len(games)}")
    for g in games:
        print(f"  {g['name']}  {g.get('odds')}  O/U {g.get('ou')}  {g.get('date')}")

    # rosters
    players: list[dict] = []
    seen = set()
    for g in games:
        for tid, abbr in ((g["away_id"], g["away"]), (g["home_id"], g["home"])):
            try:
                for p in roster_offense(tid, abbr):
                    if p["athlete_id"] in seen:
                        continue
                    seen.add(p["athlete_id"])
                    p["game"] = g["name"]
                    p["game_id"] = g["id"]
                    players.append(p)
            except Exception as e:
                print(f"roster FAIL {abbr}: {e}", file=sys.stderr)
    players = players[: args.max_players]
    print(f"offense players: {len(players)}")

    sheets: dict[str, dict] = {}

    def fetch_one(p):
        try:
            gl = nfl_gamelog(p["athlete_id"])
            return p["name"], {
                **p,
                "sport": "nfl",
                "ok": True,
                "missing_cats": [],
                "n_rs": gl["n"],
                "rows": gl["rows"],
                "present_cats": gl["present_cats"],
                "source": gl["source"],
                "names_schema": gl["names"],
            }
        except Exception as e:
            err = str(e)
            skip = "http_404" if "404" in err else None
            return p["name"], {
                **p,
                "sport": "nfl",
                "ok": bool(skip),
                "skip": skip,
                "error": err,
                "missing_cats": list(PROP_KEYS) if not skip else [],
                "n_rs": 0,
                "rows": [],
                "present_cats": [],
            }

    with ThreadPoolExecutor(24) as ex:
        futs = [ex.submit(fetch_one, p) for p in players]
        for f in as_completed(futs):
            name, sheet = f.result()
            key = name
            if key in sheets:
                key = f"{name} ({sheet.get('team')})"
            sheets[key] = sheet

    ok_n = sum(1 for s in sheets.values() if s.get("ok"))
    print(f"sheets ok {ok_n}/{len(sheets)}")

    # Betravon posted
    posted = pull_betravon()
    # Filter to Sunday slate teams
    slate_teams = set()
    for g in games:
        slate_teams.add(g["away"])
        slate_teams.add(g["home"])
    # Betravon may use WSH vs WAS etc — keep all with matching game window loosely
    # Index sheets by normalized name
    by_name: dict[str, list[tuple[str, dict]]] = {}
    for name, s in sheets.items():
        by_name.setdefault(norm_name(name), []).append((name, s))
        by_name.setdefault(norm_name(s.get("name") or name), []).append((name, s))

    graded = []
    unmatched = []
    for r in posted:
        pname = r["player"]
        nn = norm_name(pname)
        cands = by_name.get(nn) or []
        # fuzzy last-token
        if not cands:
            last = nn.split()[-1] if nn else ""
            for k, v in by_name.items():
                if last and last in k.split() and (nn.split()[0] in k if nn.split() else False):
                    cands = v
                    break
        if not cands:
            unmatched.append(r)
            continue
        # prefer matching team abbr
        pick = cands[0]
        t = (r.get("team") or "").upper()
        for name, s in cands:
            if (s.get("team") or "").upper() == t or t in (s.get("team") or "").upper():
                pick = (name, s)
                break
        name, s = pick
        if s.get("roster_group") == "injuredreserveorout":
            graded.append(
                {
                    "player": name,
                    "athlete_id": s.get("athlete_id"),
                    "team": s.get("team"),
                    "pos": s.get("pos"),
                    "game": s.get("game"),
                    "stat": r["stat"],
                    "posted": r["line"],
                    "label": "OUT",
                    "vals": [],
                    "injury": s.get("injury"),
                    "source": s.get("source"),
                    "posted_src": "betravon",
                }
            )
            continue
        key = r["stat"]
        vals = []
        for row in s.get("rows") or []:
            v = row.get(key)
            if v is None or v == "NOT_FETCHED":
                continue
            vals.append(float(v))
        vals = vals[:7]
        if not vals:
            graded.append(
                {
                    "player": name,
                    "athlete_id": s.get("athlete_id"),
                    "team": s.get("team"),
                    "pos": s.get("pos"),
                    "game": s.get("game"),
                    "stat": key,
                    "posted": r["line"],
                    "label": "NOT_FETCHED",
                    "vals": [],
                    "source": s.get("source"),
                    "posted_src": "betravon",
                }
            )
            continue
        sh = shave_to_67(vals, r["line"], key)
        soft = r["line"] <= SOFT.get(key, 0.5) + 1e-9
        label = sh["g_main"]
        if soft and label in ("KEEP", "RISK-KEEP"):
            label = "SOFT"
        graded.append(
            {
                "player": name,
                "athlete_id": s.get("athlete_id"),
                "team": s.get("team"),
                "pos": s.get("pos"),
                "game": s.get("game"),
                "stat": key,
                "posted": r["line"],
                "label": label,
                "hits_main": sh["hits_main"],
                "n": sh["n"],
                "vals": vals,
                "first_67": sh["first_67"],
                "deepest_67": sh["deepest_67"],
                "can_67": sh["can_67"],
                "soft": soft,
                "injury": s.get("injury"),
                "source": s.get("source"),
                "posted_src": "betravon",
                "books": r.get("books"),
            }
        )

    # Also grade every sheet×present cat at common floors even without posted (internal)
    # — user asked every prop; posted mains are Gate 2; extras marked INTERNAL
    # Skip to keep board readable — focus posted + full per-player cat dump in by-game

    # Game markets
    game_board = []
    for g in games:
        fav = g.get("fav")
        spread = g.get("spread")
        ou = g.get("ou")
        soft = soft_spread(spread) if spread is not None else None
        ban_raw = spread is not None and abs(spread) >= 9.5
        game_board.append(
            {
                "game": g["name"],
                "id": g["id"],
                "raw": g.get("odds"),
                "fav": fav,
                "spread": spread,
                "soft_alt": soft,
                "ban_raw": ban_raw,
                "ou": ou,
                "status": g.get("status"),
                "kick": g.get("date"),
            }
        )

    # Buckets
    keep = [x for x in graded if x["label"] == "KEEP"]
    risk_keep = [x for x in graded if x["label"] == "RISK-KEEP"]
    softs = [x for x in graded if x["label"] == "SOFT"]
    risk = [x for x in graded if x["label"] == "RISK"]
    cut = [x for x in graded if x["label"] == "CUT"]
    outs = [x for x in graded if x["label"] == "OUT"]
    # BANGERS = KEEP at posted OR first_67 within small shave
    bangers = []
    for x in graded:
        if x["label"] == "KEEP" and not x.get("soft"):
            bangers.append({**x, "play_line": x["posted"], "play_why": "posted KEEP"})
        elif x.get("can_67") and x["label"] in ("RISK-KEEP", "RISK", "CUT"):
            fk = x["first_67"]
            drop = x["posted"] - fk["line"]
            # meaningful but not absurd shave
            max_drop = {"PASS_YD": 45, "RUSH_YD": 20, "REC_YD": 25, "REC": 2, "PASS_TD": 1}.get(
                x["stat"], 15
            )
            if drop <= max_drop and fk["line"] > SOFT.get(x["stat"], 0.5):
                bangers.append(
                    {
                        **x,
                        "play_line": fk["line"],
                        "play_why": f"shave −{drop} → 6/7+",
                        "label_play": "KEEP",
                    }
                )

    # Sort bangers by hits then low drop
    def bang_key(x):
        drop = x["posted"] - x.get("play_line", x["posted"])
        return (-(x.get("hits_main") or 0), drop)

    bangers.sort(key=bang_key)

    # SAFE = KEEP posted non-soft
    safe = sorted(keep, key=lambda x: (-x.get("hits_main", 0), x["stat"], x["player"]))
    primary = safe[:20] + [
        {**x, "posted": x.get("play_line", x["posted"]), "note": x.get("play_why")}
        for x in bangers
        if x.get("play_line") != x.get("posted")
    ][:15]

    # Write sheets
    out_dir = OUT / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    sheets_path = out_dir / f"GATE_SHEETS_NFL_{date}.json"
    sheets_path.write_text(json.dumps(sheets, indent=2))
    try:
        STORE.mkdir(parents=True, exist_ok=True)
        (STORE / f"GATE_SHEETS_NFL_{date}.json").write_text(json.dumps(sheets, indent=2))
    except Exception:
        pass

    if args.write_gate:
        failures = []
        if not games:
            failures.append("No NFL games")
        if ok_n < 50:
            failures.append(f"NFL sheets insufficient ok={ok_n}")
        gate = {
            "status": "PASS" if not failures else "FAIL",
            "date": date,
            "started_utc": started,
            "finished_utc": datetime.now(timezone.utc).isoformat(),
            "tz": "America/New_York",
            "sports_active": {"NFL": len(games)},
            "games": {"NFL": games},
            "sheets_ok": ok_n,
            "sheets_total": len(sheets),
            "failures": failures,
            "sheets_path": str(sheets_path),
            "rules": [
                "NFL Sunday exhaustive — offense sheets + Betravon posted props",
                "Soft floors: REC≤0.5 REC_YD≤8.5 RUSH_YD≤5.5 PASS_YD≤149.5",
                "Ban raw NFL -9.5+ without soft alt",
            ],
        }
        payload = json.dumps(gate, indent=2)
        for store in (out_dir, STORE):
            try:
                store.mkdir(parents=True, exist_ok=True)
                (store / "GATE_TODAY.json").write_text(payload)
                (store / "GATE_STATUS.txt").write_text(
                    f"{gate['status']} date={date} NFL sheets {ok_n}/{len(sheets)}\n"
                )
            except Exception as e:
                print(f"gate write skip {store}: {e}", file=sys.stderr)
        print(f"GATE {gate['status']} date={date}")

    # posted dump
    posted_payload = {
        "date": date,
        "n": len(posted),
        "rows": posted,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (OUT / f"posted-mains-nfl-{date}.json").write_text(json.dumps(posted_payload, indent=2))

    # Build text card
    lines = []
    lines.append(f"NFL SUNDAY EXHAUSTIVE · {date} · {now_et}")
    lines.append(f"GATE sheets {ok_n}/{len(sheets)} · games {len(games)} · posted props graded {len(graded)}")
    lines.append(f"G1 ESPN offense gamelogs · G2 Betravon mains · G3 confirm HR floor before bet")
    lines.append(f"Unmatched posted (no sheet): {len(unmatched)}")
    lines.append("")

    lines.append("=" * 60)
    lines.append("BANGERS (posted KEEP or shave→6/7)")
    lines.append("=" * 60)
    for i, x in enumerate(bangers[:25], 1):
        pl = x.get("play_line", x["posted"])
        why = x.get("play_why", "posted")
        h = x.get("hits_main")
        n = x.get("n")
        lines.append(
            f"{i}. {x['player']}  {x['stat']} O{pl}  [{x.get('label_play', x['label'])}]  "
            f"L7 {h}/{n} · posted O{x['posted']} · {why}"
        )
        lines.append(
            f"   {x.get('game')} · {x.get('team')} {x.get('pos')} · id={x.get('athlete_id')}"
        )
        lines.append(f"   L7 vals {x.get('vals')}")
        lines.append(f"   source={x.get('source')}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("SAFE (KEEP @ posted, non-soft)")
    lines.append("=" * 60)
    if not safe:
        lines.append("  (none at posted — use BANGERS shaves)")
    for x in safe[:30]:
        lines.append(
            f"  KEEP  {x['hits_main']}/{x['n']}  {x['player']:22} O{x['posted']} {x['stat']:7} "
            f"{x.get('game')} id={x.get('athlete_id')}"
        )
        lines.append(f"         L={x.get('vals')}")
    lines.append("")

    lines.append("=" * 60)
    lines.append("PRIMARY (SAFE + best shaves)")
    lines.append("=" * 60)
    seen_p = set()
    for x in primary:
        key = (x["player"], x["stat"], x.get("posted"))
        if key in seen_p:
            continue
        seen_p.add(key)
        note = x.get("note") or x.get("play_why") or ""
        lines.append(
            f"  {x.get('label','KEEP'):10} {x['player']:22} {x['stat']} O{x['posted']}  "
            f"{x.get('game')}  {note}"
        )
    lines.append("")

    lines.append("=" * 60)
    lines.append("GAME MARKETS (every game)")
    lines.append("=" * 60)
    for g in game_board:
        ban = " BAN-RAW" if g["ban_raw"] else ""
        soft = f" · soft {g['fav']} −{g['soft_alt']}" if g.get("soft_alt") and g["ban_raw"] else ""
        if g.get("soft_alt") and not g["ban_raw"] and g.get("spread") and abs(g["spread"]) >= 6.5:
            soft = f" · soft alt −{g['soft_alt']}"
        lines.append(
            f"  {g['game']:12}  {g['raw'] or '?':12}  O/U {g['ou']}{ban}{soft}  kick={g['kick']}"
        )
    lines.append("")

    lines.append("=" * 60)
    lines.append("BY-GAME PROPS (all graded posted)")
    lines.append("=" * 60)
    by_game: dict[str, list] = {}
    for x in graded:
        by_game.setdefault(x.get("game") or "?", []).append(x)
    for gname in sorted(by_game):
        lines.append(f"\n── {gname} ──")
        rows = sorted(by_game[gname], key=lambda x: (x["label"], x["stat"], x["player"]))
        for x in rows:
            extra = ""
            if x.get("first_67") and x["label"] not in ("KEEP", "OUT", "SOFT"):
                fk = x["first_67"]
                extra = f" · shave→O{fk['line']} {fk['hits']}/{fk['n']}"
            lines.append(
                f"  {x['label']:10} {x.get('hits_main','-')}/{x.get('n','-')}  "
                f"{x['player']:22} O{x['posted']} {x['stat']:7} id={x.get('athlete_id')}{extra}"
            )
            if x.get("vals"):
                lines.append(f"             L={x['vals']}")

    lines.append("")
    lines.append("=" * 60)
    lines.append("RISK-KEEP @ posted")
    lines.append("=" * 60)
    for x in risk_keep[:40]:
        fk = x.get("first_67")
        sh = f" · →O{fk['line']}" if fk else " · no 6/7 above soft"
        lines.append(
            f"  {x['hits_main']}/{x['n']} {x['player']:22} O{x['posted']} {x['stat']}{sh}"
        )

    lines.append("")
    lines.append("=" * 60)
    lines.append("BAN")
    lines.append("=" * 60)
    lines.append("  Raw −9.5/+ spreads without soft alt")
    for g in game_board:
        if g["ban_raw"]:
            lines.append(f"  BAN RAW {g['raw']} → use soft −{g['soft_alt']} / ML")
    lines.append("  Soft juice pads: REC O0.5 · REC_YD ≤8.5 · RUSH_YD ≤5.5 as spine")
    lines.append("  Posted OUT / IR props:")
    for x in outs[:40]:
        lines.append(f"  OUT {x['player']} {x['stat']} O{x['posted']} {x.get('injury')}")
    ir_names = []
    q_names = []
    for name, s in sorted(sheets.items(), key=lambda kv: kv[0]):
        inj = s.get("injury") or {}
        st = (inj.get("status") or "")
        stl = st.lower()
        if "injur" in stl or s.get("roster_group") == "injuredreserveorout":
            ir_names.append(f"{name} {s.get('team')} {s.get('pos')} id={s.get('athlete_id')}")
        elif any(k in stl for k in ("question", "doubt")):
            q_names.append(f"{name} {s.get('team')} {s.get('pos')} status={st} id={s.get('athlete_id')}")
    lines.append(f"  IR roster ({len(ir_names)}) — do not spine:")
    for x in ir_names[:40]:
        lines.append(f"  IR {x}")
    lines.append(f"  Questionable ({len(q_names)}) — confirm active:")
    for x in q_names[:40]:
        lines.append(f"  Q {x}")

    # Clean slips
    lines.append("")
    lines.append("=" * 60)
    lines.append("CLEAN SLIPS")
    lines.append("=" * 60)
    # Slip A: best sides soft
    sides = []
    for g in game_board:
        if g["ban_raw"] and g.get("soft_alt") and g.get("fav"):
            sides.append(f"{g['fav']} −{g['soft_alt']}")
        elif g.get("spread") is not None and abs(g["spread"]) <= 4.5 and g.get("fav"):
            sides.append(f"{g['fav']} {g['spread']:+g}" if False else f"{g['raw']}")
    # simpler side picks from prior weekend logic + soft
    slip_a = []
    for g in game_board:
        if not g.get("fav") or g.get("spread") is None:
            continue
        if g.get("soft_alt") and (g["ban_raw"] or abs(g["spread"]) >= 6.5):
            slip_a.append(f"{g['fav']} −{g['soft_alt']} (soft from {g['raw']})")
        elif abs(g["spread"]) <= 5.5:
            slip_a.append(str(g.get("raw") or f"{g['fav']} {g['spread']}"))
    lines.append("SLIP A — SIDES (soft chalk / small numbers)")
    for i, s in enumerate(slip_a[:12], 1):
        lines.append(f"  {i}. {s}")
    lines.append("")
    lines.append("SLIP B — PROP BANGERS (4)")
    for i, x in enumerate(bangers[:4], 1):
        lines.append(
            f"  {i}. {x['player']} {x['stat']} O{x.get('play_line', x['posted'])}  "
            f"({x.get('game')})"
        )
    lines.append("")
    lines.append("SLIP C — MIX (3 sides + 3 props)")
    for i, s in enumerate(slip_a[:3], 1):
        lines.append(f"  {i}. {s}")
    for i, x in enumerate(bangers[:3], 4):
        lines.append(
            f"  {i}. {x['player']} {x['stat']} O{x.get('play_line', x['posted'])}"
        )
    lines.append("")
    lines.append("SLIP D — TOTALS lean (confirm script)")
    for g in game_board:
        if g.get("ou"):
            lines.append(f"  {g['game']} O/U {g['ou']} — grade live vs pace; no auto")
    lines.append("")
    lines.append(
        f"SUMMARY: KEEP={len(keep)} RISK-KEEP={len(risk_keep)} RISK={len(risk)} "
        f"CUT={len(cut)} SOFT={len(softs)} OUT={len(outs)} BANGERS={len(bangers)} "
        f"games={len(games)} sheets={ok_n}"
    )

    text = "\n".join(lines)
    txt_path = OUT / f"NFL-EXHAUSTIVE-{date}.txt"
    json_path = OUT / f"NFL-EXHAUSTIVE-{date}.json"
    txt_path.write_text(text)
    payload = {
        "date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "games": games,
        "game_board": game_board,
        "sheets_ok": ok_n,
        "sheets_total": len(sheets),
        "graded": graded,
        "bangers": bangers,
        "safe": safe,
        "unmatched_posted": unmatched,
        "counts": {
            "KEEP": len(keep),
            "RISK-KEEP": len(risk_keep),
            "RISK": len(risk),
            "CUT": len(cut),
            "SOFT": len(softs),
            "OUT": len(outs),
            "BANGERS": len(bangers),
        },
    }
    json_path.write_text(json.dumps(payload, indent=2))
    print(text[-3000:] if len(text) > 3000 else text)
    print(f"\nwrote {txt_path}")
    print(f"wrote {json_path}")
    print(f"wrote {sheets_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
