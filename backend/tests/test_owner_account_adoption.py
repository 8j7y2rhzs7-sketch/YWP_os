"""Production startup renames demo@ onto the owner email without dropping history."""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password, verify_password
from app.models import BankrollAccount, RefreshSession, User
from app.services.auth import issue_tokens
from app.services.demo_account import DEMO_EMAIL, DEMO_PASSWORD, prepare_production_identities

OWNER_EMAIL = "ywpossports@gmail.com"
OWNER_PASSWORD = "OwnerPrivate!2026"


def _demo_admin(db) -> User:
    user = User(
        email=DEMO_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        name="GHOSTT YWP",
        timezone="America/New_York",
        role="admin",
        is_active=True,
        subscription_status="active",
    )
    db.add(user)
    db.flush()
    db.add(BankrollAccount(user_id=user.id, balance=2500))
    db.commit()
    db.refresh(user)
    return user


def _enable_move(monkeypatch, *, password: str = OWNER_PASSWORD) -> None:
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "owner_email", OWNER_EMAIL)
    monkeypatch.setattr(settings, "owner_initial_password", password)


def test_move_keeps_id_admin_and_bankroll(monkeypatch) -> None:
    _enable_move(monkeypatch)
    with SessionLocal() as db:
        demo = _demo_admin(db)
        demo_id = demo.id
        outcome = prepare_production_identities(db)
        assert outcome == "moved"
        moved = db.scalar(select(User).where(User.email == OWNER_EMAIL))
        assert moved is not None
        assert moved.id == demo_id
        assert moved.role == "admin"
        assert moved.is_active is True
        assert moved.subscription_status == "active"
        assert verify_password(DEMO_PASSWORD, moved.password_hash) is False
        assert verify_password(OWNER_PASSWORD, moved.password_hash) is True
        bankroll = db.scalar(select(BankrollAccount).where(BankrollAccount.user_id == demo_id))
        assert bankroll is not None and float(bankroll.balance) == 2500
        assert db.scalar(select(User).where(User.email == DEMO_EMAIL)) is None


def test_missing_password_does_not_move_or_lock(monkeypatch, caplog) -> None:
    _enable_move(monkeypatch, password="")
    with SessionLocal() as db:
        demo = _demo_admin(db)
        demo_id = demo.id
        with caplog.at_level(logging.ERROR):
            outcome = prepare_production_identities(db)
        assert outcome == "skipped_missing_config"
        assert "YWP_OWNER_INITIAL_PASSWORD" in caplog.text
        assert OWNER_PASSWORD not in caplog.text
        user = db.get(User, demo_id)
        assert user is not None
        assert user.email == DEMO_EMAIL
        assert user.role == "admin"
        assert user.is_active is True
        assert user.subscription_status == "active"
        assert verify_password(DEMO_PASSWORD, user.password_hash) is True


def test_missing_password_still_allows_demo_admin_login(client: TestClient, monkeypatch) -> None:
    _enable_move(monkeypatch, password="")
    with SessionLocal() as db:
        _demo_admin(db)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    assert login.status_code == 200, login.text
    me = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert me.status_code == 200, me.text
    assert me.json()["role"] == "admin"
    assert me.json()["email"] == DEMO_EMAIL


def test_owner_email_already_taken_is_not_clobbered(monkeypatch, caplog) -> None:
    _enable_move(monkeypatch)
    with SessionLocal() as db:
        demo = _demo_admin(db)
        other = User(
            email=OWNER_EMAIL,
            password_hash=hash_password("OtherUser!2026"),
            name="Other",
            timezone="America/New_York",
            role="user",
            is_active=True,
            subscription_status="none",
        )
        db.add(other)
        db.commit()
        other_id = other.id
        demo_id = demo.id
        with caplog.at_level(logging.ERROR):
            outcome = prepare_production_identities(db)
        assert outcome == "owner_email_taken"
        assert OWNER_EMAIL in caplog.text
        assert "different user" in caplog.text
        assert OWNER_PASSWORD not in caplog.text
        demo_row = db.get(User, demo_id)
        other_row = db.get(User, other_id)
        assert demo_row is not None and demo_row.email == DEMO_EMAIL
        assert demo_row.role == "admin" and demo_row.is_active is True
        assert verify_password(DEMO_PASSWORD, demo_row.password_hash) is True
        assert other_row is not None and other_row.email == OWNER_EMAIL
        assert other_row.role == "user"
        assert verify_password("OtherUser!2026", other_row.password_hash) is True


def test_move_is_idempotent_and_does_not_reset_password(monkeypatch) -> None:
    _enable_move(monkeypatch)
    with SessionLocal() as db:
        demo = _demo_admin(db)
        demo_id = demo.id
        assert prepare_production_identities(db) == "moved"
        moved = db.get(User, demo_id)
        assert moved is not None
        moved.password_hash = hash_password("ChangedLater!2026")
        epoch = moved.auth_epoch
        db.commit()
        assert prepare_production_identities(db) == "no_demo_user"
        again = db.get(User, demo_id)
        assert again is not None
        assert again.email == OWNER_EMAIL
        assert again.role == "admin"
        assert again.is_active is True
        assert again.auth_epoch == epoch
        assert verify_password("ChangedLater!2026", again.password_hash) is True
        assert verify_password(OWNER_PASSWORD, again.password_hash) is False
        assert verify_password(DEMO_PASSWORD, again.password_hash) is False


def test_published_demo_password_and_old_tokens_fail_after_move(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "demo_mode", True)
    with SessionLocal() as db:
        demo = _demo_admin(db)
        tokens = issue_tokens(db, demo)
        access = tokens.access_token
        refresh = tokens.refresh_token
    _enable_move(monkeypatch)

    assert (
        client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh},
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {access}"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": OWNER_EMAIL, "password": DEMO_PASSWORD},
        ).status_code
        == 401
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    assert login.status_code == 200, login.text
    me = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert me.status_code == 200, me.text
    assert me.json()["email"] == OWNER_EMAIL
    assert me.json()["role"] == "admin"
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == OWNER_EMAIL))
        assert user is not None
        open_sessions = db.scalars(
            select(RefreshSession).where(
                RefreshSession.user_id == user.id,
                RefreshSession.revoked_at.is_(None),
            )
        ).all()
        # The pre-move session is revoked. Login above opens one new session.
        assert len(open_sessions) == 1


def test_future_demo_row_is_locked_after_adoption(monkeypatch) -> None:
    _enable_move(monkeypatch)
    with SessionLocal() as db:
        _demo_admin(db)
        assert prepare_production_identities(db) == "moved"
        clone = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            name="Later Demo",
            timezone="America/New_York",
            role="admin",
            is_active=True,
            subscription_status="active",
        )
        db.add(clone)
        db.commit()
        assert prepare_production_identities(db) == "future_demo"
        locked = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        owner = db.scalar(select(User).where(User.email == OWNER_EMAIL))
        assert locked is not None and locked.is_active is False and locked.role == "user"
        assert verify_password(DEMO_PASSWORD, locked.password_hash) is False
        assert owner is not None and owner.role == "admin" and owner.is_active is True
