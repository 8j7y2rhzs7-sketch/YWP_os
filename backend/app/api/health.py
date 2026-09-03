from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.deps import DB
from app.services.odds_provider import odds_api_configured, probe_odds_api

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DB) -> dict[str, str | bool]:
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "protocol_version": settings.protocol_version,
        "demo_mode": settings.demo_mode,
        "odds_api_configured": odds_api_configured(),
        "database": "ok",
    }


@router.get("/health/providers")
def health_providers() -> dict[str, object]:
    """
    Probe external providers. Safe for public checks: never returns secret values.
    Uses one Odds API request when a key is configured.
    """
    odds = probe_odds_api()
    return {
        "status": "ok" if odds.get("ok") else "degraded",
        "version": settings.app_version,
        "demo_mode": settings.demo_mode,
        "odds": odds,
    }
