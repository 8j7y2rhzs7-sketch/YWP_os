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
    assert body["app_download_url"].endswith("YWP-OS-3.3.5.apk")
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
    assert body["app_download_url"].endswith("YWP-OS-3.3.5.apk")


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
