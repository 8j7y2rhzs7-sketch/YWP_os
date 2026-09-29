"""Public demo login is local-dev only and is never an admin principal.

The password is in the repository README. Production (`YWP_DEMO_MODE=false`)
must refuse it, including tokens that were issued before the lock.
"""

from __future__ import annotations

import secrets
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, utcnow, verify_password
from app.models import AuditLog, BankrollAccount, BankrollTransaction, RefreshSession, User

DEMO_EMAIL = "demo@ywp-os.com"
DEMO_PASSWORD = "YwpDemo!2026"


def is_demo_email(email: str | None) -> bool:
    return (email or "").strip().lower() == DEMO_EMAIL


def demo_authentication_blocked(email: str | None) -> bool:
    """True when this identity must not receive or use a session."""
    return is_demo_email(email) and not settings.demo_mode


def is_admin_principal(user: object) -> bool:
    """Demo identities are never operators, even if a row still says admin."""
    if is_demo_email(getattr(user, "email", None)):
        return False
    return str(getattr(user, "role", "") or "").lower() == "admin"


def _password_is_public(user: User) -> bool:
    try:
        return verify_password(DEMO_PASSWORD, user.password_hash)
    except Exception:
        return False


def neutralize_demo_account(db: Session) -> bool:
    """Deactivate the published demo user without deleting unrelated rows.

    Returns True when a change was written. Bankroll, tickets, and other users
    stay in place. Refresh sessions for the demo user are revoked and the
    published password stops matching.
    """
    user = db.scalar(select(User).where(func.lower(User.email) == DEMO_EMAIL))
    if user is None:
        return False
    open_sessions = list(
        db.scalars(
            select(RefreshSession).where(
                RefreshSession.user_id == user.id,
                RefreshSession.revoked_at.is_(None),
            )
        ).all()
    )
    public_password = _password_is_public(user)
    needs_lock = (
        user.role != "user"
        or user.is_active
        or user.subscription_status == "active"
        or user.subscription_granted_at is not None
        or public_password
        or bool(open_sessions)
    )
    if not needs_lock:
        return False
    user.role = "user"
    user.is_active = False
    user.subscription_status = "inactive"
    user.subscription_granted_at = None
    user.password_hash = hash_password(secrets.token_urlsafe(32))
    now = utcnow()
    for session in open_sessions:
        session.revoked_at = now
    db.add(
        AuditLog(
            user_id=user.id,
            action="DEMO_ACCOUNT_NEUTRALIZED",
            entity_type="user",
            entity_id=user.id,
            details={
                "demo_mode": False,
                "role": "user",
                "is_active": False,
                "sessions_revoked": len(open_sessions),
            },
        )
    )
    return True


def ensure_local_demo_user(db: Session) -> User:
    """Create or repair the local-dev demo user. Never grants admin."""
    user = db.scalar(select(User).where(func.lower(User.email) == DEMO_EMAIL))
    created = user is None
    if user is None:
        user = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            name="GHOSTT YWP",
            timezone="America/New_York",
            risk_profile="balanced",
            role="user",
            is_active=True,
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
    else:
        user.email = DEMO_EMAIL
        user.role = "user"
        user.is_active = True
        user.password_hash = hash_password(DEMO_PASSWORD)
        if db.scalar(select(BankrollAccount).where(BankrollAccount.user_id == user.id)) is None:
            db.add(BankrollAccount(user_id=user.id))
    db.add(
        AuditLog(
            user_id=user.id,
            action="DEMO_ACCOUNT_SEEDED",
            entity_type="user",
            entity_id=user.id,
            details={"created": created, "role": "user", "demo_mode": True},
        )
    )
    return user
