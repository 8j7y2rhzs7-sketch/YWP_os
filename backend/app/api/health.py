from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.deps import DB

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
        "database": "ok",
    }
