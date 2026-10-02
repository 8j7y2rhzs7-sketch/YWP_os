"""Map a Kalshi contract onto the sports verdict ladder.

The contract price is the market. It is never copied into the model
probability. A sportsbook-versus-Kalshi gap is stored as PRICE_GAP and cannot
create a PLAY by itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.markets.adapter import Instrument

INDEPENDENT_SOURCES = frozenset({"model", "manual_verified"})


@dataclass(frozen=True)
class SportsModelQuote:
    model_probability: float
    sportsbook_implied: float | None
    source: str
    recommendation_id: str | None = None


def classify_contract(instrument: Instrument) -> str:
    ticker = instrument.instrument_id.upper()
    blob = f"{instrument.title} {instrument.rules_text}".lower()
    if "spread" in blob or "SPREAD" in ticker:
        return "spread"
    if "total" in blob or "TOTAL" in ticker:
        return "total"
    if "GAME" in ticker or "winner" in blob or "moneyline" in blob:
        return "moneyline"
    return "unknown"


def team_name(instrument: Instrument) -> str:
    extra = instrument.extra or {}
    subtitle = extra.get("yes_sub_title")
    if isinstance(subtitle, str) and subtitle.strip():
        return subtitle.strip()
    return instrument.title.strip()


def select_independent_probability(candidates: list[SportsModelQuote]) -> SportsModelQuote | None:
    """Use a stored sports-model probability. Skip anything that came from a price."""
    for candidate in candidates:
        if candidate.source in INDEPENDENT_SOURCES:
            return candidate
    return None


def price_gap_signal(
    sportsbook_implied: float | None,
    kalshi_fair: float | None,
) -> dict[str, float | str] | None:
    if sportsbook_implied is None or kalshi_fair is None:
        return None
    gap = float(sportsbook_implied) - float(kalshi_fair)
    return {
        "code": "PRICE_GAP",
        "sportsbook_implied": round(float(sportsbook_implied), 6),
        "kalshi_fair": round(float(kalshi_fair), 6),
        "gap": round(gap, 6),
        "note": (
            "Sportsbook price versus Kalshi price. Logged only. "
            "A price gap cannot create a PLAY by itself."
        ),
    }


def price_gap_cannot_authorize_play(decision: str, *, has_independent_model: bool) -> str:
    """A market disagreement is not an independent probability."""
    if not has_independent_model and decision in {"PLAY", "LEAN"}:
        return "SKIP"
    return decision


def rules_need_review(instrument: Instrument, contract_type: str) -> str | None:
    rules = (instrument.rules_text or "").lower()
    if contract_type == "unknown":
        return "Contract rules do not clearly match a game-winner question."
    if contract_type == "moneyline" and "regulation only" in rules:
        return "Contract settles on regulation time, which may not match the full-game model."
    if "does not include overtime" in rules and contract_type == "moneyline":
        return "Contract excludes overtime, so it may not match the full-game model."
    return None
