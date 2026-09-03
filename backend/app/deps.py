import logging
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User

bearer = HTTPBearer(auto_error=False)
DB = Annotated[Session, Depends(get_db)]


def payment_required(message: str | None = None) -> HTTPException:
    from app.services.whop import checkout_url

    url = checkout_url()
    return HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "message": message
            or "Daily Access required. Complete checkout on Whop, then return.",
            "checkout_url": url,
        },
        headers={"Location": url},
    )


def get_current_user(
    request: Request,
    db: DB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    from app.services.whop import verify_whop_user_token
    from app.services.whop_access import get_or_create_whop_user

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    whop_user_id = verify_whop_user_token(request.headers)
    if whop_user_id:
        user = get_or_create_whop_user(db, whop_user_id)
        db.commit()
        db.refresh(user)
        if not user.is_active:
            raise unauthorized
        return user

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


def get_optional_user(
    request: Request,
    db: DB,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User | None:
    """Resolve the caller when authenticated; never raise 401 for anonymous clients."""
    try:
        return get_current_user(request, db, credentials)
    except HTTPException as error:
        if error.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_402_PAYMENT_REQUIRED}:
            return None
        raise


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def require_subscription(user: CurrentUser, db: DB) -> User:
    from app.services.whop import check_user_access, product_id, whop_enabled
    from app.services.whop_access import (
        apply_pending_access,
        sync_user_subscription,
        user_has_app_access,
    )

    if not whop_enabled() or user.role == "admin":
        return user
    user = apply_pending_access(db, user)
    if user.whop_user_id:
        try:
            access = check_user_access(user.whop_user_id, product_id())
            if access.get("access_level") != "unknown":
                user.subscription_status = "active" if access.get("has_access") else "inactive"
        except Exception:
            logging.getLogger(__name__).exception(
                "Whop checkAccess failed for user %s", user.id
            )
    else:
        user = sync_user_subscription(db, user)
    db.commit()
    db.refresh(user)
    if not user_has_app_access(user):
        raise payment_required()
    return user


SubscribedUser = Annotated[User, Depends(require_subscription)]