from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.seed import DEMO_EMAIL, DEMO_PASSWORD, seed


def test_learning_requires_admin_approval_and_supports_rollback(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    slate = client.get(
        "/api/v1/sports/slate",
        params={"sport": "mlb", "date": str(date.today())},
        headers=auth_headers,
    )
    assert slate.status_code == 200
    candidates = slate.json()["candidates"]

    for _ in range(30):
        analysis = client.post(
            "/api/v1/sports/analyze",
            json={
                "sport": "mlb",
                "date": str(date.today()),
                "mode": "pregame",
                "user_risk_profile": "balanced",
                "candidates": candidates,
            },
            headers=auth_headers,
        )
        assert analysis.status_code == 201
        recs = analysis.json()["ranked_picks"] + analysis.json()["stay_away"]
        target = next(item for item in recs if item["candidate_id"] == "demo-mlb-1")
        result = client.post(
            "/api/v1/sports/result",
            json={
                "recommendation_id": target["id"],
                "outcome": "LOSS",
                "stake": "1.00",
                "profit_loss": "-1.00",
                "process_outcome_class": "BAD_PROCESS_BAD_OUTCOME",
                "error_category": "BAD_PRICE",
                "process_grade": "D",
                "variance_grade": "MEDIUM",
                "root_cause_tags": ["PRICE_DISCIPLINE"],
                "lesson": "Repeated price error used only as proposal evidence.",
            },
            headers=auth_headers,
        )
        assert result.status_code == 201

    forbidden = client.post("/api/v1/learning/weights/propose", headers=auth_headers)
    assert forbidden.status_code == 403

    seed()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    assert login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    proposed = client.post("/api/v1/learning/weights/propose", headers=admin_headers)
    assert proposed.status_code == 200, proposed.text
    proposal = next(item for item in proposed.json() if item["feature_name"] == "market_value")
    assert proposal["sample_size"] >= 30
    assert proposal["repeated_pattern_count"] >= 5
    assert proposal["status"] == "pending"

    approved = client.post(
        f"/api/v1/learning/weights/proposals/{proposal['id']}/review",
        json={"decision": "approve", "note": "Reviewed repeated evidence."},
        headers=admin_headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "applied"

    rolled_back = client.post(
        f"/api/v1/learning/weights/proposals/{proposal['id']}/rollback",
        headers=admin_headers,
    )
    assert rolled_back.status_code == 200, rolled_back.text
    assert rolled_back.json()["status"] == "rolled_back"
