"""Just-tipped games stay board-eligible during the early-live grace window."""

from datetime import UTC, datetime, timedelta

from app.core import config
from app.services import ticket_gates as gates


def test_event_market_status_pre_game_before_tip(monkeypatch) -> None:
    monkeypatch.setattr(config.settings, "early_live_grace_seconds", 45 * 60)
    start = datetime(2026, 11, 22, 18, 0, tzinfo=UTC)
    now = start - timedelta(minutes=5)
    assert gates.event_market_status(start, now) == ("PRE_GAME", "OPEN")


def test_event_market_status_early_live_stays_open(monkeypatch) -> None:
    monkeypatch.setattr(config.settings, "early_live_grace_seconds", 45 * 60)
    start = datetime(2026, 11, 22, 18, 0, tzinfo=UTC)
    now = start + timedelta(minutes=12)
    assert gates.event_market_status(start, now) == ("LIVE", "OPEN")
    assert gates.board_game_eligible("LIVE", "OPEN") is True
    assert gates.game_status_ok("LIVE") is True
    assert gates.market_status_ok("OPEN") is True


def test_event_market_status_closes_after_grace(monkeypatch) -> None:
    monkeypatch.setattr(config.settings, "early_live_grace_seconds", 45 * 60)
    start = datetime(2026, 11, 22, 18, 0, tzinfo=UTC)
    now = start + timedelta(minutes=50)
    assert gates.event_market_status(start, now) == ("LIVE", "CLOSED")
    assert gates.board_game_eligible("LIVE", "CLOSED") is False


def test_zero_grace_closes_immediately(monkeypatch) -> None:
    monkeypatch.setattr(config.settings, "early_live_grace_seconds", 0)
    start = datetime(2026, 11, 22, 18, 0, tzinfo=UTC)
    now = start + timedelta(seconds=1)
    assert gates.event_market_status(start, now) == ("LIVE", "CLOSED")
