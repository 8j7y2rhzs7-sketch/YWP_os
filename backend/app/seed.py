from __future__ import annotations

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.demo_account import (
    DEMO_EMAIL,
    DEMO_PASSWORD,
    ensure_local_demo_user,
    prepare_production_identities,
)

__all__ = ["DEMO_EMAIL", "DEMO_PASSWORD", "seed"]


def seed() -> None:
    """Local demo login when YWP_DEMO_MODE is true; otherwise adopt or lock it."""
    with SessionLocal() as db:
        if not settings.demo_mode:
            outcome = prepare_production_identities(db)
            print(f"YWP_DEMO_MODE is false; owner adoption result: {outcome}")
            return
        user = ensure_local_demo_user(db)
        db.commit()
        print(f"Local-dev demo user ready (role={user.role}): {DEMO_EMAIL}")


if __name__ == "__main__":
    seed()
