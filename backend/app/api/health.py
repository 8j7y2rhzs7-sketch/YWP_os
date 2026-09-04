from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.deps import DB
from app.services.espn_provider import probe_espn_api
from app.services.mlb_provider import probe_mlb_api
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
    ESPN is probed per sport — one league 403 does not imply all ESPN sports are down.
    """
    mlb = probe_mlb_api()
    odds = probe_odds_api()
    espn_by_sport = {
        sport: probe_espn_api(sport) for sport in ("mlb", "nba", "nfl", "soccer")
    }
    espn_any_ok = any(item.get("status") == "connected" for item in espn_by_sport.values())
    mlb_ok = bool(mlb.get("ok"))
    odds_ok = bool(odds.get("ok"))
    return {
        "status": "ok" if mlb_ok and odds_ok and espn_any_ok else "degraded",
        "version": settings.app_version,
        "demo_mode": settings.demo_mode,
        "mlb": mlb,
        "espn": espn_by_sport,
        "odds": odds,
        "coverage_note": (
            "Selectable sports are not fully supported merely because prices load. "
            "Check per-sport ESPN status and research readiness on each slate."
        ),
    }
