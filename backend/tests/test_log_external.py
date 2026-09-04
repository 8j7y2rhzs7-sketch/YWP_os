from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient


def test_log_external_strikeout_feeds_learning(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/sports/log-external",
        json={
            "sport": "mlb",
            "league": "MLB",
            "slate_date": str(date.today()),
            "event_name": "Cardinals @ Dodgers",
            "market_type": "player_strikeouts_over",
            "selection": "Michael Wacha Over 4.5 Strikeouts",
            "line": "4.5",
            "american_odds": -140,
            "outcome": "WIN",
            "actual_value": "7",
            "final_score": "Wacha 7 Ks",
            "stake": "0.00",
            "profit_loss": "0.00",
            "process_grade": "B",
            "variance_grade": "MEDIUM",
            "player_key": "michael_wacha",
            "lesson": "Strikeout ticket never locked in-app; logged from sportsbook.",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["outcome"] == "WIN"
    assert body["market_type"] == "player_strikeouts_over"
    assert body["result"]["actual_value"] == "7.000"

    pulse = client.get("/api/v1/learning/pulse", headers=auth_headers)
    assert pulse.status_code == 200
    assert pulse.json()["graded_results"] >= 1

    performance = client.get("/api/v1/learning/performance", headers=auth_headers)
    assert performance.status_code == 200
    assert performance.json()["settled"] >= 1
    assert performance.json()["wins"] >= 1
