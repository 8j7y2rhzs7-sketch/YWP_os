from __future__ import annotations

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.demo_account import (
    DEMO_EMAIL,
    DEMO_PASSWORD,
    ensure_local_demo_user,
    neutralize_demo_account,
)

__all__ = ["DEMO_EMAIL", "DEMO_PASSWORD", "seed"]


def seed() -> None:
    """Local demo login when YWP_DEMO_MODE is true; otherwise lock that account."""
    with SessionLocal() as db:
        if not settings.demo_mode:
            changed = neutralize_demo_account(db)
            db.commit()
            if changed:
                print("YWP_DEMO_MODE is false; demo account deactivated (not an admin).")
            else:
                print("YWP_DEMO_MODE is false; demo account is not active.")
            return
        user = ensure_local_demo_user(db)
        db.commit()
        print(f"Local-dev demo user ready (role={user.role}): {DEMO_EMAIL}")


if __name__ == "__main__":
    seed()
