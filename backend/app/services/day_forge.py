"""Day Forge — pick one hittable, non-juice play when the slate is cooked enough.

This is the Home-screen "left something in the oven" ritual: wait until research
and prices are ready, then surface a single cash-style PLAY (never -1400 juice,
never lottery longshots). Process language only — never claim a lock will hit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from app.core.config import settings
from app.schemas import CandidateInput, RecommendationOut
from app.services.readiness import candidate_readiness, slate_readiness

DayForgeStatus = Literal["cooking", "ready", "pass", "unavailable"]
DayForgePhase = Literal[
    "waiting_slate",
    "gathering_heat",
    "grading",
    "forging",
    "ready",
    "pass",
    "unavailable",
]

# Cash-oriented odds band: no heavy juice (-1400), no lottery tickets.
MIN_AMERICAN_ODDS = -200
MAX_AMERICAN_ODDS = 150
HARD_JUICE_FLOOR = -300  # absolute reject (covers -1400)

MIN_CONFIDENCE_PLAY = 85
MIN_CONFIDENCE_LEAN = 78
MIN_EDGE = 0.03
MAX_MISS_BY_ONE = 0.55
MAX_VARIANCE = 0.48
MIN_YWP_RATING = 6.5
MIN_DATA_QUALITY = 0.65
MIN_COOK_CANDIDATES = 3
MAX_FORGE_CANDIDATES = 48

BLOCKING_REASON_CODES = {
    "NO_CLEAN_EDGE",
    "ODDS_TOO_EXPENSIVE",
    "RESEARCH_INCOMPLETE",
    "NO_INDEPENDENT_PROBABILITY",
    "MODEL_EDGE_QUARANTINE",
    "FILLER_LEG_TAX",
    "MISS_BY_ONE_GATE_FAILED",
    "DATA_QUALITY_BAD",
}


@dataclass(slots=True)
class DayForgeSelection:
    status: DayForgeStatus
    phase: DayForgePhase
    progress: float
    message: str
    cook_reasons: list[str]
    pass_reason: str | None = None
    forgeable_count: int = 0
    graded_count: int = 0


def _odds_in_band(american_odds: int) -> bool:
    if american_odds <= HARD_JUICE_FLOOR:
        return False
    return MIN_AMERICAN_ODDS <= american_odds <= MAX_AMERICAN_ODDS


def _allowed_probability_sources() -> set[str]:
    allowed = {"model", "manual_verified"}
    if settings.demo_mode:
        allowed.add("demo")
    return allowed


def candidate_is_forge_fuel(candidate: CandidateInput) -> bool:
    """Cheap pre-filter before we spend engine cycles."""
    if candidate.game_status != "PRE_GAME":
        return False
    if candidate.market_status != "OPEN":
        return False
    if not _odds_in_band(int(candidate.american_odds)):
        return False
    if float(candidate.data_quality) < MIN_DATA_QUALITY:
        return False
    if float(candidate.variance) > MAX_VARIANCE:
        return False
    if candidate.probability_source not in _allowed_probability_sources():
        return False
    if candidate_readiness(candidate) == "PARTIAL" and not settings.demo_mode:
        return False
    return True


def cook_progress_from_slate(candidates: list[CandidateInput]) -> DayForgeSelection:
    readiness = slate_readiness(candidates)
    if not candidates:
        return DayForgeSelection(
            status="unavailable",
            phase="unavailable",
            progress=0.08,
            message="No slate heat yet — waiting on today's priced board.",
            cook_reasons=["empty_slate"],
        )

    forgeable = [c for c in candidates if candidate_is_forge_fuel(c)]
    priced = sum(1 for c in candidates if int(c.american_odds) != 0)
    modelish = sum(
        1 for c in candidates if c.probability_source in _allowed_probability_sources()
    )
    verified = sum(1 for c in candidates if candidate_readiness(c) == "VERIFIED")

    # Progress blends board coverage + forge fuel.
    coverage = min(1.0, priced / max(6, len(candidates) * 0.35))
    fuel = min(1.0, len(forgeable) / float(MIN_COOK_CANDIDATES))
    research = min(1.0, verified / max(1.0, len(candidates) * 0.25))
    progress = round(0.18 + 0.32 * coverage + 0.30 * fuel + 0.20 * research, 3)
    progress = max(0.12, min(0.92, progress))

    reasons: list[str] = []
    if readiness == "PARTIAL":
        reasons.append("research_still_partial")
    if len(forgeable) < MIN_COOK_CANDIDATES:
        reasons.append(f"need_{MIN_COOK_CANDIDATES}_cash_band_candidates")
    if modelish == 0:
        reasons.append("waiting_independent_probability")
    if priced == 0:
        reasons.append("waiting_book_prices")

    ready_to_grade = len(forgeable) >= MIN_COOK_CANDIDATES or (
        readiness == "VERIFIED" and len(forgeable) >= 1
    ) or (settings.demo_mode and len(forgeable) >= 1)

    if not ready_to_grade:
        return DayForgeSelection(
            status="cooking",
            phase="gathering_heat",
            progress=progress,
            message="Day Forge is cooking — gathering verified edges in the cash band.",
            cook_reasons=reasons or ["warming"],
            forgeable_count=len(forgeable),
        )

    return DayForgeSelection(
        status="cooking",
        phase="grading",
        progress=max(progress, 0.78),
        message="Heat locked. Grading forge candidates…",
        cook_reasons=["grading"],
        forgeable_count=len(forgeable),
    )


def _rec_snapshot(rec: Any) -> dict[str, Any]:
    snap = getattr(rec, "snapshot", None)
    return snap if isinstance(snap, dict) else {}


def recommendation_is_day_forge_eligible(rec: Any, *, allow_lean: bool = False) -> bool:
    decision = str(getattr(rec, "decision", "") or "")
    allowed_decisions = {"PLAY"} if not allow_lean else {"PLAY", "LEAN"}
    if decision not in allowed_decisions:
        return False

    odds = int(getattr(rec, "american_odds", 0) or 0)
    if not _odds_in_band(odds):
        return False

    snap = _rec_snapshot(rec)
    source = str(snap.get("probability_source") or "")
    if source and source not in _allowed_probability_sources():
        return False
    if not source and not settings.demo_mode:
        # Prefer known independent sources; allow unknown only in demo.
        pass

    confidence = int(getattr(rec, "confidence_score", 0) or 0)
    min_conf = MIN_CONFIDENCE_PLAY if decision == "PLAY" else MIN_CONFIDENCE_LEAN
    if confidence < min_conf:
        return False

    edge = float(getattr(rec, "edge", 0) or 0)
    if edge < MIN_EDGE:
        return False

    miss = float(getattr(rec, "miss_by_one_risk", 1) or 1)
    if miss >= MAX_MISS_BY_ONE:
        return False

    variance = float(getattr(rec, "variance", 1) or 1)
    if variance > MAX_VARIANCE:
        return False

    ywp = float(getattr(rec, "ywp_rating", 0) or 0)
    if ywp < MIN_YWP_RATING:
        return False

    risk = str(getattr(rec, "risk", "") or "").lower()
    if risk == "high":
        return False

    reasons = set(getattr(rec, "reason_codes", None) or [])
    if reasons & BLOCKING_REASON_CODES:
        return False

    game_status = str(snap.get("game_status") or "PRE_GAME")
    market_status = str(snap.get("market_status") or "OPEN")
    if game_status not in {"PRE_GAME", ""}:
        return False
    if market_status not in {"OPEN", ""}:
        return False

    return True


def _sort_key(rec: Any) -> tuple:
    decision = str(getattr(rec, "decision", "") or "")
    tier = str(getattr(rec, "recommendation_tier", "") or "")
    cash = 0 if tier in {"cash_builder", "no_stress"} else 1
    play_rank = 0 if decision == "PLAY" else 1
    confidence = -int(getattr(rec, "confidence_score", 0) or 0)
    miss = float(getattr(rec, "miss_by_one_risk", 1) or 1)
    vision = -float(getattr(rec, "vision_score", 0) or 0)
    # Prefer nearer -110 than deep favorites inside the band.
    odds = int(getattr(rec, "american_odds", 0) or 0)
    juice_distance = abs(odds + 110)
    rank = int(getattr(rec, "rank", 999) or 999)
    return (play_rank, cash, confidence, miss, vision, juice_distance, rank)


def select_day_forge_play(records: list[Any]) -> Any | None:
    """Pick the best eligible PLAY, then soft-fallback to LEAN."""
    plays = [r for r in records if recommendation_is_day_forge_eligible(r, allow_lean=False)]
    if plays:
        return sorted(plays, key=_sort_key)[0]
    leans = [r for r in records if recommendation_is_day_forge_eligible(r, allow_lean=True)]
    if leans:
        return sorted(leans, key=_sort_key)[0]
    return None


def trim_forge_candidates(candidates: list[CandidateInput]) -> list[CandidateInput]:
    fuel = [c for c in candidates if candidate_is_forge_fuel(c)]
    fuel.sort(
        key=lambda c: (
            -float(c.data_quality),
            abs(int(c.american_odds) + 110),
            -float(c.estimated_probability),
        )
    )
    return fuel[:MAX_FORGE_CANDIDATES]


def resolve_day_forge_sport(
    catalog: list[dict[str, Any]],
    requested: str | None = None,
) -> str:
    if requested:
        return requested.lower()
    rows = [row for row in catalog if row.get("in_season") is True]
    ids = [str(row.get("id") or row.get("sport") or "").lower() for row in rows]
    if "mlb" in ids:
        return "mlb"
    if ids:
        return ids[0]
    return "mlb"


def day_forge_play_payload(play: RecommendationOut | None) -> dict[str, Any] | None:
    if play is None:
        return None
    return play.model_dump(mode="json")
