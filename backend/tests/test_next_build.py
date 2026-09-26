from __future__ import annotations

from datetime import UTC, datetime, date

from fastapi.testclient import TestClient

from app.schemas import CandidateInput, RiskProfile
from app.services.decision_engine import decision_engine
from app.services.mlb_provider import player_headshot_url, team_logo_url
from app.services.team_art import logo_for_play, team_logo


def _analysis(client: TestClient, headers: dict[str, str], sport: str = "mlb") -> dict:
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


def test_demo_slate_includes_sport_graphics(client: TestClient, auth_headers: dict[str, str]) -> None:
    slate = client.get(
        "/api/v1/sports/slate",
        params={"sport": "mlb", "date": str(date.today())},
        headers=auth_headers,
    )
    assert slate.status_code == 200
    candidates = slate.json()["candidates"]
    assert any(item.get("team_image_url") for item in candidates)
    assert any(item.get("image_url") for item in candidates)


def test_mlb_and_wnba_logo_helpers() -> None:
    assert player_headshot_url(123456).endswith("people/123456/headshot/silo/current")
    assert team_logo_url(147) == "https://midfield.mlbstatic.com/v1/team/147/spots/96"
    assert "ind.png" in (team_logo("wnba", "Indiana Fever") or "")
    assert "kc.png" in (logo_for_play("nfl", "Kansas City Chiefs ML", "Bills @ Chiefs") or "")


def test_learned_weights_nudge_adjusted_probability() -> None:
    now = datetime.now(UTC)
    payload = CandidateInput(
        candidate_id="candidate-learn",
        event_id="event-learn",
        event_name="Demo Event",
        sport="mlb",
        league="MLB",
        start_time=now,
        market_type="moneyline",
        selection="Demo Metro ML",
        american_odds=-110,
        estimated_probability=0.64,
        variance=0.22,
        data_quality=0.95,
        data_source="TEST",
        source_timestamp=now,
        source_status={"market": "confirmed"},
        schedule_verified=True,
        universe_scan_complete=True,
        current_form_verified=True,
        l5_l10_verified=True,
        lineup_confirmed=True,
        injuries_verified=True,
        weather_verified=True,
        starter_confirmed=True,
        motivation_rotation_verified=True,
        home_away_verified=True,
        market_movement_verified=True,
        sport_specific_sweep_complete=True,
        thesis_key="learn-ml",
        script_key="learn-script",
    )
    base = decision_engine.evaluate(payload, RiskProfile.balanced)
    boosted = decision_engine.evaluate(
        payload,
        RiskProfile.balanced,
        learned_weights={"market_value": 0.20},
    )
    assert boosted.adjusted_probability > base.adjusted_probability


def test_every_grade_micro_learns_and_pulse_counts(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    analysis = _analysis(client, auth_headers)
    pick = analysis["ranked_picks"][0]
    graded = client.post(
        "/api/v1/sports/result",
        json={
            "recommendation_id": pick["id"],
            "outcome": "LOSS",
            "stake": "1.00",
            "profit_loss": "-1.00",
            "process_outcome_class": "BAD_PROCESS_BAD_OUTCOME",
            "error_category": "BAD_PRICE",
            "process_grade": "D",
            "variance_grade": "MEDIUM",
            "root_cause_tags": ["PRICE_DISCIPLINE"],
            "lesson": "Price was the miss. Train immediately.",
        },
        headers=auth_headers,
    )
    assert graded.status_code == 201, graded.text
    pulse = client.get("/api/v1/learning/pulse", headers=auth_headers)
    assert pulse.status_code == 200, pulse.text
    body = pulse.json()
    assert body["protocol_runs"] >= 1
    assert body["graded_results"] >= 1
    assert body["micro_updates"] >= 1
    assert any(shift["feature_name"] == "market_value" for shift in body["active_shifts"])
    assert "Trained on" in body["headline"]


def test_ticket_is_editable_with_alternatives_and_custom_save(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    analysis = _analysis(client, auth_headers)
    ranked = analysis["ranked_picks"]
    assert len(ranked) >= 3
    elite = client.post(
        "/api/v1/sports/build-ticket",
        json={
            "analysis_id": analysis["analysis_id"],
            "max_legs": 5,
            "min_rating": 0,
            "risk_profile": "balanced",
        },
        headers=auth_headers,
    )
    assert elite.status_code == 200, elite.text
    elite_ids = elite.json()["cards"]["elite_two"]["recommendation_ids"]
    ticket = client.post(
        "/api/v1/tickets",
        json={
            "ticket_type": "elite_two",
            "label": "YWP Elite 2",
            "recommendation_ids": elite_ids,
            "stake": "10.00",
        },
        headers=auth_headers,
    )
    assert ticket.status_code == 201, ticket.text
    ticket_id = ticket.json()["id"]
    assert any(
        leg.get("team_image_url") or leg.get("image_url") for leg in ticket.json()["legs"]
    )

    alternatives = client.get(f"/api/v1/tickets/{ticket_id}/alternatives", headers=auth_headers)
    assert alternatives.status_code == 200, alternatives.text
    alts = alternatives.json()
    assert alts, "qualified leftover plays should be offered for editing"
    added = client.post(
        f"/api/v1/tickets/{ticket_id}/legs",
        json={"recommendation_id": alts[0]["id"]},
        headers=auth_headers,
    )
    assert added.status_code == 201, added.text
    assert len(added.json()["legs"]) == len(elite_ids) + 1

    leftover = client.get(f"/api/v1/tickets/{ticket_id}/alternatives", headers=auth_headers).json()
    if leftover:
        swapped = client.patch(
            f"/api/v1/tickets/{ticket_id}/legs/{added.json()['legs'][0]['id']}",
            json={"action": "replace", "replacement_recommendation_id": leftover[0]["id"]},
            headers=auth_headers,
        )
        assert swapped.status_code == 200, swapped.text

    used = set(elite_ids) | {alts[0]["id"]}
    custom_ids = [item["id"] for item in ranked if item["id"] not in used][:2]
    if len(custom_ids) < 2:
        custom_ids = [item["id"] for item in ranked[:2]]
    custom = client.post(
        "/api/v1/tickets",
        json={
            "ticket_type": "custom",
            "label": "My custom two",
            "recommendation_ids": custom_ids,
            "stake": "8.00",
            "intentional_correlation": True,
            "intentional_thesis_exposure": True,
        },
        headers=auth_headers,
    )
    assert custom.status_code == 201, custom.text
    assert custom.json()["ticket_type"] == "custom"
    assert len(custom.json()["legs"]) == len(custom_ids)
