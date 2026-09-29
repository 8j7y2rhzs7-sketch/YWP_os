from datetime import UTC

import hmac

import jwt
from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import select

from app.core.config import settings
from app.core.security import decode_token, hash_password, utcnow, verify_password
from app.deps import DB
from app.models import AuditLog, BankrollAccount, User
from app.schemas import (
    LoginRequest,
    LogoutRequest,
    MessageOut,
    ProvisionTesterOut,
    ProvisionTesterRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.whop_access import apply_pending_access, ensure_fresh_subscription
from app.services.auth import find_refresh_session, issue_tokens, revoke_session
from app.services.tester_access import upsert_tester

router = APIRouter(prefix="/auth", tags=["authentication"])


def _aware(value):
    return value if value.tzinfo else value.replace(tzinfo=UTC)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DB) -> TokenResponse:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with that email already exists")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
        timezone=payload.timezone,
    )
    db.add(user)
    db.flush()
    db.add(BankrollAccount(user_id=user.id))
    user = apply_pending_access(db, user)
    user = ensure_fresh_subscription(db, user, force=True)
    db.add(
        AuditLog(
            user_id=user.id,
            action="USER_REGISTERED",
            entity_type="user",
            entity_id=user.id,
        )
    )
    db.commit()
    return issue_tokens(db, user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DB) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    user = apply_pending_access(db, user)
    user = ensure_fresh_subscription(db, user, force=True)
    db.add(
        AuditLog(
            user_id=user.id,
            action="USER_LOGGED_IN",
            entity_type="user",
            entity_id=user.id,
        )
    )
    db.commit()
    return issue_tokens(db, user)


@router.post(
    "/provision-tester",
    response_model=ProvisionTesterOut,
    status_code=status.HTTP_201_CREATED,
)
def provision_tester(
    payload: ProvisionTesterRequest,
    db: DB,
    x_ywp_provision_secret: str | None = Header(default=None),
) -> ProvisionTesterOut:
    """Create/activate a tester account with subscription access (ops only)."""
    expected = (settings.provision_secret or "").strip()
    provided = (x_ywp_provision_secret or "").strip()
    if not expected or not provided or not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=403, detail="Provision secret rejected")
    user, created = upsert_tester(
        db,
        email=str(payload.email),
        password=payload.password,
        name=payload.name,
        timezone=payload.timezone,
        role=payload.role,
    )
    db.commit()
    return ProvisionTesterOut(
        email=user.email,
        name=user.name,
        created=created,
        subscription_status=user.subscription_status,
        role=user.role,
        message=(
            f"{'Created' if created else 'Updated'} {user.role} account with active access"
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: DB) -> TokenResponse:
    try:
        claims = decode_token(payload.refresh_token, "refresh")
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from error
    session = find_refresh_session(db, payload.refresh_token)
    if (
        not session
        or session.revoked_at is not None
        or _aware(session.expires_at) <= utcnow()
        or session.user_id != claims["sub"]
        or session.jti != claims["jti"]
    ):
        raise HTTPException(status_code=401, detail="Refresh session is expired or revoked")
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive")
    revoke_session(session)
    db.commit()
    return issue_tokens(db, user)


@router.post("/logout", response_model=MessageOut)
def logout(payload: LogoutRequest, db: DB) -> MessageOut:
    session = find_refresh_session(db, payload.refresh_token)
    if session and session.revoked_at is None:
        revoke_session(session)
        db.commit()
    return MessageOut(message="Session revoked")
