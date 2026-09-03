from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hasher = PasswordHash.recommended()


def utcnow() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_token(
    subject: str,
    token_type: Literal["access", "refresh"],
    expires_delta: timedelta,
    extra: dict[str, Any] | None = None,
) -> tuple[str, datetime, str]:
    now = utcnow()
    expires_at = now + expires_delta
    jti = str(uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "jti": jti,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": expires_at,
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at, jti


def create_token_pair(subject: str) -> dict[str, Any]:
    access_token, access_expires, _ = create_token(
        subject,
        "access",
        timedelta(minutes=settings.access_token_minutes),
    )
    refresh_token, refresh_expires, refresh_jti = create_token(
        subject,
        "refresh",
        timedelta(days=settings.refresh_token_days),
        {"nonce": secrets.token_hex(8)},
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_expires_at": access_expires,
        "refresh_expires_at": refresh_expires,
        "refresh_jti": refresh_jti,
    }


def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub", "type", "jti"]},
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Wrong token type")
    return payload
