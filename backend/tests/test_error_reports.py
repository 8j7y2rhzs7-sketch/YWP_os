from __future__ import annotations

from fastapi.testclient import TestClient


def test_submit_error_report_anonymous(client: TestClient) -> None:
    response = client.post(
        "/api/v1/errors",
        json={
            "category": "crash",
            "message": "UI crashed while opening ticket cards",
            "screen": "analysis",
            "app_version": "3.2.3",
            "platform": "android",
            "context": {"note": "unit-test"},
        },
    )
    assert response.status_code == 201, response.text
    assert "received" in response.json()["message"].lower()


def test_submit_error_report_authenticated(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/errors",
        headers=auth_headers,
        json={
            "category": "pick_quality",
            "message": "Rank 1 pick never appeared on any ticket card",
            "screen": "analysis",
            "app_version": "3.2.3",
            "platform": "android",
        },
    )
    assert response.status_code == 201, response.text


def test_list_error_reports_requires_admin(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    denied = client.get("/api/v1/errors", headers=auth_headers)
    assert denied.status_code == 403

    from app.core.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        user = db.query(User).one()
        user.role = "admin"
        db.commit()
    finally:
        db.close()

    seed = client.post(
        "/api/v1/errors",
        headers=auth_headers,
        json={"category": "ui", "message": "Button did nothing after lock check"},
    )
    assert seed.status_code == 201, seed.text
    listed = client.get("/api/v1/errors", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) >= 1
