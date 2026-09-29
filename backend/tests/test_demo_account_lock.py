"""Published demo login cannot authenticate or act as admin when demo mode is off."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password, verify_password
from app.models import BankrollAccount, User
from app.seed import DEMO_EMAIL, DEMO_PASSWORD, seed
from app.services.auth import issue_tokens
from app.services.demo_account import neutralize_demo_account
from app.services.whop_access import user_has_app_access


def _demo_user(db, *, role: str = "admin", active: bool = True) -> User:
    user = User(
        email=DEMO_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        name="GHOSTT YWP",
        timezone="America/New_York",
        role=role,
        is_active=active,
        subscription_status="active",
    )
    db.add(user)
    db.flush()
    db.add(
        BankrollAccount(
            user_id=user.id,
            balance=1000,
        )
    )
    db.add(
        User(
            email="real-owner@ywp-os.com",
            password_hash=hash_password("OwnerYwp!2026"),
            name="Real Owner",
            timezone="America/New_York",
            role="admin",
            is_active=True,
            subscription_status="active",
        )
    )
    db.commit()
    db.refresh(user)
    return user


def test_seed_never_creates_demo_admin(monkeypatch) -> None:
    monkeypatch.setattr(settings, "demo_mode", True)
    seed()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        assert user is not None
        assert user.role == "user"
        assert user.is_active is True
        assert verify_password(DEMO_PASSWORD, user.password_hash)


def test_local_demo_login_is_not_admin(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "demo_mode", True)
    seed()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["role"] == "user"
    propose = client.post("/api/v1/learning/weights/propose", headers=headers)
    assert propose.status_code == 403


def test_demo_mode_off_blocks_login_tokens_and_refresh(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "demo_mode", True)
    with SessionLocal() as db:
        user = _demo_user(db)
        original_id = user.id
        tokens = issue_tokens(db, user)
        access = tokens.access_token
        refresh = tokens.refresh_token

    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "owner_email", "ywpossports@gmail.com")
    monkeypatch.setattr(settings, "owner_initial_password", "OwnerPrivate!2026")

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert refreshed.status_code == 401
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    assert login.status_code == 401

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": DEMO_EMAIL,
            "password": "AnotherStrong!2026",
            "name": "Demo Clone",
            "timezone": "America/New_York",
        },
    )
    assert register.status_code == 403

    with SessionLocal() as db:
        moved = db.scalar(select(User).where(User.email == "ywpossports@gmail.com"))
        assert moved is not None
        assert moved.id == original_id
        assert moved.role == "admin"
        assert moved.is_active is True
        assert verify_password(DEMO_PASSWORD, moved.password_hash) is False
        assert verify_password("OwnerPrivate!2026", moved.password_hash) is True
        bankroll = db.scalar(select(BankrollAccount).where(BankrollAccount.user_id == moved.id))
        assert bankroll is not None
        other = db.scalar(select(User).where(User.email == "real-owner@ywp-os.com"))
        assert other is not None and other.role == "admin" and other.is_active is True


def test_seed_moves_existing_demo_without_deleting_others(monkeypatch) -> None:
    monkeypatch.setattr(settings, "demo_mode", True)
    with SessionLocal() as db:
        demo = _demo_user(db, role="admin")
        demo_id = demo.id
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "owner_email", "ywpossports@gmail.com")
    monkeypatch.setattr(settings, "owner_initial_password", "OwnerPrivate!2026")
    seed()
    with SessionLocal() as db:
        moved = db.scalar(select(User).where(User.email == "ywpossports@gmail.com"))
        owner = db.scalar(select(User).where(User.email == "real-owner@ywp-os.com"))
        assert moved is not None and moved.id == demo_id
        assert moved.role == "admin" and moved.is_active is True
        assert db.scalar(select(User).where(User.email == DEMO_EMAIL)) is None
        assert owner is not None and owner.role == "admin" and owner.is_active is True
        assert neutralize_demo_account(db) is False


def test_demo_email_is_never_an_admin_principal(monkeypatch) -> None:
    monkeypatch.setattr(settings, "whop_subscription_required", True)
    monkeypatch.setattr(settings, "whop_product_id", "prod_test")
    demo = User(
        email=DEMO_EMAIL,
        password_hash="x",
        name="Demo",
        role="admin",
        subscription_status="none",
    )
    owner = User(
        email="owner-admin@ywp-os.com",
        password_hash="x",
        name="Owner",
        role="admin",
        subscription_status="none",
    )
    assert user_has_app_access(demo) is False
    assert user_has_app_access(owner) is True


def test_cannot_provision_demo_as_admin(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "provision_secret", "test-provision-secret")
    denied = client.post(
        "/api/v1/auth/provision-tester",
        headers={"X-YWP-Provision-Secret": "test-provision-secret"},
        json={
            "email": DEMO_EMAIL,
            "password": "TesterPass123",
            "name": "Demo Admin",
            "role": "admin",
        },
    )
    assert denied.status_code == 403
