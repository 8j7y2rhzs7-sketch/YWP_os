"""ESPN scoreboard rows for a date when sportsbooks have not posted prices.

NBA preseason (and other gaps) still has a full ESPN slate while The Odds API
catalog marks the sport inactive. Those games must show up. They are not plays:
odds stay 0 and the row is suspended so the engine cannot grade them as priced.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas import CandidateInput
from app.services.espn_provider import espn_path_for, get_scoreboard

_LEAGUE = {
    "nba": "NBA",
    "wnba": "WNBA",
    "nfl": "NFL",
    "ncaaf": "NCAAF",
    "ncaab": "NCAAB",
    "nhl": "NHL",
    "soccer": "Soccer",
    "mls": "MLS",
    "epl": "EPL",
}


def espn_unpriced_schedule(sport: str, slate_date) -> list[CandidateInput]:
    sport_l = (sport or "").lower().strip()
    if not espn_path_for(sport_l):
        return []
    games = get_scoreboard(sport_l, slate_date)
    now = datetime.now(UTC)
    rows: list[CandidateInput] = []
    for game in games:
        event_id = str(game.get("event_id") or "").strip()
        home = str(game.get("home_team") or "").strip()
        away = str(game.get("away_team") or "").strip()
        if len(event_id) < 3 or not home or not away:
            continue
        start = _parse_start(game.get("start_time"))
        if start is None:
            continue
        event_name = f"{away} @ {home}"
        status_name = str(game.get("status") or "").upper()
        if game.get("completed") or "FINAL" in status_name:
            game_status = "FINAL"
        elif "IN_PROGRESS" in status_name or status_name in {"LIVE", "STATUS_HALFTIME"}:
            game_status = "LIVE"
        elif "POSTPON" in status_name:
            game_status = "POSTPONED"
        elif "CANCEL" in status_name:
            game_status = "CANCELLED"
        else:
            game_status = "PRE_GAME"
        source_url = str(game.get("source_url") or "")
        rows.append(
            CandidateInput(
                candidate_id=f"espn-{event_id}-schedule",
                event_id=event_id,
                event_name=event_name,
                sport=sport_l,
                league=_LEAGUE.get(sport_l, sport_l.upper()),
                start_time=start,
                home_team=home,
                away_team=away,
                market_type="schedule",
                market_period="full_game",
                selection=event_name,
                american_odds=0,
                estimated_probability=0.5,
                probability_source="model",
                variance=1.0,
                data_quality=0.0,
                reason_codes=["ESPN_SCHEDULE_ONLY", "NO_SPORTSBOOK_PRICE"],
                reasoning=[
                    "ESPN lists this game. Sportsbooks have not posted a price, "
                    "so this is not a play."
                ],
                data_source="ESPN_SCOREBOARD",
                source_urls=[source_url] if source_url else [],
                source_timestamp=now,
                missing_fields=["sportsbook price"],
                schedule_verified=True,
                home_away_verified=True,
                game_status=game_status,
                market_status="SUSPENDED",
                thesis_key="unpriced-schedule",
                script_key=f"espn-{event_id}"[:160],
            )
        )
    return rows


def _parse_start(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed
