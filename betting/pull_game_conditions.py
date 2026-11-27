#!/usr/bin/env python3
"""Venue + weather for today's slate — mandatory before outdoor football cards/weeds.

Writes:
  betting/game-conditions-YYYYMMDD.{txt,json}
  /cursor/stores/self/betting/GAME_CONDITIONS.json (when store writable)

Outdoor NFL/NCAAF without a weather block = FAIL for that game (do not spine pass/rec overs).
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

UA = {"User-Agent": "Mozilla/5.0"}
ET = ZoneInfo("America/New_York")
STORE = Path(os.environ.get("BETTING_STORE", "/cursor/stores/self/betting"))
REPO = Path(__file__).resolve().parent


def _get(url: str, timeout: int = 25) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _today() -> str:
    return datetime.now(ET).strftime("%Y%m%d")


SPORTS = [
    ("nfl", "football/nfl", True),  # weather-critical when outdoor
    ("ncaaf", "football/college-football", True),
    ("nba", "basketball/nba", False),
    ("nhl", "hockey/nhl", False),
]


def _event_conditions(sport: str, event: dict, weather_critical: bool) -> dict:
    c = (event.get("competitions") or [{}])[0]
    venue = c.get("venue") or {}
    addr = venue.get("address") or {}
    eid = event.get("id")
    weather = c.get("weather") or event.get("weather") or {}
    indoor = venue.get("indoor")
    # summary often has richer weather
    if eid and weather_critical:
        try:
            path = (
                "football/nfl"
                if sport == "nfl"
                else "football/college-football"
                if sport == "ncaaf"
                else None
            )
            if path:
                s = _get(
                    f"https://site.api.espn.com/apis/site/v2/sports/{path}/summary?event={eid}"
                )
                gi = s.get("gameInfo") or {}
                weather = gi.get("weather") or s.get("weather") or weather
                if indoor is None:
                    indoor = (gi.get("venue") or {}).get("indoor")
                if not venue.get("fullName"):
                    venue = gi.get("venue") or venue
        except Exception as e:  # noqa: BLE001
            weather = {**weather, "fetch_error": str(e)[:120]}

    outdoor = indoor is False or (
        indoor is None and weather_critical and bool(venue.get("fullName"))
    )
    temp = weather.get("temperature") or weather.get("highTemperature")
    precip = weather.get("precipitation")
    gust = weather.get("gust")
    display = weather.get("displayValue") or weather.get("conditionId")
    # Flag pass-hostile outdoor football
    pass_hostile = False
    notes = []
    if weather_critical and outdoor:
        try:
            if temp is not None and float(temp) <= 40:
                notes.append(f"cold≤40°F({temp})")
                pass_hostile = True
        except (TypeError, ValueError):
            pass
        try:
            if precip is not None and float(precip) >= 40:
                notes.append(f"precip≥40%({precip})")
                pass_hostile = True
        except (TypeError, ValueError):
            pass
        try:
            if gust is not None and float(gust) >= 20:
                notes.append(f"gust≥20({gust})")
                pass_hostile = True
        except (TypeError, ValueError):
            pass
        if display and str(display).lower() in (
            "rain",
            "snow",
            "storm",
            "showers",
            "thunderstorm",
        ):
            notes.append(f"cond={display}")
            pass_hostile = True
        if not weather or (temp is None and precip is None and not display):
            notes.append("WEATHER_MISSING")

    o = (c.get("odds") or [{}])[0]
    return {
        "sport": sport,
        "event_id": eid,
        "name": event.get("shortName") or event.get("name"),
        "status": (event.get("status") or {}).get("type", {}).get("detail"),
        "venue": venue.get("fullName"),
        "city": addr.get("city"),
        "state": addr.get("state"),
        "indoor": indoor,
        "outdoor": outdoor,
        "odds": o.get("details"),
        "ou": o.get("overUnder"),
        "weather": weather,
        "temp_f": temp,
        "precip_pct": precip,
        "gust_mph": gust,
        "condition": display,
        "pass_hostile": pass_hostile,
        "notes": notes,
        "weather_critical": weather_critical,
    }


def main() -> int:
    date = _today()
    rows: list[dict] = []
    for sport, path, critical in SPORTS:
        extra = "&limit=100" if sport == "ncaaf" else ""
        try:
            sb = _get(
                f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={date}{extra}"
            )
        except Exception as e:  # noqa: BLE001
            rows.append(
                {
                    "sport": sport,
                    "error": str(e)[:160],
                    "weather_critical": critical,
                }
            )
            continue
        for e in sb.get("events") or []:
            rows.append(_event_conditions(sport, e, critical))

    hostile = [r for r in rows if r.get("pass_hostile")]
    missing = [
        r
        for r in rows
        if r.get("weather_critical")
        and r.get("outdoor")
        and "WEATHER_MISSING" in (r.get("notes") or [])
    ]

    payload = {
        "date": date,
        "generated_at": datetime.now(ET).isoformat(),
        "n": len(rows),
        "pass_hostile_games": [
            r.get("name") for r in hostile if r.get("name")
        ],
        "weather_missing_outdoor": [
            r.get("name") for r in missing if r.get("name")
        ],
        "rows": rows,
        "rules": {
            "outdoor_football": "Pull venue+weather before any NFL/NCAAF card or slip weed",
            "pass_hostile": "temp≤40 OR precip%≥40 OR gust≥20 OR rain/snow → demote pass/rec overs; prefer rush + Under + soft sides",
            "location": "Always state venue city + home/away/neutral + indoor/outdoor on BY GAME",
        },
    }

    out_json = REPO / f"game-conditions-{date}.json"
    out_txt = REPO / f"game-conditions-{date}.txt"
    out_json.write_text(json.dumps(payload, indent=2))
    lines = [
        f"GAME CONDITIONS — {date}",
        f"pass_hostile: {payload['pass_hostile_games'] or 'none'}",
        f"weather_missing_outdoor: {payload['weather_missing_outdoor'] or 'none'}",
        "",
    ]
    for r in rows:
        if r.get("error"):
            lines.append(f"  {r['sport']}: ERROR {r['error']}")
            continue
        tag = "PASS_HOSTILE" if r.get("pass_hostile") else ("OUTDOOR" if r.get("outdoor") else "INDOOR/NA")
        lines.append(
            f"  [{tag}] {r.get('sport')} {r.get('name')} | {r.get('venue')} ({r.get('city')}, {r.get('state')})"
            f" indoor={r.get('indoor')} | {r.get('condition')} {r.get('temp_f')}F precip={r.get('precip_pct')} gust={r.get('gust_mph')}"
            f" | {r.get('odds')} O/U {r.get('ou')} | notes={r.get('notes')}"
        )
    out_txt.write_text("\n".join(lines) + "\n")

    try:
        STORE.mkdir(parents=True, exist_ok=True)
        (STORE / "GAME_CONDITIONS.json").write_text(json.dumps(payload, indent=2))
        (STORE / f"GAME_CONDITIONS_{date}.json").write_text(json.dumps(payload, indent=2))
    except OSError:
        pass

    print(out_txt.read_text())
    print(f"wrote {out_json}")
    if missing:
        print("WARN: outdoor football missing weather — do not spine pass/rec until fixed")
        return 2
    if hostile:
        print("WARN: pass-hostile outdoor game(s) — demote pass/rec overs; prefer rush/Under")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
