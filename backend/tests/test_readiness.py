from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.api import sports as sports_mod


def test_demo_slate_is_labeled_demo(client: TestClient, auth_headers: dict[str, str]) -> None:
    slate = client.get(
        "/api/v1/sports/slate",
        params={"sport": "mlb", "date": str(date.today())},
        headers=auth_headers,
    )
    assert slate.status_code == 200, slate.text
    payload = slate.json()
    assert payload["mode"] == "demo"
    assert payload["readiness"] == "DEMO"
    assert payload["verification_summary"]["demo_count"] == len(payload["candidates"])
    assert all(item["probability_source"] == "demo" for item in payload["candidates"])

    analysis = client.post(
        "/api/v1/sports/analyze",
        json={
            "sport": "mlb",
            "date": str(date.today()),
            "mode": "pregame",
            "user_risk_profile": "balanced",
            "candidates": payload["candidates"],
        },
        headers=auth_headers,
    )
    assert analysis.status_code == 201, analysis.text
    body = analysis.json()
    assert body["readiness"] == "DEMO"
    assert "official_pass" in body["data_quality_summary"]
    assert body["data_quality_summary"]["official_pass_count"] == len(body["ranked_picks"])
    assert body["data_quality_summary"]["official_skip_count"] == len(body["stay_away"])


def test_production_does_not_silently_substitute_demo_slate(
    client: TestClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(sports_mod.settings, "demo_mode", False)
    monkeypatch.setattr(sports_mod.settings, "odds_api_key", None)

    def _fail(_slate_date: date):
        raise RuntimeError("provider down")

    monkeypatch.setattr(sports_mod, "live_mlb_slate", _fail)
    response = client.get(
        "/api/v1/sports/slate",
        params={"sport": "mlb", "date": str(date.today())},
        headers=auth_headers,
    )
    assert response.status_code == 503, response.text
    assert "will not silently substitute" in response.json()["detail"]
