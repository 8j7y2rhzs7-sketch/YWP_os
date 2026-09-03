from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import AuditLog, BankrollAccount, BankrollTransaction, User

DEMO_EMAIL = "demo@ywp-os.com"
DEMO_PASSWORD = "YwpDemo!2026"


def seed() -> None:
    if not settings.demo_mode:
        print("YWP_DEMO_MODE is false; no demo records were created.")
        return
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user:
            print(f"Demo user already exists: {DEMO_EMAIL}")
            return
        user = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            name="GHOSTT YWP",
            timezone="America/New_York",
            risk_profile="balanced",
            role="admin",
        )
        db.add(user)
        db.flush()
        bankroll = BankrollAccount(
            user_id=user.id,
            balance=Decimal("1000.00"),
            max_stake_pct=Decimal("0.0200"),
            max_daily_exposure_pct=Decimal("0.1000"),
            max_thesis_exposure_pct=Decimal("0.0300"),
        )
        db.add(bankroll)
        db.flush()
        db.add(
            BankrollTransaction(
                bankroll_id=bankroll.id,
                transaction_type="deposit",
                amount=Decimal("1000.00"),
                balance_after=Decimal("1000.00"),
                note="Synthetic demo bankroll",
            )
        )
        db.add(
            AuditLog(
                user_id=user.id,
                action="DEMO_ACCOUNT_SEEDED",
                entity_type="user",
                entity_id=user.id,
            )
        )
        db.commit()
        print(f"Created demo user: {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    seed()
