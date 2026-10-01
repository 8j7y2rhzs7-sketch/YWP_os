"""Read-only markets API.

GET routes use the same subscription check as the sports board.
POST /scan and POST /grade are admin-only, or the scheduler secret header.
"""

from __future__ import annotations

import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select

from app.core.config import settings
from app.deps import DB, SubscribedUser, bearer
from app.models_markets import MarketCall, MarketJobRun, MarketOutcome
from app.services.demo_account import is_admin_principal
from app.services.markets.performance import track_record
from app.services.markets.scheduler_jobs import run_grade, run_scan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/markets", tags=["markets"])


def _token_ok(provided: str | None) -> bool:
    expected = settings.markets_scan_token or ""
    token = provided or ""
    if not expected or not token or len(expected) != len(token):
        return False
    return hmac.compare_digest(token, expected)


def _operator(
    request: Request,
    db: DB,
    credentials: HTTPAuthorizationCredentials | None,
    scan_token: str | None,
) -> str:
    if _token_ok(scan_token):
        return "scheduler"
    from app.deps import get_current_user

    user = get_current_user(request, db, credentials)
    if not is_admin_principal(user):
        raise HTTPException(status_code=403, detail="Admin role required")
    return "admin"


def _venue_group(value: str) -> str:
    text = value.strip().lower().replace("-", "_")
    if text in {"exchange", "kalshi", "sports", "sports_exchange"}:
        return "sports_exchange"
    if text == "crypto":
        return "crypto"
    raise HTTPException(status_code=400, detail="venue must be crypto or sports_exchange")


def _iso(value: object) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _outcome_for(db: DB, call_id: str) -> MarketOutcome | None:
    return db.scalar(select(MarketOutcome).where(MarketOutcome.call_id == call_id))


def serialize_call(call: MarketCall, outcome: MarketOutcome | None) -> dict[str, object]:
    return {
        "id": call.id,
        "venue": call.venue,
        "venue_group": call.venue_group,
        "instrument_id": call.instrument_id,
        "call_type": call.call_type,
        "title": call.title,
        "selection": call.selection,
        "entry": call.entry,
        "target": call.target,
        "stop": call.stop,
        "horizon_hours": call.horizon_hours,
        "horizon_end": _iso(call.horizon_end),
        "market_price": call.market_price,
        "fair_price": call.fair_price,
        "model_probability": call.model_probability,
        "lower_90": call.lower_90,
        "edge": call.edge,
        "expected_value": call.expected_value,
        "confidence": call.confidence,
        "verdict": call.verdict,
        "tier": call.tier,
        "edge_class": call.edge_class,
        "stake_pct": call.stake_pct,
        "reason_codes": call.reason_codes or [],
        "reasons": call.reasons or [],
        "warnings": call.warnings or [],
        "price_gap": call.price_gap,
        "model_version": call.model_version,
        "read_only": True,
        "created_at": _iso(call.created_at),
        "outcome": None if outcome is None else outcome.outcome,
        "realized_return": None if outcome is None else outcome.realized_return,
        "brier": None if outcome is None else outcome.brier,
        "grading_method": None if outcome is None else outcome.grading_method,
    }


@router.get("/health")
def markets_health(_: SubscribedUser, db: DB) -> dict[str, object]:
    last = db.scalar(select(MarketJobRun).order_by(MarketJobRun.started_at.desc()))
    venues = [
        {
            "venue": "coinbase",
            "kind": "crypto_spot",
            "enabled": settings.markets_enabled and settings.markets_coinbase_enabled,
            "role": "primary crypto prices",
        },
        {
            "venue": "kraken",
            "kind": "crypto_spot",
            "enabled": settings.markets_enabled and settings.markets_kraken_enabled,
            "role": "price cross-check",
        },
        {
            "venue": "kalshi",
            "kind": "event_contract",
            "enabled": settings.markets_enabled and settings.markets_kalshi_enabled,
            "role": "sports exchange prices",
        },
    ]
    return {
        "status": "ok" if settings.markets_enabled else "disabled",
        "read_only": True,
        "version": settings.app_version,
        "enabled": settings.markets_enabled,
        "venues": venues,
        "orders_enabled": False,
        "last_job": None
        if last is None
        else {
            "id": last.id,
            "job_name": last.job_name,
            "status": last.status,
            "items_processed": last.items_processed,
            "error_count": last.error_count,
            "started_at": _iso(last.started_at),
            "finished_at": _iso(last.finished_at),
        },
    }


@router.get("/calls")
def list_calls(
    _: SubscribedUser,
    db: DB,
    venue: str = Query(default="crypto"),
    limit: int = Query(default=40, ge=1, le=100),
) -> dict[str, object]:
    group = _venue_group(venue)
    rows = db.scalars(
        select(MarketCall)
        .where(MarketCall.venue_group == group)
        .order_by(MarketCall.created_at.desc())
        .limit(limit)
    ).all()
    return {
        "venue_group": group,
        "read_only": True,
        "calls": [serialize_call(row, _outcome_for(db, row.id)) for row in rows],
    }


@router.get("/calls/{call_id}")
def call_detail(_: SubscribedUser, db: DB, call_id: str) -> dict[str, object]:
    call = db.get(MarketCall, call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Market call not found")
    payload = serialize_call(call, _outcome_for(db, call.id))
    payload["payload"] = call.payload or {}
    return payload


@router.get("/performance")
def performance(
    _: SubscribedUser,
    db: DB,
    venue: str = Query(default="crypto"),
) -> dict[str, object]:
    return track_record(db, _venue_group(venue))


@router.post("/scan")
def scan(
    request: Request,
    db: DB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    x_ywp_markets_token: str | None = Header(default=None),
) -> dict[str, object]:
    actor = _operator(request, db, credentials, x_ywp_markets_token)
    logger.info("markets scan requested by %s", actor)
    return run_scan(db)


@router.post("/grade")
def grade(
    request: Request,
    db: DB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    x_ywp_markets_token: str | None = Header(default=None),
) -> dict[str, object]:
    actor = _operator(request, db, credentials, x_ywp_markets_token)
    logger.info("markets grade requested by %s", actor)
    return run_grade(db)
