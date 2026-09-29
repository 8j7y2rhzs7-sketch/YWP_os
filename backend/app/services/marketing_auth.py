"""Scoped marketing service token — env override or DB-stored SHA-256 hash."""

from __future__ import annotations

import hmac
import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_token, utcnow
from app.models import ServiceCredential

MARKETING_CREDENTIAL_NAME = "marketing_feed"


def marketing_token_configured(db: Session) -> bool:
    if (settings.marketing_service_token or "").strip():
        return True
    row = db.scalar(
        select(ServiceCredential).where(ServiceCredential.name == MARKETING_CREDENTIAL_NAME)
    )
    return row is not None


def verify_marketing_service_token(db: Session, provided: str) -> bool:
    token = (provided or "").strip()
    if not token:
        return False
    expected_env = (settings.marketing_service_token or "").strip()
    if expected_env and hmac.compare_digest(expected_env, token):
        return True
    row = db.scalar(
        select(ServiceCredential).where(ServiceCredential.name == MARKETING_CREDENTIAL_NAME)
    )
    if row is None:
        return False
    return hmac.compare_digest(row.token_hash, hash_token(token))


def rotate_marketing_service_token(db: Session, *, admin_user_id: str) -> dict[str, Any]:
    """Generate a new marketing token. Plaintext is returned once; only the hash is stored."""
    plaintext = secrets.token_urlsafe(32)
    digest = hash_token(plaintext)
    row = db.scalar(
        select(ServiceCredential).where(ServiceCredential.name == MARKETING_CREDENTIAL_NAME)
    )
    now = utcnow()
    if row is None:
        row = ServiceCredential(
            name=MARKETING_CREDENTIAL_NAME,
            token_hash=digest,
            rotated_by_user_id=admin_user_id,
            created_at=now,
            rotated_at=now,
        )
        db.add(row)
    else:
        row.token_hash = digest
        row.rotated_by_user_id = admin_user_id
        row.rotated_at = now
        db.add(row)
    return {
        "name": MARKETING_CREDENTIAL_NAME,
        "token": plaintext,
        "rotated_at": now.isoformat(),
        "note": (
            "Store this token as YWP_OS_API_TOKEN for the marketing bot. "
            "It will not be shown again."
        ),
    }
