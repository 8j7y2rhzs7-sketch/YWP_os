from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def _analysis(client: TestClient, headers: dict[str, str], sport: str) -> dict:
    slate = client.get(
        "/api/v1/sports/slate",
        params={"sport": sport, "date": str(date.today())},
        headers=headers,
    )
    assert slate.status_code == 200, slate.text
    response = client.post(
        "/api/v1/sports/analyze",
        json={
            "sport": sport,
            "date": str(date.today()),
            "mode": "pregame",
            "user_risk_profile": "balanced",
            "candidates": slate.json()["candidates"],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health_and_authenticated_full_flow(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["protocol_version"] == "2026.09.03"

    analysis = _analysis(client, auth_headers, "mlb")
    assert analysis["data_quality_summary"]["protocol_status"] == "DOUBLE_CLEARED"
    reason_codes = {code for item in analysis["stay_away"] for code in item["reason_codes"]}
    assert "FIRST_START_BACK_EXCLUSION" in reason_codes
    assert "LOW_TOTAL_TWO_PATH_GATE_FAILED" in reason_codes
    assert "FILLER_LEG_TAX" in reason_codes

    cards_response = client.post(
        "/api/v1/sports/build-ticket",
        json={
            "analysis_id": analysis["analysis_id"],
            "max_legs": 5,
            "min_rating": 0,
            "risk_profile": "balanced",
        },
        headers=auth_headers,
    )
    assert cards_response.status_code == 200, cards_response.text
    payload = cards_response.json()
    assert payload["official_pass"] is False
    cards = payload["cards"]
    assert "max_bet" in cards
    assert cards["max_bet"]["recommendation_ids"]
    # Multi-leg templates are omitted when too few plays survive gates.
    for key, needed in {
        "elite_two": 2,
        "core_3": 3,
        "core_4": 4,
        "core_5": 5,
        "ticket_a": 2,
    }.items():
        if key in cards:
            assert len(cards[key]["recommendation_ids"]) >= needed

    recommendation_ids = (
        cards.get("elite_two", cards["max_bet"])["recommendation_ids"]
    )
    ticket_response = client.post(
        "/api/v1/tickets",
        json={
            "ticket_type": "elite_two",
            "label": "YWP Elite 2",
            "recommendation_ids": recommendation_ids,
            "stake": "10.00",
        },
        headers=auth_headers,
    )
    assert ticket_response.status_code == 201, ticket_response.text
    ticket_id = ticket_response.json()["id"]

    lock = client.post(
        f"/api/v1/tickets/{ticket_id}/lock-check",
        json={"updates": []},
        headers=auth_headers,
    )
    assert lock.status_code == 200, lock.text
    assert lock.json()["lock_status"] == "LOCKED"

    placed = client.post(f"/api/v1/tickets/{ticket_id}/place", headers=auth_headers)
    assert placed.status_code == 200
    assert placed.json()["status"] == "placed"

    result = client.post(
        "/api/v1/sports/result",
        json={
            "recommendation_id": recommendation_ids[0],
            "outcome": "LOSS",
            "stake": "5.00",
            "profit_loss": "-5.00",
            "actual_value": "4.5",
            "bet_line": "5.5",
            "killed_ticket": True,
            "last_losing_leg": True,
            "process_outcome_class": "GOOD_PROCESS_BAD_OUTCOME",
            "error_category": "VARIANCE",
            "process_grade": "A",
            "variance_grade": "HIGH",
            "root_cause_tags": ["MISS_BY_ONE"],
            "lesson": "The process was sound, but the realized margin missed by one.",
            "cashout_action": "HOLD",
            "cashout_offer": "7.50",
            "cashout_reason": (
                "Verified thesis remained intact and the offer underpriced fair value."
            ),
        },
        headers=auth_headers,
    )
    assert result.status_code == 201, result.text
    assert result.json()["miss_distance"] == "-1.000"
    assert result.json()["cashout_action"] == "HOLD"
    assert result.json()["cashout_offer"] == "7.50"

    graded_ticket = client.get(f"/api/v1/tickets/{ticket_id}", headers=auth_headers)
    assert graded_ticket.status_code == 200
    graded_leg = next(
        leg
        for leg in graded_ticket.json()["legs"]
        if leg["recommendation_id"] == recommendation_ids[0]
    )
    assert graded_leg["outcome"] == "LOSS"

    miss_report = client.get("/api/v1/learning/miss-by-one", headers=auth_headers)
    assert miss_report.status_code == 200
    assert miss_report.json()["near_miss_results"] == 1
    assert miss_report.json()["tickets_killed_by_near_miss"] == 1


def test_recommendations_are_user_scoped(client: TestClient, auth_headers: dict[str, str]) -> None:
    analysis = _analysis(client, auth_headers, "soccer")
    recommendation_id = (analysis["ranked_picks"] + analysis["stay_away"])[0]["id"]
    second = client.post(
        "/api/v1/auth/register",
        json={
            "email": "second@ywp-os.com",
            "password": "AnotherStrong!2026",
            "name": "Second User",
        },
    )
    second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}
    forbidden = client.get(
        f"/api/v1/sports/recommendations/{recommendation_id}",
        headers=second_headers,
    )
    assert forbidden.status_code == 404
