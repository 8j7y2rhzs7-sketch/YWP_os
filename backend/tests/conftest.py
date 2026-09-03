from __future__ import annotations

import os

os.environ["YWP_ENV"] = "test"
os.environ["YWP_DEMO_MODE"] = "true"
os.environ["YWP_JWT_SECRET"] = "test-secret-that-is-longer-than-thirty-two-bytes"
os.environ["DATABASE_URL"] = "sqlite:///./test_ywp.db"
os.environ["WHOP_SUBSCRIPTION_REQUIRED"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@ywp-os.com",
            "password": "StrongYwp!2026",
            "name": "YWP Owner",
            "timezone": "America/New_York",
        },
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
