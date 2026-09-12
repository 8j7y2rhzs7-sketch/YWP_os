from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.deps import DB
from app.services.cfbd_provider import cfbd_configured, probe_cfbd_api
from app.services.espn_provider import probe_espn_api
from app.services.mlb_provider import probe_mlb_api
from app.services.nhl_provider import probe_nhl_api
from app.services.odds_provider import odds_api_configured, get_last_fetch_status, probe_odds_api
from app.services.ncaa_provider import probe_ncaa_api

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DB) -> dict[str, str | bool | None]:
    db.execute(text("SELECT 1"))
    odds_remaining = get_last_fetch_status().get("remaining")
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "protocol_version": settings.protocol_version,
        "demo_mode": settings.demo_mode,
        "odds_api_configured": odds_api_configured(),
        "odds_requests_remaining": odds_remaining,
        "database": "ok",
    }


@router.get("/health/providers")
def health_providers() -> dict[str, object]:
    """
    Probe external providers. Safe for public checks: never returns secret values.
    Odds is the non-MLB slate backbone; fact sources are probed separately and may
    degrade without hiding priced plays.
    """
    mlb = probe_mlb_api()
    odds = probe_odds_api()
    nhl = probe_nhl_api()
    espn_by_sport = {
        sport: probe_espn_api(sport) for sport in ("nba", "nfl", "soccer", "wnba", "ncaaf")
    }
    cfbd = probe_cfbd_api()
    ncaa = probe_ncaa_api(week=3)
    mlb_ok = bool(mlb.get("ok"))
    odds_ok = bool(odds.get("ok"))
    return {
        "status": "ok" if mlb_ok and odds_ok else "degraded",
        "version": settings.app_version,
        "demo_mode": settings.demo_mode,
        "mlb": mlb,
        "nhl": nhl,
        "espn": espn_by_sport,
        "cfbd": {
            "configured": cfbd_configured(),
            **cfbd,
        },
        "ncaa": ncaa,
        "kbo": {
            "status": "odds_backed",
            "detail": "ESPN has no baseball/kbo path; KBO facts use The Odds API scores + Open-Meteo.",
        },
        "odds": odds,
        "coverage_note": (
            "Odds health uses the free /v4/sports catalog (0 credits). "
            "ESPN facts use site.web.api.espn.com (site.api is often Akamai-blocked from cloud IPs). "
            "NCAAF facts: ESPN primary, CFBD secondary (CFBD_API_KEY), NCAA scoreboard tertiary, "
            "Open-Meteo + NWS weather. "
            "KBO uses Odds scores (not ESPN). "
            "Non-MLB slates still show Odds-priced plays if a fact feed degrades. "
            "Out-of-season sports are gated before paid /odds calls. "
            "Empty dates mean no Odds events that day — try a nearby date from the slate notice."
        ),
    }
