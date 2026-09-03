from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_token_pair, hash_token, utcnow
from app.models import RefreshSession, User
from app.schemas import TokenResponse


def issue_tokens(db: Session, user: User) -> TokenResponse:
    pair = create_token_pair(user.id)
    db.add(
        RefreshSession(
            user_id=user.id,
            jti=pair["refresh_jti"],
            token_hash=hash_token(pair["refresh_token"]),
            expires_at=pair["refresh_expires_at"],
        )
    )
    db.commit()
    return TokenResponse(
        access_token=pair["access_token"],
        refresh_token=pair["refresh_token"],
        access_expires_at=pair["access_expires_at"],
        refresh_expires_at=pair["refresh_expires_at"],
    )


def find_refresh_session(db: Session, raw_token: str) -> RefreshSession | None:
    return db.scalar(
        select(RefreshSession).where(RefreshSession.token_hash == hash_token(raw_token))
    )


def revoke_session(session: RefreshSession, when: datetime | None = None) -> None:
    session.revoked_at = when or utcnow()
