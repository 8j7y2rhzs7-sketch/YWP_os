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
