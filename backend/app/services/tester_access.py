"""Provision tester accounts with active subscription (bypass Whop charge)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import AuditLog, BankrollAccount, User


def upsert_tester(
    db: Session,
    *,
    email: str,
    password: str,
    name: str,
    timezone: str = "America/New_York",
) -> tuple[User, bool]:
    email = email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    created = False
    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(password),
            name=name.strip() or "YWP Tester",
            timezone=timezone or "America/New_York",
            risk_profile="balanced",
            role="user",
            subscription_status="active",
        )
        db.add(user)
        db.flush()
        db.add(BankrollAccount(user_id=user.id))
        created = True
    else:
        user.password_hash = hash_password(password)
        user.subscription_status = "active"
        user.is_active = True
        if name.strip():
            user.name = name.strip()
        if timezone:
            user.timezone = timezone
    db.add(
        AuditLog(
            user_id=user.id,
            action="TESTER_PROVISIONED",
            entity_type="user",
            entity_id=user.id,
            details={"created": created, "subscription_status": "active"},
        )
    )
    return user, created
