from __future__ import annotations

from fastapi.testclient import TestClient


def test_provision_tester_requires_secret(client: TestClient, monkeypatch) -> None:
    from app.core import config

    monkeypatch.setattr(config.settings, "provision_secret", "test-provision-secret")

    denied = client.post(
        "/api/v1/auth/provision-tester",
        json={
            "email": "tester-denied@example.com",
            "password": "TesterPass123",
            "name": "Denied",
        },
    )
    assert denied.status_code == 403

    created = client.post(
        "/api/v1/auth/provision-tester",
        headers={"X-YWP-Provision-Secret": "test-provision-secret"},
        json={
            "email": "tester-ok@example.com",
            "password": "TesterPass123",
            "name": "Tester Ok",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["created"] is True
    assert body["subscription_status"] == "active"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "tester-ok@example.com", "password": "TesterPass123"},
    )
    assert login.status_code == 200
    me = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["has_app_access"] is True
