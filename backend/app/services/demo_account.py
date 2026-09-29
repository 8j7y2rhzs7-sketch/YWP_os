"""Public demo login is local-dev only.

Production (`YWP_DEMO_MODE=false`) first renames an existing `demo@ywp-os.com`
row to `YWP_OWNER_EMAIL` when that address is free, keeping the same user id,
admin role, and subscription. The published password is replaced only when
`YWP_OWNER_INITIAL_PASSWORD` is set. If that secret is missing, or the owner
email already belongs to someone else, the demo row is left signed-in-able so
the owner is not locked out. Any later `demo@ywp-os.com` row is still locked.
"""

from __future__ import annotations

import logging
import secrets
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, utcnow, verify_password
from app.models import AuditLog, BankrollAccount, BankrollTransaction, RefreshSession, User

logger = logging.getLogger(__name__)

DEMO_EMAIL = "demo@ywp-os.com"
DEMO_PASSWORD = "YwpDemo!2026"
MIN_OWNER_PASSWORD_LENGTH = 10
_ADOPTED_ACTION = "OWNER_ACCOUNT_ADOPTED"


def is_demo_email(email: str | None) -> bool:
    return (email or "").strip().lower() == DEMO_EMAIL


def configured_owner_email() -> str:
    return (settings.owner_email or "").strip().lower()


def demo_authentication_blocked(email: str | None) -> bool:
    """True when this identity must not receive or use a session."""
    return is_demo_email(email) and not settings.demo_mode


def is_admin_principal(user: object) -> bool:
    """Demo identities are never operators, except the still-unmoved owner row."""
    pending_owner = settings.owner_adoption_pending and not settings.demo_mode
    if is_demo_email(getattr(user, "email", None)) and not pending_owner:
        return False
    return str(getattr(user, "role", "") or "").lower() == "admin"


def _password_is_public(user: User) -> bool:
    try:
        return verify_password(DEMO_PASSWORD, user.password_hash)
    except Exception:
        return False


def _find_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(func.lower(User.email) == email))


def _owner_password_usable() -> bool:
    password = settings.owner_initial_password or ""
    if len(password) < MIN_OWNER_PASSWORD_LENGTH:
        return False
    return password != DEMO_PASSWORD


def _revoke_open_sessions(db: Session, user_id: str) -> int:
    sessions = list(
        db.scalars(
            select(RefreshSession).where(
                RefreshSession.user_id == user_id,
                RefreshSession.revoked_at.is_(None),
            )
        ).all()
    )
    now = utcnow()
    for session in sessions:
        session.revoked_at = now
    return len(sessions)


def _adoption_recorded(db: Session, user_id: str) -> bool:
    row = db.scalar(
        select(AuditLog.id).where(
            AuditLog.user_id == user_id,
            AuditLog.action == _ADOPTED_ACTION,
        )
    )
    return row is not None


def neutralize_demo_account(db: Session) -> bool:
    """Deactivate a published demo user without deleting unrelated rows.

    Returns True when a change was written. Bankroll, tickets, and other users
    stay in place. Refresh sessions for the demo user are revoked and the
    published password stops matching.
    """
    user = _find_email(db, DEMO_EMAIL)
    if user is None:
        return False
    open_count = len(
        list(
            db.scalars(
                select(RefreshSession.id).where(
                    RefreshSession.user_id == user.id,
                    RefreshSession.revoked_at.is_(None),
                )
            ).all()
        )
    )
    public_password = _password_is_public(user)
    needs_lock = (
        user.role != "user"
        or user.is_active
        or user.subscription_status == "active"
        or user.subscription_granted_at is not None
        or public_password
        or open_count > 0
    )
    if not needs_lock:
        return False
    user.role = "user"
    user.is_active = False
    user.subscription_status = "inactive"
    user.subscription_granted_at = None
    user.password_hash = hash_password(secrets.token_urlsafe(32))
    user.auth_epoch = int(user.auth_epoch or 0) + 1
    revoked = _revoke_open_sessions(db, user.id)
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
                "sessions_revoked": revoked,
            },
        )
    )
    return True


def _adopt_demo_account(db: Session) -> str:
    """Rename the demo row onto the owner email, or explain why it did not."""
    owner_email = configured_owner_email()
    demo = _find_email(db, DEMO_EMAIL)
    if not owner_email or owner_email == DEMO_EMAIL or "@" not in owner_email:
        if demo is not None:
            logger.error(
                "Owner account was not moved: set YWP_OWNER_EMAIL to the owner's "
                "real address and restart. %s was left unchanged.",
                DEMO_EMAIL,
            )
        return "skipped_missing_config"

    owner = _find_email(db, owner_email)
    if demo is None:
        return "no_demo_user"
    if owner is not None and owner.id != demo.id:
        if _adoption_recorded(db, owner.id):
            return "future_demo"
        logger.error(
            "Owner account was not moved: %s already belongs to a different user. "
            "%s was left unchanged. Remove or rename that other user, then restart.",
            owner_email,
            DEMO_EMAIL,
        )
        return "owner_email_taken"
    if not _owner_password_usable():
        logger.error(
            "Owner account was not moved: set YWP_OWNER_INITIAL_PASSWORD to a private "
            "password of at least %s characters (not the published demo password) and "
            "restart. %s was left unchanged so the current admin is not locked out.",
            MIN_OWNER_PASSWORD_LENGTH,
            DEMO_EMAIL,
        )
        return "skipped_missing_config"

    previous_email = demo.email
    demo.email = owner_email
    demo.role = "admin"
    demo.is_active = True
    demo.password_hash = hash_password(settings.owner_initial_password)
    demo.auth_epoch = int(demo.auth_epoch or 0) + 1
    revoked = _revoke_open_sessions(db, demo.id)
    db.add(
        AuditLog(
            user_id=demo.id,
            action=_ADOPTED_ACTION,
            entity_type="user",
            entity_id=demo.id,
            details={
                "from_email": previous_email,
                "to_email": owner_email,
                "role": "admin",
                "sessions_revoked": revoked,
                "auth_epoch": demo.auth_epoch,
            },
        )
    )
    logger.info(
        "Moved demo account user_id=%s to %s and revoked %s refresh session(s).",
        demo.id,
        owner_email,
        revoked,
    )
    return "moved"


def prepare_production_identities(db: Session) -> str:
    """Move the demo row when it is safe, then lock any leftover demo login.

    Idempotent. Does not reset the owner password on later boots. Does not
    delete bankroll, tickets, or other users. Commits only when a row changes.
    """
    if settings.demo_mode:
        settings.owner_adoption_pending = False
        return "demo_mode"

    outcome = _adopt_demo_account(db)
    if outcome == "future_demo":
        settings.owner_adoption_pending = False
        db.flush()
        neutralize_demo_account(db)
    elif outcome in {"moved", "no_demo_user"}:
        settings.owner_adoption_pending = False
    else:
        settings.owner_adoption_pending = _find_email(db, DEMO_EMAIL) is not None

    if db.new or db.dirty or db.deleted:
        db.commit()
    return outcome


def reject_demo_authentication(db: Session, email: str | None) -> bool:
    """Return True when this email must be refused before the password is checked.

    While owner adoption is pending, the existing demo row can still sign in.
    """
    if not demo_authentication_blocked(email):
        prepare_production_identities(db)
        return False
    prepare_production_identities(db)
    if settings.owner_adoption_pending:
        return False
    neutralize_demo_account(db)
    if db.new or db.dirty or db.deleted:
        db.commit()
    return True


def ensure_local_demo_user(db: Session) -> User:
    """Create or repair the local-dev demo user. Never grants admin."""
    user = _find_email(db, DEMO_EMAIL)
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
