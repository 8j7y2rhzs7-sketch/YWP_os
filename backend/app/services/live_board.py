"""Live scores and how today's plays are tracking.

Major-game scores come from ESPN and the MLB Stats API. Player stats come
from the same box scores settlement already trusts. This does not call The
Odds API, grade a result, or place anything. A live "cashing" read can still
change before the game ends.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import DayPrepPlay, Ticket, TicketLeg
from app.schemas import LiveBoardResponse, LiveGameOut, LivePlayOut
from app.services.day_prep import slate_date_for
from app.services.espn_provider import _name_overlap
from app.services.settlement import (
    _derive_espn_player_prop,
    _derive_outcome,
    _is_player_prop_market,
)

logger = logging.getLogger(__name__)

NOTICE = "Live stats, not a wager. A read can change before the game ends."
MAJOR_SPORTS = ("nba", "nfl", "nhl", "mlb", "ncaaf", "wnba")
_PACE_RANK = {
    "cashing": 0,
    "behind": 1,
    "waiting": 2,
    "watching": 3,
    "cashed": 4,
    "push": 5,
    "missed": 6,
}
_STATUS_RANK = {"LIVE": 0, "PRE": 1, "FINAL": 2, "OTHER": 3}


def _phase(row: dict[str, Any]) -> str:
    explicit = str(row.get("status") or "").upper()
    if explicit in {"LIVE", "PRE", "FINAL", "OTHER"}:
        return explicit
    state = str(row.get("game_state") or row.get("state") or "").lower()
    name = str(row.get("status") or "").lower()
    if state == "in" or "in_progress" in name or "in progress" in name:
        return "LIVE"
    if row.get("completed") or state == "post" or "final" in name:
        return "FINAL"
    if state == "pre" or "schedul" in name:
        return "PRE"
    return "OTHER"


def _score(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _detail(row: dict[str, Any], phase: str) -> str:
    text = str(row.get("detail") or "").strip()
    clock = str(row.get("clock") or "").strip()
    if text:
        return text
    if clock and phase == "LIVE":
        return clock
    if phase == "FINAL":
        return "Final"
    if phase == "PRE":
        return "Not started"
    return phase.title()


def _game(row: dict[str, Any], sport: str) -> LiveGameOut:
    phase = _phase(row)
    return LiveGameOut(
        sport=sport,
        event_id=str(row.get("event_id") or ""),
        away_team=str(row.get("away_team") or ""),
        home_team=str(row.get("home_team") or ""),
        away_score=_score(row.get("away_score")),
        home_score=_score(row.get("home_score")),
        status=phase,
        detail=_detail(row, phase)[:80],
        start_time=str(row.get("start_time") or "") or None,
    )


def _same_game(event_name: str, event_id: str, game: LiveGameOut) -> bool:
    if event_id and event_id == game.event_id:
        return True
    text = event_name or ""
    if not text:
        return False
    return _name_overlap(game.home_team, text) >= 2 and _name_overlap(game.away_team, text) >= 2


def _pace(outcome: str | None, phase: str) -> str:
    if phase == "PRE" or outcome is None:
        return "waiting" if phase == "PRE" else "watching"
    if phase == "FINAL":
        return {"WIN": "cashed", "LOSS": "missed", "PUSH": "push"}.get(outcome, "watching")
    if phase == "LIVE":
        return {"WIN": "cashing", "LOSS": "behind", "PUSH": "push"}.get(outcome, "watching")
    return "waiting"


def _namespace(
    *,
    selection: str,
    market: str,
    line: Any,
    sport: str,
    home: str,
    away: str,
) -> SimpleNamespace:
    number = None
    if line is not None and line != "":
        number = Decimal(str(line))
    return SimpleNamespace(
        selection=selection,
        market_type=market,
        line=number,
        sport=sport,
        player_key="",
        snapshot={"home_team": home, "away_team": away},
    )


def _team_box(game: LiveGameOut) -> dict[str, Any]:
    home = game.home_score or 0
    away = game.away_score or 0
    return {
        "home_team": game.home_team,
        "away_team": game.away_team,
        "home_runs": home,
        "away_runs": away,
        "total_runs": home + away,
        "final_score": f"{game.away_team} {away} @ {game.home_team} {home}",
        "pitchers": {},
        "batters": {},
    }


def _mlb_box_from_feed(feed: dict[str, Any] | None) -> dict[str, Any] | None:
    if not feed:
        return None
    game_data = feed.get("gameData") or {}
    live_data = feed.get("liveData") or {}
    teams = game_data.get("teams") or {}
    linescore = live_data.get("linescore") or {}
    line_teams = linescore.get("teams") or {}
    home_team = (teams.get("home") or {}).get("name") or ""
    away_team = (teams.get("away") or {}).get("name") or ""
    home_runs = int((line_teams.get("home") or {}).get("runs") or 0)
    away_runs = int((line_teams.get("away") or {}).get("runs") or 0)
    boxscore = (live_data.get("boxscore") or {}).get("teams") or {}
    pitchers: dict[int, dict[str, Any]] = {}
    batters: dict[int, dict[str, Any]] = {}
    for side in ("home", "away"):
        players = (boxscore.get(side) or {}).get("players") or {}
        for record in players.values():
            person = record.get("person") or {}
            pid = person.get("id")
            if not isinstance(pid, int):
                continue
            pitching = (record.get("stats") or {}).get("pitching") or {}
            if pitching:
                pitchers[pid] = {
                    "id": pid,
                    "name": person.get("fullName") or "",
                    "strikeouts": int(pitching.get("strikeOuts") or 0),
                    "outs": int(pitching.get("outs") or 0),
                    "hits_allowed": int(pitching.get("hits") or 0),
                    "earned_runs": int(pitching.get("earnedRuns") or 0),
                    "walks": int(pitching.get("baseOnBalls") or 0),
                }
            batting = (record.get("stats") or {}).get("batting") or {}
            if batting:
                hits = int(batting.get("hits") or 0)
                runs = int(batting.get("runs") or 0)
                rbi = int(batting.get("rbi") or 0)
                batters[pid] = {
                    "id": pid,
                    "name": person.get("fullName") or "",
                    "hits": hits,
                    "runs": runs,
                    "rbi": rbi,
                    "home_runs": int(batting.get("homeRuns") or 0),
                    "total_bases": int(batting.get("totalBases") or 0),
                    "hits_runs_rbis": hits + runs + rbi,
                    "stolen_bases": int(batting.get("stolenBases") or 0),
                    "walks": int(batting.get("baseOnBalls") or 0),
                }
    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_runs": home_runs,
        "away_runs": away_runs,
        "total_runs": home_runs + away_runs,
        "final_score": f"{away_team} {away_runs} @ {home_team} {home_runs}",
        "pitchers": pitchers,
        "batters": batters,
    }


def _read_play(
    play: LivePlayOut,
    game: LiveGameOut | None,
    *,
    players: list[dict[str, Any]] | None,
    mlb_box: dict[str, Any] | None,
) -> LivePlayOut:
    if game is None or game.status == "PRE":
        play.status = game.status if game else "PRE"
        play.detail = game.detail if game else "Waiting on the game"
        play.pace = "waiting"
        return play
    play.status = game.status
    score = f"{game.away_team} {game.away_score or 0}, {game.home_team} {game.home_score or 0}"
    rec = _namespace(
        selection=play.selection,
        market=play.market_type,
        line=play.line,
        sport=play.sport,
        home=game.home_team,
        away=game.away_team,
    )
    derived: dict[str, Any] | None = None
    if play.sport == "mlb" and _is_player_prop_market(play.market_type, play.selection):
        derived = _derive_outcome(rec, mlb_box or _team_box(game))
    elif _is_player_prop_market(play.market_type, play.selection):
        derived = _derive_espn_player_prop(
            rec,
            {"final_score": score},
            players or [],
        )
    else:
        derived = _derive_outcome(rec, _team_box(game))
    outcome = None if not derived else str(derived.get("outcome") or "")
    if outcome in {"", "VOID", "None"}:
        outcome = None
    play.pace = _pace(outcome, game.status)
    if derived and derived.get("actual_value") is not None:
        play.actual = float(derived["actual_value"])
    detail = str((derived or {}).get("detail") or "")
    play.detail = detail[:180] or f"{score} · {game.detail}"
    if play.actual is not None and play.line is not None:
        play.stat_label = f"{play.actual:g} / {play.line:g}"
    return play


def _your_plays(db: Session, user_id: str) -> list[LivePlayOut]:
    tickets = list(
        db.scalars(
            select(Ticket)
            .where(Ticket.user_id == user_id, Ticket.settled_at.is_(None))
            .options(selectinload(Ticket.legs).selectinload(TicketLeg.recommendation))
            .order_by(Ticket.updated_at.desc())
        ).all()
    )
    plays: list[LivePlayOut] = []
    seen: set[str] = set()
    for ticket in tickets:
        for leg in ticket.legs:
            rec = leg.recommendation
            if rec is None:
                continue
            key = f"{rec.sport}|{rec.event_id}|{rec.selection}"
            if key in seen:
                continue
            seen.add(key)
            plays.append(
                LivePlayOut(
                    id=leg.id,
                    source="yours",
                    sport=rec.sport,
                    selection=rec.selection,
                    market_type=rec.market_type,
                    line=float(rec.line) if rec.line is not None else None,
                    event_name=rec.event_name,
                    event_id=rec.event_id,
                    status="PRE",
                    detail="",
                    pace="waiting",
                )
            )
    return plays


def _board_plays(db: Session, slate_date) -> list[LivePlayOut]:
    rows = list(
        db.scalars(
            select(DayPrepPlay)
            .where(DayPrepPlay.slate_date == slate_date)
            .order_by(DayPrepPlay.rank)
        ).all()
    )
    plays: list[LivePlayOut] = []
    for row in rows:
        payload = row.payload if isinstance(row.payload, dict) else {}
        line = payload.get("line")
        plays.append(
            LivePlayOut(
                id=row.id,
                source="board",
                sport=row.sport,
                selection=row.selection,
                market_type=row.market_type,
                line=float(line) if line is not None else None,
                event_name=str(payload.get("event_name") or row.selection),
                event_id=row.event_id,
                status="PRE",
                detail="",
                pace="waiting",
            )
        )
    return plays


def _default_espn(sport: str, slate_date) -> list[dict[str, Any]]:
    from app.services.espn_provider import get_scoreboard

    return list(get_scoreboard(sport, slate_date) or [])


def _default_mlb(slate_date) -> list[dict[str, Any]]:
    from app.services.mlb_provider import get_day_board

    return list(get_day_board(slate_date) or [])


def _default_players(sport: str, event_id: str) -> list[dict[str, Any]]:
    from app.services.espn_provider import get_event_summary, parse_boxscore_player_stats

    summary = get_event_summary(sport, event_id)
    return parse_boxscore_player_stats(summary)


def _default_mlb_feed(event_id: str) -> dict[str, Any] | None:
    from app.services.mlb_provider import get_live_feed

    try:
        return get_live_feed(int(event_id))
    except (TypeError, ValueError):
        return None


def build_live_board(
    db: Session,
    user_id: str,
    *,
    now: datetime | None = None,
    espn_loader=None,
    mlb_loader=None,
    players_loader=None,
    mlb_feed_loader=None,
) -> LiveBoardResponse:
    """Read scores and open plays. Loaders exist so tests never hit the network."""
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    slate = slate_date_for(moment)
    espn_loader = espn_loader or _default_espn
    mlb_loader = mlb_loader or _default_mlb
    players_loader = players_loader or _default_players
    mlb_feed_loader = mlb_feed_loader or _default_mlb_feed

    games: list[LiveGameOut] = []
    for sport in MAJOR_SPORTS:
        try:
            rows = mlb_loader(slate) if sport == "mlb" else espn_loader(sport, slate)
        except Exception:
            logger.exception("live board score pull failed for %s", sport)
            rows = []
        for row in rows or []:
            games.append(_game(row, sport if sport != "mlb" else str(row.get("sport") or "mlb")))
    games.sort(key=lambda game: (_STATUS_RANK.get(game.status, 9), game.start_time or ""))
    games = games[:32]

    yours = _your_plays(db, user_id)
    seen = {f"{play.sport}|{play.event_id}|{play.selection}" for play in yours}
    board = [
        play
        for play in _board_plays(db, slate)
        if f"{play.sport}|{play.event_id}|{play.selection}" not in seen
    ]
    plays = (yours + board)[:24]

    player_cache: dict[str, list[dict[str, Any]]] = {}
    feed_cache: dict[str, dict[str, Any] | None] = {}
    tracked: list[LivePlayOut] = []
    for play in plays:
        game = next((row for row in games if _same_game(play.event_name, play.event_id, row)), None)
        players = None
        mlb_box = None
        needs_players = game is not None and game.status in {"LIVE", "FINAL"}
        if needs_players and _is_player_prop_market(play.market_type, play.selection):
            if play.sport == "mlb":
                if game.event_id not in feed_cache:
                    try:
                        feed_cache[game.event_id] = mlb_feed_loader(game.event_id)
                    except Exception:
                        logger.exception("mlb live feed failed")
                        feed_cache[game.event_id] = None
                mlb_box = _mlb_box_from_feed(feed_cache[game.event_id])
            else:
                cache_key = f"{play.sport}:{game.event_id}"
                if cache_key not in player_cache:
                    try:
                        loaded = players_loader(play.sport, game.event_id) or []
                        player_cache[cache_key] = list(loaded)
                    except Exception:
                        logger.exception("espn summary failed")
                        player_cache[cache_key] = []
                players = player_cache[cache_key]
        tracked.append(_read_play(play, game, players=players, mlb_box=mlb_box))
    tracked.sort(key=lambda play: _PACE_RANK.get(play.pace, 9))
    return LiveBoardResponse(
        slate_date=slate,
        notice=NOTICE,
        live_count=sum(1 for game in games if game.status == "LIVE"),
        games=games,
        plays=tracked,
    )
