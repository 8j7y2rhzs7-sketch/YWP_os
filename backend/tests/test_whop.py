from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient


def _sign(payload: bytes, secret: str, msg_id: str, timestamp: str) -> str:
    signed = f"{msg_id}.{timestamp}.{payload.decode('utf-8')}"
    digest = base64.b64encode(
        hmac.new(secret.encode(), signed.encode(), hashlib.sha256).digest()
    ).decode()
    return digest


def test_whop_webhook_grants_pending_access(client: TestClient, monkeypatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "whop_api_key", "apik_test")
    monkeypatch.setattr(settings, "whop_product_id", "prod_test")
    monkeypatch.setattr(settings, "whop_webhook_secret", "ws_test_secret")
    monkeypatch.setattr(settings, "whop_subscription_required", True)

    payload = json.dumps(
        {
            "id": "evt_test_1",
            "type": "membership.activated",
            "data": {
                "id": "mem_123",
                "status": "active",
                "user": {"id": "user_whop_1", "email": "subscriber@ywp-os.com"},
            },
        }
    ).encode()
    msg_id = "msg_123"
    timestamp = str(int(time.time()))
    signature = _sign(payload, "ws_test_secret", msg_id, timestamp)

    response = client.post(
        "/api/v1/whop/webhook",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "webhook-id": msg_id,
            "webhook-timestamp": timestamp,
            "webhook-signature": signature,
        },
    )
    assert response.status_code == 200, response.text

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "subscriber@ywp-os.com",
            "password": "StrongYwp!2026",
            "name": "Whop Subscriber",
        },
    )
    assert register.status_code == 201, register.text
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["has_app_access"] is True
    assert body["subscription_status"] == "active"


def test_checkout_uses_existing_decision_engine_plan(client: TestClient) -> None:
    response = client.get("/api/v1/whop/checkout")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["checkout_url"] == "https://whop.com/checkout/plan_MwJ2qcFxmvqDY"
    assert body["product_id"] == "prod_NuPQUAGoibkpW"
    assert body["app_download_url"].endswith("YWP-OS-3.3.7.apk")
    assert "same email" in body["message"].lower()


def test_sync_resolves_membership_by_email(
    client: TestClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "whop_subscription_required", True)
    monkeypatch.setattr(settings, "whop_product_id", "prod_NuPQUAGoibkpW")
    monkeypatch.setattr(settings, "whop_api_key", "apik_test")
    monkeypatch.setattr(settings, "whop_company_id", "biz_test")

    monkeypatch.setattr(
        "app.services.whop_access.find_whop_user_id_by_email",
        lambda _email: "user_whop_email_1",
    )
    monkeypatch.setattr(
        "app.services.whop_access.check_user_access",
        lambda _uid, _product=None: {"has_access": True, "access_level": "customer"},
    )

    response = client.post("/api/v1/whop/sync", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_access"] is True
    assert body["status"] == "active"
    assert body["whop_user_id"] == "user_whop_email_1"
    assert body["app_download_url"].endswith("YWP-OS-3.3.7.apk")


def test_day_pass_expires_without_fresh_checkaccess(
    client: TestClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    from datetime import timedelta

    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.core.security import utcnow
    from app.models import User

    monkeypatch.setattr(settings, "whop_subscription_required", True)
    monkeypatch.setattr(settings, "whop_product_id", "prod_NuPQUAGoibkpW")
    monkeypatch.setattr(settings, "whop_api_key", "apik_test")
    monkeypatch.setattr(settings, "whop_access_recheck_seconds", 300)
    monkeypatch.setattr(settings, "whop_day_pass_seconds", 86_400)

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "owner@ywp-os.com").one()
        user.whop_user_id = "user_stale_1"
        user.subscription_status = "active"
        user.subscription_granted_at = utcnow() - timedelta(hours=25)
        user.subscription_checked_at = utcnow() - timedelta(hours=25)
        db.commit()

    calls: list[str] = []

    def fake_check(uid: str, _product=None):
        calls.append(uid)
        return {"has_access": False, "access_level": "no_access"}

    monkeypatch.setattr("app.services.whop_access.check_user_access", fake_check)

    me = client.get("/api/v1/users/me", headers=auth_headers)
    assert me.status_code == 200, me.text
    assert me.json()["has_app_access"] is False
    assert me.json()["subscription_status"] == "inactive"
    assert calls == ["user_stale_1"]


def test_repay_regrants_access_via_sync(
    client: TestClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.models import User

    monkeypatch.setattr(settings, "whop_subscription_required", True)
    monkeypatch.setattr(settings, "whop_product_id", "prod_NuPQUAGoibkpW")
    monkeypatch.setattr(settings, "whop_api_key", "apik_test")

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "owner@ywp-os.com").one()
        user.whop_user_id = "user_repay_1"
        user.subscription_status = "inactive"
        user.subscription_granted_at = None
        user.subscription_checked_at = None
        db.commit()

    monkeypatch.setattr(
        "app.services.whop_access.check_user_access",
        lambda _uid, _product=None: {"has_access": True, "access_level": "customer"},
    )

    response = client.post("/api/v1/whop/sync", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["has_access"] is True
    assert response.json()["status"] == "active"

    me = client.get("/api/v1/users/me", headers=auth_headers)
    assert me.json()["has_app_access"] is True


def test_webhook_expired_revokes_access(client: TestClient, monkeypatch) -> None:
    import base64
    import hashlib
    import hmac
    import json
    import time

    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.core.security import hash_password
    from app.models import BankrollAccount, User

    monkeypatch.setattr(settings, "whop_api_key", "apik_test")
    monkeypatch.setattr(settings, "whop_product_id", "prod_test")
    monkeypatch.setattr(settings, "whop_webhook_secret", "ws_test_secret")
    monkeypatch.setattr(settings, "whop_subscription_required", True)

    with SessionLocal() as db:
        user = User(
            email="daypass@ywp-os.com",
            password_hash=hash_password("StrongYwp!2026"),
            name="Day Pass",
            whop_user_id="user_expire_1",
            subscription_status="active",
        )
        db.add(user)
        db.flush()
        db.add(BankrollAccount(user_id=user.id))
        db.commit()

    payload = json.dumps(
        {
            "id": "evt_expire_1",
            "type": "membership.deactivated",
            "data": {
                "id": "mem_expire",
                "status": "expired",
                "user": {"id": "user_expire_1", "email": "daypass@ywp-os.com"},
            },
        }
    ).encode()
    msg_id = "msg_expire"
    timestamp = str(int(time.time()))
    signed = f"{msg_id}.{timestamp}.{payload.decode()}"
    signature = base64.b64encode(
        hmac.new(b"ws_test_secret", signed.encode(), hashlib.sha256).digest()
    ).decode()

    response = client.post(
        "/api/v1/whop/webhook",
        content=payload,
        headers={
            "Content-Type": "application/json",
            "webhook-id": msg_id,
            "webhook-timestamp": timestamp,
            "webhook-signature": signature,
        },
    )
    assert response.status_code == 200, response.text

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "daypass@ywp-os.com").one()
        assert user.subscription_status == "inactive"
        assert user.subscription_granted_at is None


def test_protected_route_sends_unpaid_user_to_whop_checkout(
    client: TestClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    from datetime import date

    from app.core.config import settings

    monkeypatch.setattr(settings, "whop_subscription_required", True)
    monkeypatch.setattr(settings, "whop_product_id", "prod_NuPQUAGoibkpW")
    monkeypatch.setattr(
        settings, "whop_checkout_url", "https://whop.com/checkout/plan_MwJ2qcFxmvqDY"
    )
    monkeypatch.setattr(settings, "whop_api_key", None)

    slate = client.get(
        "/api/v1/sports/slate",
        params={"sport": "mlb", "date": str(date.today())},
        headers=auth_headers,
    )
    assert slate.status_code == 402, slate.text
    detail = slate.json()["detail"]
    assert detail["checkout_url"] == "https://whop.com/checkout/plan_MwJ2qcFxmvqDY"


def test_experience_linker_never_sets_is_public() -> None:
    import inspect

    from app.services import whop_experience

    source = inspect.getsource(whop_experience.link_decision_engine_experience)
    assert "is_public" not in source
    assert "prod_NuPQUAGoibkpW" in source or "product_id" in source
