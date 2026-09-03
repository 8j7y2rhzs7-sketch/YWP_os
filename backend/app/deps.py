from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User

bearer = HTTPBearer(auto_error=False)
DB = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_token(credentials.credentials, "access")
    except jwt.PyJWTError as error:
        raise unauthorized from error
    user = db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def require_subscription(user: CurrentUser, db: DB) -> User:
    from app.services.whop_access import (
        apply_pending_access,
        sync_user_subscription,
        user_has_app_access,
    )
    from app.services.whop import whop_enabled

    if not whop_enabled() or user.role == "admin":
        return user
    user = apply_pending_access(db, user)
    user = sync_user_subscription(db, user)
    db.commit()
    db.refresh(user)
    if not user_has_app_access(user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                "Active Whop subscription required. Subscribe on Whop, then tap "
                "'Sync my access' using the same email."
            ),
        )
    return user


SubscribedUser = Annotated[User, Depends(require_subscription)]
