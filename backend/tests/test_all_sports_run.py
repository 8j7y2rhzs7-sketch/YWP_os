"""ALL SPORTS run, soccer date calendars, and mega-board grade caps."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.api.sports import _grade_slice
from app.schemas import CandidateInput, PropWarmRequest, SportsAnalyzeRequest
from app.services.live_generic_slate import (
    ALL_SLATE_SPORTS,
    event_matches_slate_date,
    live_all_slate,
)
from app.services.odds_provider import (
    SOCCER_MAX_LEAGUES_PER_FETCH,
    canonical_app_sport,
    sport_public_label,
)


def test_canonical_all_aliases() -> None:
    assert canonical_app_sport("all") == "all"
    assert canonical_app_sport("multi") == "all"
    assert canonical_app_sport("mixed") == "all"
    assert sport_public_label("all") == "ALL SPORTS"


def test_soccer_event_matches_london_calendar() -> None:
    start = datetime(2026, 11, 14, 19, 0, tzinfo=ZoneInfo("Europe/London")).astimezone(UTC)
    assert event_matches_slate_date(start, date(2026, 11, 14), sport="soccer")
    # Early Asia kickoff: Monday Tokyo morning is still Sunday UTC — must keep the
    # Tokyo slate date so Hard Rock Asia boards are not dropped.
    asia = datetime(2026, 11, 16, 1, 0, tzinfo=ZoneInfo("Asia/Tokyo")).astimezone(UTC)
    assert asia.astimezone(UTC).date() == date(2026, 11, 15)
    assert event_matches_slate_date(asia, date(2026, 11, 16), sport="soccer")
    assert not event_matches_slate_date(asia, date(2026, 11, 16), sport="nba")


def test_soccer_league_cap_widened() -> None:
    assert SOCCER_MAX_LEAGUES_PER_FETCH >= 24


def _candidate(sport: str, candidate_id: str, *, prop: bool = False) -> CandidateInput:
    return CandidateInput(
        candidate_id=candidate_id,
        event_id=f"evt-{candidate_id}",
        event_name="Away @ Home",
        sport=sport,
        league=sport.upper(),
        market_type="player_points_over" if prop else "moneyline",
        market_period="full_game",
        selection="Home ML" if not prop else "Player Over 20.5",
        american_odds=-110,
        estimated_probability=0.55,
        start_time=datetime(2026, 11, 14, 20, 0, tzinfo=UTC),
        home_team="Home",
        away_team="Away",
        data_source="THE_ODDS_API",
        source_timestamp=datetime(2026, 11, 14, 12, 0, tzinfo=UTC),
        probability_source="market_implied" if prop else "model",
        thesis_key=f"thesis-{candidate_id}",
        script_key=f"script-{candidate_id}",
        reason_codes=["MATCHUP_EDGE"],
        reasoning=["unit test"],
        variance=0.2,
        data_quality=0.8,
    )


def test_analyze_allows_mixed_sports_for_all() -> None:
    payload = SportsAnalyzeRequest(
        sport="all",
        date=date(2026, 11, 14),
        candidates=[
            _candidate("nba", "nba-1"),
            _candidate("soccer", "soccer-1"),
            _candidate("nfl", "nfl-1"),
        ],
    )
    assert payload.sport == "all"
    assert len(payload.candidates) == 3


def test_analyze_rejects_mismatched_single_sport() -> None:
    with pytest.raises(ValidationError):
        SportsAnalyzeRequest(
            sport="nba",
            date=date(2026, 11, 14),
            candidates=[_candidate("nba", "nba-1"), _candidate("nfl", "nfl-1")],
        )


def test_warm_allows_mixed_sports_for_all() -> None:
    payload = PropWarmRequest(
        sport="all",
        date=date(2026, 11, 14),
        candidates=[_candidate("nba", "nba-p1", prop=True), _candidate("nfl", "nfl-p1", prop=True)],
    )
    assert payload.sport == "all"


def test_grade_slice_caps_mega_board() -> None:
    board = [_candidate("nba", f"ml-{i}") for i in range(3000)]
    board.extend(
        [
            _candidate("nba", f"prop-{i}", prop=True).model_copy(
                update={"probability_source": "model"}
            )
            for i in range(600)
        ]
    )
    graded, deferred = _grade_slice(board)
    assert len(graded) <= 1600
    assert deferred >= 2000
    assert all(
        not (str(c.market_type).startswith("player_") and c.probability_source == "market_implied")
        for c in graded
    )


def test_all_slate_sports_cover_run_grid() -> None:
    assert "soccer" in ALL_SLATE_SPORTS
    assert "tennis" in ALL_SLATE_SPORTS
    assert "ncaab" in ALL_SLATE_SPORTS


def test_live_all_slate_merges_in_season(monkeypatch) -> None:
    from app.services import live_generic_slate as mod

    def fake_in_season(sport: str, *, force_refresh: bool = False) -> bool | None:
        return sport in {"nba", "soccer"}

    def fake_generic(sport: str, slate_date: date):
        return [_candidate(sport, f"{sport}-a")]

    monkeypatch.setattr(
        "app.services.odds_provider.app_sport_in_season",
        fake_in_season,
    )
    monkeypatch.setattr(mod, "live_generic_slate", fake_generic)
    monkeypatch.setattr(
        "app.services.live_mlb_slate.live_mlb_slate",
        lambda _d: [],
    )
    monkeypatch.setattr(
        "app.services.live_wnba_slate.live_wnba_slate",
        lambda _d: [],
    )
    # live_all_slate calls live_generic_slate for non-mlb/wnba — but also
    # imports app_sport_in_season inside the function.
    out = live_all_slate(date(2026, 11, 14))
    sports = {c.sport for c in out}
    assert sports == {"nba", "soccer"}
    assert len(out) == 2
