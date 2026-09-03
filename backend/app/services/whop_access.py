"""Whop subscription state synced to YWP OS users."""
from __future__ import annotations

import logging
import secrets

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import AuditLog, BankrollAccount, PendingWhopAccess, User
from app.services.whop import check_user_access, checkout_url, product_id, whop_enabled

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
        }
    )


def apply_pending_access(db: Session, user: User) -> User:
    conditions = [PendingWhopAccess.email == user.email.lower()]
    if user.whop_user_id:
        conditions.append(PendingWhopAccess.whop_user_id == user.whop_user_id)
    pending = db.scalar(select(PendingWhopAccess).where(or_(*conditions)))
    if pending and pending.status == "active":
        user.whop_user_id = pending.whop_user_id or user.whop_user_id
        user.whop_membership_id = pending.whop_membership_id
        user.subscription_status = "active"
        db.delete(pending)
    return user


def sync_user_subscription(db: Session, user: User) -> User:
    if not whop_enabled() or user.role == "admin":
        if user.role == "admin":
            user.subscription_status = "active"
        return user
    if user.whop_user_id:
        try:
            access = check_user_access(user.whop_user_id, product_id())
            if access.get("access_level") != "unknown":
                user.subscription_status = "active" if access.get("has_access") else "inactive"
        except Exception:
            logger.exception("Whop access check failed for user %s", user.id)
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
        user.whop_membership_id = membership_id
        user.subscription_status = "active" if active else "inactive"
        db.add(
            AuditLog(
                user_id=user.id,
                action="WHOP_SUBSCRIPTION_ACTIVATED" if active else "WHOP_SUBSCRIPTION_DEACTIVATED",
                entity_type="subscription",
                entity_id=membership_id or whop_user_id or email or "unknown",
            )
        )
        _clear_pending(db, email, whop_user_id)
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
