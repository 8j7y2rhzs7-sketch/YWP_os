#!/usr/bin/env python3
"""Season-wide trend / correlation scan across all GATE sheets.

Walks every player · every counting stat · every RS game we have sheeted.
Writes:
  betting/season-trends-YYYYMMDD.txt
  betting/season-trends-YYYYMMDD.json
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
OUT = Path(__file__).resolve().parent
STORE = Path("/cursor/stores/self/betting")

NBA_STATS = ["MIN", "PTS", "REB", "AST", "STL", "BLK", "3PT", "TO"]
NHL_STATS = ["SOG"]


def fnum(v):
    if v is None or v == "":
        return None
    try:
        if isinstance(v, str) and ":" in v:
            return float(v.split(":")[0])
        return float(v)
    except Exception:
        return None


def threes(row):
    raw = row.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted")
    if raw is None:
        return None
    try:
        return float(str(raw).split("-")[0])
    except Exception:
        return None


def row_vals(row, sport):
    if sport == "nba":
        return {
            "MIN": fnum(row.get("minutes")),
            "PTS": fnum(row.get("points")),
            "REB": fnum(row.get("totalRebounds")),
            "AST": fnum(row.get("assists")),
            "STL": fnum(row.get("steals")),
            "BLK": fnum(row.get("blocks")),
            "3PT": threes(row),
            "TO": fnum(row.get("turnovers")),
            "eventId": row.get("eventId"),
            "gameDate": row.get("gameDate"),
        }
    return {
        "SOG": fnum(row.get("shots")),
        "eventId": row.get("eventId"),
        "gameDate": row.get("gameDate"),
    }


def pearson(xs, ys):
    n = len(xs)
    if n < 8:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)


def hit_rate(vals, line):
    if not vals:
        return None
    return sum(1 for v in vals if v > line) / len(vals)


def load_universe():
    """Dedupe by athlete_id keeping max n_rs sheet."""
    files = sorted(set(list(STORE.glob("GATE_SHEETS_*.json")) + list((OUT / "out").glob("GATE_SHEETS_*.json"))))
    best: dict[str, dict] = {}
    for p in files:
        if "roster_verified" in p.name:
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        for name, rec in d.items():
            if not isinstance(rec, dict) or not rec.get("ok"):
                continue
            aid = str(rec.get("athlete_id") or "")
            if not aid:
                continue
            sport = rec.get("sport")
            if sport not in ("nba", "nhl"):
                continue
            rows = rec.get("rows") or []
            # normalize rows newest-first already usually
            key = f"{sport}:{aid}"
            cur = best.get(key)
            if cur is None or len(rows) > len(cur["rows"]):
                best[key] = {
                    "name": name,
                    "athlete_id": aid,
                    "sport": sport,
                    "team": rec.get("team"),
                    "rows": rows,
                    "source_file": p.name,
                }
    return best


def analyze_player(p):
    sport = p["sport"]
    games = []
    for r in p["rows"]:
        v = row_vals(r, sport)
        # require core presence
        if sport == "nba" and v["MIN"] is None:
            continue
        if sport == "nhl" and v["SOG"] is None:
            continue
        games.append(v)
    if sport == "nba":
        # active filter
        games = [g for g in games if (g["MIN"] or 0) > 0]
    if sport == "nhl":
        # drop goalies / shots-faced (avg SOG ≥ 10 is not a skater prop)
        sogs = [g["SOG"] for g in games if g.get("SOG") is not None]
        if sogs and (sum(sogs) / len(sogs)) >= 10:
            return None
        if p.get("team") and str(p.get("name", "")).lower() in set():
            return None
    n = len(games)
    if n < 5:
        return None

    stats = NBA_STATS if sport == "nba" else NHL_STATS
    series = {s: [g[s] for g in games if g.get(s) is not None] for s in stats}

    out = {
        "name": p["name"],
        "id": p["athlete_id"],
        "sport": sport,
        "team": p["team"],
        "n": n,
        "means": {},
        "stds": {},
        "cv": {},
        "l7_means": {},
        "drift_l7": {},
        "floors": {},
        "min_corr": {},
        "stat_corr": {},
        "min_cliff": {},
        "fake_firm": [],
        "stable_floors": [],
        "volatile": [],
    }

    for s, vals in series.items():
        if len(vals) < 5:
            continue
        mean = sum(vals) / len(vals)
        std = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        out["means"][s] = round(mean, 3)
        out["stds"][s] = round(std, 3)
        out["cv"][s] = round(std / mean, 3) if mean > 0.2 else None
        l7 = vals[:7]
        l7m = sum(l7) / len(l7)
        out["l7_means"][s] = round(l7m, 3)
        out["drift_l7"][s] = round(l7m - mean, 3)

        # floor ladder
        if s == "MIN":
            continue
        floors = {}
        # candidate lines
        if s in ("PTS",):
            cands = [x + 0.5 for x in range(4, 36)]
        elif s in ("REB", "AST"):
            cands = [x + 0.5 for x in range(0, 16)]
        elif s in ("STL", "BLK", "3PT"):
            cands = [0.5, 1.5, 2.5, 3.5, 4.5]
        elif s == "SOG":
            cands = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        else:
            cands = [0.5, 1.5, 2.5]
        for line in cands:
            hr = hit_rate(vals, line)
            hr7 = hit_rate(l7, line)
            floors[str(line)] = {"season": round(hr, 3), "l7": round(hr7, 3) if hr7 is not None else None}
            # fake firm: season/L7 perfect but soft
            soft = (s in ("REB", "AST", "STL") and line <= 1.5) or (s == "3PT" and line <= 0.5) or (s == "SOG" and line <= 1.5)
            if hr7 is not None and hr7 >= 0.99 and soft:
                out["fake_firm"].append({"stat": s, "line": line, "l7": 1.0, "season": hr})
            # stable non-soft floors clearing ≥85% season AND L7
            if (not soft) and hr >= 0.85 and hr7 is not None and hr7 >= 0.85:
                out["stable_floors"].append({"stat": s, "line": line, "season": hr, "l7": hr7})
        out["floors"][s] = floors

        # volatility flag
        cv = out["cv"][s]
        if cv is not None and cv >= 0.55 and mean >= 3:
            out["volatile"].append({"stat": s, "cv": cv, "mean": mean})

    # minutes correlations (NBA)
    if sport == "nba" and len(series.get("MIN") or []) >= 8:
        mins = []
        aligned = {s: [] for s in stats if s != "MIN"}
        for g in games:
            if g["MIN"] is None:
                continue
            mins.append(g["MIN"])
            for s in aligned:
                aligned[s].append(g.get(s) if g.get(s) is not None else 0.0)
        for s, ys in aligned.items():
            r = pearson(mins, ys)
            if r is not None:
                out["min_corr"][s] = round(r, 3)

        # minutes cliff: compare games MIN>=28 vs MIN<22
        hi = [g for g in games if (g["MIN"] or 0) >= 28]
        lo = [g for g in games if (g["MIN"] or 0) < 22]
        if len(hi) >= 3 and len(lo) >= 3:
            for s in ("PTS", "REB", "AST", "3PT"):
                hv = [g[s] for g in hi if g.get(s) is not None]
                lv = [g[s] for g in lo if g.get(s) is not None]
                if hv and lv:
                    out["min_cliff"][s] = {
                        "hi_mean": round(sum(hv) / len(hv), 2),
                        "lo_mean": round(sum(lv) / len(lv), 2),
                        "drop": round(sum(hv) / len(hv) - sum(lv) / len(lv), 2),
                        "n_hi": len(hv),
                        "n_lo": len(lv),
                    }

        # pairwise stat correlations
        pairs = [("PTS", "AST"), ("PTS", "REB"), ("AST", "REB"), ("PTS", "3PT"), ("REB", "STL"), ("MIN", "PTS")]
        for a, b in pairs:
            xs, ys = [], []
            for g in games:
                if g.get(a) is None or g.get(b) is None:
                    continue
                xs.append(g[a])
                ys.append(g[b])
            r = pearson(xs, ys)
            if r is not None:
                out["stat_corr"][f"{a}-{b}"] = round(r, 3)

    # highest stable floor per key stat
    best_stable = {}
    for sf in out["stable_floors"]:
        s = sf["stat"]
        if s not in best_stable or sf["line"] > best_stable[s]["line"]:
            best_stable[s] = sf
    out["best_stable"] = best_stable
    return out


def aggregate(players):
    """Global patterns across the league."""
    nba = [p for p in players if p["sport"] == "nba"]
    nhl = [p for p in players if p["sport"] == "nhl"]

    # 1) Minutes ↔ PTS/REB/AST average correlations
    min_corrs = defaultdict(list)
    for p in nba:
        for s, r in p.get("min_corr", {}).items():
            min_corrs[s].append(r)

    # 2) Soft-floor fake firm prevalence
    fake = []
    for p in nba:
        for f in p.get("fake_firm") or []:
            fake.append({**f, "player": p["name"], "team": p["team"]})

    # 3) L7 hot streaks that outrun season (trap risk when fading / boost risk)
    hot = []
    cold = []
    for p in nba:
        if p["n"] < 8:
            continue
        for s in ("PTS", "REB", "AST", "3PT"):
            d = p.get("drift_l7", {}).get(s)
            mean = p.get("means", {}).get(s)
            if d is None or mean is None:
                continue
            if d >= 3.0 and mean >= 5:
                hot.append({"player": p["name"], "stat": s, "drift": d, "season": mean, "l7": p["l7_means"][s], "team": p["team"]})
            if d <= -3.0 and mean >= 5:
                cold.append({"player": p["name"], "stat": s, "drift": d, "season": mean, "l7": p["l7_means"][s], "team": p["team"]})

    # 4) High-CV props (avoid firm claims)
    volatile = []
    for p in nba:
        for v in p.get("volatile") or []:
            volatile.append({**v, "player": p["name"], "team": p["team"]})

    # 5) Minutes cliff magnitude
    cliffs = []
    for p in nba:
        for s, c in (p.get("min_cliff") or {}).items():
            if c["drop"] >= 5:
                cliffs.append({**c, "player": p["name"], "stat": s, "team": p["team"]})

    # 6) Pairwise corr league averages
    pair_corrs = defaultdict(list)
    for p in nba:
        for k, r in p.get("stat_corr", {}).items():
            pair_corrs[k].append(r)

    # 7) Best true stable floors (non-soft) ranked
    stables = []
    for p in nba:
        for s, sf in (p.get("best_stable") or {}).items():
            # meaningful lines only
            if s == "PTS" and sf["line"] < 9.5:
                continue
            if s in ("REB", "AST") and sf["line"] < 2.5:
                continue
            if s == "3PT" and sf["line"] < 1.0:
                continue
            stables.append({**sf, "player": p["name"], "team": p["team"], "mpg": p["means"].get("MIN")})

    # 8) STL/BLK reality check — almost never firm above 0.5/1.5
    stl_blk = {"STL_0.5": [], "STL_1.5": [], "BLK_0.5": [], "BLK_1.5": []}
    for p in nba:
        for s, line in (("STL", 0.5), ("STL", 1.5), ("BLK", 0.5), ("BLK", 1.5)):
            fl = (p.get("floors") or {}).get(s, {}).get(str(line))
            if not fl:
                continue
            stl_blk[f"{s}_{line}"].append(fl["season"])

    # 9) NHL SOG stability
    nhl_sog = []
    for p in nhl:
        fl = (p.get("floors") or {}).get("SOG", {})
        for line in ("1.5", "2.5", "3.5"):
            if line in fl and fl[line]["season"] >= 0.85:
                nhl_sog.append({"player": p["name"], "line": float(line), "season": fl[line]["season"], "l7": fl[line]["l7"], "team": p["team"]})

    # 10) Rule: L7==7/7 but season << — regression traps
    traps = []
    for p in nba:
        for s, floors in (p.get("floors") or {}).items():
            for line, hr in floors.items():
                if hr["l7"] is None:
                    continue
                if hr["l7"] >= 0.99 and hr["season"] <= 0.70 and float(line) > 1.5:
                    traps.append(
                        {
                            "player": p["name"],
                            "stat": s,
                            "line": float(line),
                            "l7": hr["l7"],
                            "season": hr["season"],
                            "team": p["team"],
                        }
                    )

    def avg(xs):
        return round(sum(xs) / len(xs), 3) if xs else None

    summary = {
        "n_nba": len(nba),
        "n_nhl": len(nhl),
        "avg_min_corr": {k: avg(v) for k, v in min_corrs.items()},
        "avg_pair_corr": {k: avg(v) for k, v in pair_corrs.items()},
        "fake_firm_n": len(fake),
        "hot_n": len(hot),
        "cold_n": len(cold),
        "trap_n": len(traps),
        "stl_blk_avg_hit": {k: avg(v) for k, v in stl_blk.items()},
        "hot": sorted(hot, key=lambda x: -x["drift"])[:25],
        "cold": sorted(cold, key=lambda x: x["drift"])[:25],
        "traps": sorted(traps, key=lambda x: (x["season"] - x["l7"]))[:40],
        "stables": sorted(stables, key=lambda x: (-x["line"], -x["season"]))[:40],
        "volatile": sorted(volatile, key=lambda x: -x["cv"])[:25],
        "cliffs": sorted(cliffs, key=lambda x: -x["drop"])[:25],
        "fake_firm_sample": fake[:30],
        "nhl_sog": sorted(nhl_sog, key=lambda x: (-x["line"], -x["season"]))[:30],
        "pair_corr_dist": {k: {"mean": avg(v), "n": len(v)} for k, v in pair_corrs.items()},
        "min_corr_dist": {k: {"mean": avg(v), "n": len(v)} for k, v in min_corrs.items()},
    }
    return summary


def render(summary, players):
    lines = []
    lines.append("═" * 72)
    lines.append("SEASON TREND / CORRELATION SCAN · NBA + NHL")
    lines.append(f"Built {datetime.now(ET).strftime('%Y-%m-%d %I:%M %p ET')} · every sheeted RS game · no preseason")
    lines.append(f"Universe: {summary['n_nba']} NBA players · {summary['n_nhl']} NHL players (deduped max gamelog)")
    lines.append("═" * 72)

    lines.append("\n══ 1. BIG RULES THAT IMPROVE ACCURACY ══")
    lines.append("A. MINUTES ARE THE MASTER VARIABLE")
    for s, d in summary["min_corr_dist"].items():
        lines.append(f"   avg corr(MIN, {s}) = {d['mean']}  (n={d['n']} players)")
    lines.append("   → If minutes are GTD/rest/blowout risk, CUT the counting prop even if L7 is pretty.")
    lines.append("   → Prefer players with stable 28+ mpg; cliff games (<22 min) nuke PTS/AST first.")

    lines.append("\nB. L7 PERFECT ≠ SEASON TRUTH (regression traps)")
    lines.append(f"   Found {summary['trap_n']} player-stat lines with L7=7/7 but season hit ≤70% (line>1.5).")
    lines.append("   → Require BOTH L7≥6/7 AND season≥75% for spine — or shave until season also clears.")
    for t in summary["traps"][:12]:
        lines.append(
            f"   TRAP  {t['player']:<22} {t['stat']:<4} O{t['line']:<5} L7={t['l7']:.0%} season={t['season']:.0%} {t['team']}"
        )

    lines.append("\nC. SOFT FLOORS LOOK FIRM — THEY'RE BAIT")
    lines.append(f"   Fake-firm soft clears found: {summary['fake_firm_n']}")
    lines.append("   → Keep ban: REB/AST/STL ≤1.5 · 3PT ≤0.5 · SOG ≤1.5 even at 7/7.")

    lines.append("\nD. STL / BLK ARE NOT PARLAY SPINE STATS")
    for k, v in summary["stl_blk_avg_hit"].items():
        lines.append(f"   avg season hit {k}: {v}")
    lines.append("   → League-average STL O1.5 is weak; treat as lottery, not KEEP.")

    lines.append("\nE. STAT CORRELATIONS (same-game stacking)")
    for k, d in summary["pair_corr_dist"].items():
        lines.append(f"   avg corr {k}: {d['mean']} (n={d['n']})")
    lines.append("   → PTS-AST stacks are only mildly correlated — not automatic SGP hedges.")
    lines.append("   → PTS-3PT correlation exists but 3PT variance is still binary-ish.")
    lines.append("   → Double-dip same player (PTS+REB) still needs independent floors.")

    lines.append("\n══ 2. HOT / COLD L7 DRIFTS (mean L7 − season) ══")
    lines.append("HOT (L7 running hot — don't overpay posted; shave or wait regression):")
    for h in summary["hot"][:15]:
        lines.append(
            f"  +{h['drift']:<5} {h['player']:<22} {h['stat']:<4} L7={h['l7']:<6} season={h['season']:<6} {h['team']}"
        )
    lines.append("COLD (L7 cold — avoid chasing overs at season mean; wait or go under/pass):")
    for h in summary["cold"][:15]:
        lines.append(
            f"  {h['drift']:<6} {h['player']:<22} {h['stat']:<4} L7={h['l7']:<6} season={h['season']:<6} {h['team']}"
        )

    lines.append("\n══ 3. TRUE STABLE FLOORS (season≥85% AND L7≥85%, non-soft) ══")
    lines.append("These are the accuracy gold — highest clear line that stays firm both windows:")
    for s in summary["stables"][:25]:
        lines.append(
            f"  {s['player']:<22} {s['stat']:<4} O{s['line']:<5} season={s['season']:.0%} L7={s['l7']:.0%} mpg={s.get('mpg')} {s['team']}"
        )

    lines.append("\n══ 4. MINUTES CLIFF (MIN≥28 vs MIN<22) ══")
    lines.append("Largest mean drops when minutes crater — blowout / foul-out / DNP-SD risk:")
    for c in summary["cliffs"][:15]:
        lines.append(
            f"  {c['player']:<22} {c['stat']:<4} hi={c['hi_mean']:<6} lo={c['lo_mean']:<6} drop={c['drop']:<6} (n {c['n_hi']}/{c['n_lo']}) {c['team']}"
        )

    lines.append("\n══ 5. HIGH VOLATILITY (CV≥0.55, mean≥3) — don't call KEEP on main ══")
    for v in summary["volatile"][:15]:
        lines.append(f"  CV={v['cv']:<5} {v['player']:<22} {v['stat']:<4} mean={v['mean']:.1f} {v['team']}")

    lines.append("\n══ 6. NHL SOG STABLE ══")
    for s in summary["nhl_sog"][:15]:
        lines.append(
            f"  {s['player']:<22} SOG O{s['line']:<4} season={s['season']:.0%} L7={s['l7']:.0%} {s['team']}"
        )

    lines.append("\n══ 7. ACTIONABLE PROCESS UPGRADES ══")
    lines.append("1. Dual-window gate: KEEP only if L7 hit≥6/7 AND season hit≥75% at that exact line.")
    lines.append("2. Minutes gate: require L7 avg MIN≥24 (NBA) else demote to RISK / skip.")
    lines.append("3. Drift check: if L7 mean − season ≥ +3 on PTS/REB/AST, shave one extra step.")
    lines.append("4. Cliff tag: if player has ≥3 games under 22 min this season, never spine without minutes confirmation.")
    lines.append("5. Correlation: same-player PTS+AST is OK only if BOTH pass dual-window; don't treat as 1 risk.")
    lines.append("6. STL/BLK: research only — never parlay spine.")
    lines.append("7. Soft 7/7: still banned — accuracy ≠ juice efficiency.")
    lines.append("8. Hot L7 / cold season traps list → auto-shave or CUT from spine.")

    lines.append("\n══ 8. WHAT DID NOT POP (negative findings) ══")
    lines.append("· No magic universal PTS-REB lockstep — correlations are moderate, not destiny.")
    lines.append("· Perfect L7 alone is common and misleading — season window catches most bad spines.")
    lines.append("· NHL SOG above 3.5 rarely stays ≥85% season — prefer 2.5 floors.")
    lines.append("· Early-season NCAAM not in this sheet universe — keep separate landmine rules.")

    return "\n".join(lines) + "\n"


def main():
    print("Loading universe…")
    universe = load_universe()
    print(f"  deduped players: {len(universe)}")
    players = []
    for p in universe.values():
        a = analyze_player(p)
        if a:
            players.append(a)
    print(f"  analyzed (≥5 games): {len(players)}")
    summary = aggregate(players)
    text = render(summary, players)
    day = datetime.now(ET).strftime("%Y%m%d")
    (OUT / f"season-trends-{day}.txt").write_text(text)
    payload = {
        "generated_at": datetime.now(ET).isoformat(),
        "summary": summary,
        "players_n": len(players),
        # store compact player best_stable only to keep file usable
        "best_stables": summary["stables"],
        "traps": summary["traps"],
        "hot": summary["hot"],
        "cold": summary["cold"],
        "rules": [
            "dual_window_L7_and_season",
            "minutes_master_variable",
            "drift_extra_shave",
            "soft_floor_ban",
            "stl_blk_research_only",
            "minutes_cliff_tag",
        ],
    }
    (OUT / f"season-trends-{day}.json").write_text(json.dumps(payload, indent=2))
    print(text)
    print(f"Wrote betting/season-trends-{day}.txt/json")


if __name__ == "__main__":
    main()
