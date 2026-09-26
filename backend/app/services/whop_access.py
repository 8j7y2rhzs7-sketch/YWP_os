"""Whop subscription state synced to YWP OS users."""
from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, utcnow
from app.models import AuditLog, BankrollAccount, PendingWhopAccess, User
from app.services.whop import (
    app_download_url,
    check_user_access,
    checkout_url,
    find_whop_user_id_by_email,
    product_id,
    whop_enabled,
)

logger = logging.getLogger(__name__)


def user_has_app_access(user: User) -> bool:
    if not whop_enabled():
        return True
    if user.role == "admin":
        return True
    return user.subscription_status == "active"


def serialize_user(user: User):
    from app.schemas import UserOut

    base = UserOut.model_validate(user)
    has_access = user_has_app_access(user)
    return base.model_copy(
        update={
            "has_app_access": has_access,
            "subscription_status": user.subscription_status,
            "checkout_url": None if has_access else checkout_url(),
            "app_download_url": app_download_url(),
        }
    )


def _aware(value):
    if value is None:
        return None
    if value.tzinfo is None:
        from datetime import UTC

        return value.replace(tzinfo=UTC)
    return value


def _mark_active(user: User, *, membership_id: str | None = None) -> None:
    now = utcnow()
    previous_membership = user.whop_membership_id
    user.subscription_status = "active"
    user.subscription_checked_at = now
    if membership_id:
        user.whop_membership_id = membership_id
    granted = _aware(user.subscription_granted_at)
    day_pass = timedelta(seconds=settings.whop_day_pass_seconds)
    renewed_membership = bool(membership_id and membership_id != previous_membership)
    if (
        granted is None
        or renewed_membership
        or now - granted >= day_pass
    ):
        user.subscription_granted_at = now


def _mark_inactive(user: User) -> None:
    user.subscription_status = "inactive"
    user.subscription_checked_at = utcnow()
    user.subscription_granted_at = None


def apply_pending_access(db: Session, user: User) -> User:
    conditions = [PendingWhopAccess.email == user.email.lower()]
    if user.whop_user_id:
        conditions.append(PendingWhopAccess.whop_user_id == user.whop_user_id)
    pending = db.scalar(select(PendingWhopAccess).where(or_(*conditions)))
    if pending and pending.status == "active":
        user.whop_user_id = pending.whop_user_id or user.whop_user_id
        user.whop_membership_id = pending.whop_membership_id
        _mark_active(user, membership_id=pending.whop_membership_id)
        db.delete(pending)
    return user


def sync_user_subscription(db: Session, user: User) -> User:
    """Live Whop checkAccess when possible; never treat unlock as permanent."""
    if not whop_enabled() or user.role == "admin":
        if user.role == "admin":
            user.subscription_status = "active"
            user.subscription_checked_at = utcnow()
            if user.subscription_granted_at is None:
                user.subscription_granted_at = utcnow()
        return user
    if not user.whop_user_id:
        resolved = find_whop_user_id_by_email(user.email)
        if resolved:
            user.whop_user_id = resolved
    if not user.whop_user_id:
        # No Whop identity → cannot confirm day-pass access.
        if user.subscription_status == "active":
            _mark_inactive(user)
        return user
    try:
        access = check_user_access(user.whop_user_id, product_id())
        if access.get("access_level") == "unknown":
            _revoke_if_stale(user, api_failed=True)
            return user
        if access.get("has_access"):
            _mark_active(user)
        else:
            _mark_inactive(user)
    except Exception:
        logger.exception("Whop access check failed for user %s", user.id)
        _revoke_if_stale(user, api_failed=True)
    return user


def _revoke_if_stale(user: User, *, api_failed: bool) -> None:
    """Fail closed for day passes when confirmation is too old."""
    if user.subscription_status != "active":
        return
    now = utcnow()
    checked = _aware(user.subscription_checked_at)
    granted = _aware(user.subscription_granted_at)
    day_pass = timedelta(seconds=settings.whop_day_pass_seconds)
    recheck = timedelta(seconds=settings.whop_access_recheck_seconds)

    if granted is not None and now - granted >= day_pass:
        logger.info(
            "Revoking stale day-pass access for user %s (granted_at=%s)",
            user.id,
            granted.isoformat(),
        )
        _mark_inactive(user)
        return
    if checked is None:
        _mark_inactive(user)
        return
    # Brief grace while Whop is unreachable; do not let it cover a full day pass.
    grace = recheck * 2 if api_failed else recheck
    if now - checked >= grace:
        _mark_inactive(user)


def needs_subscription_recheck(user: User, *, force: bool = False) -> bool:
    if force:
        return True
    if not whop_enabled() or user.role == "admin":
        return False
    now = utcnow()
    checked = _aware(user.subscription_checked_at)
    granted = _aware(user.subscription_granted_at)
    if checked is None:
        return True
    if now - checked >= timedelta(seconds=settings.whop_access_recheck_seconds):
        return True
    if (
        user.subscription_status == "active"
        and granted is not None
        and now - granted >= timedelta(seconds=settings.whop_day_pass_seconds)
    ):
        return True
    return False


def ensure_fresh_subscription(db: Session, user: User, *, force: bool = False) -> User:
    """Apply pending grants and re-sync with Whop on a TTL schedule."""
    if not whop_enabled() or user.role == "admin":
        return sync_user_subscription(db, user)
    user = apply_pending_access(db, user)
    if needs_subscription_recheck(user, force=force):
        user = sync_user_subscription(db, user)
    elif user.subscription_status == "active":
        # Local soft ceiling even between rechecks.
        granted = _aware(user.subscription_granted_at)
        if granted is not None and utcnow() - granted >= timedelta(
            seconds=settings.whop_day_pass_seconds
        ):
            user = sync_user_subscription(db, user)
    return user


def get_or_create_whop_user(db: Session, whop_user_id: str) -> User:
    user = db.scalar(select(User).where(User.whop_user_id == whop_user_id))
    if user:
        return user
    email = f"{whop_user_id.lower()}@members.whop.invalid"
    user = db.scalar(select(User).where(User.email == email))
    if user:
        user.whop_user_id = whop_user_id
        return user
    user = User(
        email=email,
        password_hash=hash_password(secrets.token_urlsafe(48)),
        name="Whop Member",
        whop_user_id=whop_user_id,
        subscription_status="none",
    )
    db.add(user)
    db.flush()
    db.add(BankrollAccount(user_id=user.id))
    return user


def apply_subscription_from_webhook(
    db: Session,
    *,
    email: str | None,
    whop_user_id: str | None,
    membership_id: str | None,
    active: bool,
) -> None:
    user = None
    if whop_user_id:
        user = db.scalar(select(User).where(User.whop_user_id == whop_user_id))
    if not user and email:
        user = db.scalar(select(User).where(User.email == email.lower()))

    if user:
        if whop_user_id:
            user.whop_user_id = whop_user_id
        if active:
            _mark_active(user, membership_id=membership_id)
        else:
            _mark_inactive(user)
            if membership_id:
                user.whop_membership_id = membership_id
        db.add(
            AuditLog(
                user_id=user.id,
                action="WHOP_SUBSCRIPTION_ACTIVATED" if active else "WHOP_SUBSCRIPTION_DEACTIVATED",
                entity_type="subscription",
                entity_id=membership_id or whop_user_id or email or "unknown",
            )
        )
        if active:
            _clear_pending(db, email, whop_user_id)
        else:
            _deactivate_pending(db, email, whop_user_id)
        return

    if active and (email or whop_user_id):
        conditions = []
        if email:
            conditions.append(PendingWhopAccess.email == email.lower())
        if whop_user_id:
            conditions.append(PendingWhopAccess.whop_user_id == whop_user_id)
        existing = (
            db.scalar(select(PendingWhopAccess).where(or_(*conditions)))
            if conditions
            else None
        )
        if existing:
            existing.whop_user_id = whop_user_id or existing.whop_user_id
            existing.whop_membership_id = membership_id or existing.whop_membership_id
            existing.status = "active"
        else:
            db.add(
                PendingWhopAccess(
                    email=email.lower() if email else f"whop:{whop_user_id}",
                    whop_user_id=whop_user_id,
                    whop_membership_id=membership_id,
                    status="active",
                )
            )
        return

    if not active:
        _deactivate_pending(db, email, whop_user_id)


def _clear_pending(db: Session, email: str | None, whop_user_id: str | None) -> None:
    conditions = []
    if email:
        conditions.append(PendingWhopAccess.email == email.lower())
    if whop_user_id:
        conditions.append(PendingWhopAccess.whop_user_id == whop_user_id)
    if not conditions:
        return
    pending = db.scalar(select(PendingWhopAccess).where(or_(*conditions)))
    if pending:
        db.delete(pending)


def _deactivate_pending(db: Session, email: str | None, whop_user_id: str | None) -> None:
    conditions = []
    if email:
        conditions.append(PendingWhopAccess.email == email.lower())
    if whop_user_id:
        conditions.append(PendingWhopAccess.whop_user_id == whop_user_id)
    if not conditions:
        return
    pending = db.scalar(select(PendingWhopAccess).where(or_(*conditions)))
    if pending:
        pending.status = "inactive"
