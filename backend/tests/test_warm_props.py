"""Chunked prop warm — give research time without a single 30s+ request."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from app.services.ops_evidence import process_for_path


def _prop(i: int, *, source: str = "market_implied") -> dict:
    now = datetime(2026, 9, 22, 20, 0, tzinfo=UTC)
    return {
        "candidate_id": f"wnba-prop-{i}",
        "event_id": "game-1",
        "event_name": "Indiana Fever @ Las Vegas Aces",
        "sport": "wnba",
        "league": "WNBA",
        "start_time": now.isoformat().replace("+00:00", "Z"),
        "home_team": "Las Vegas Aces",
        "away_team": "Indiana Fever",
        "market_type": "player_points_over",
        "selection": f"Player {i} Over 12.5 points",
        "line": "12.5",
        "american_odds": -110,
        "estimated_probability": 0.52,
        "probability_source": source,
        "variance": 0.4,
        "data_quality": 0.4 if source == "market_implied" else 0.75,
        "data_source": (
            "ESPN_PLAYER_PROP_MODEL" if source == "model" else "THE_ODDS_API_BOARD"
        ),
        "source_timestamp": now.isoformat().replace("+00:00", "Z"),
        "missing_fields": (
            ["independent_model_projection"] if source == "market_implied" else []
        ),
        "source_status": {"market": "confirmed", "schedule": "confirmed"},
        "schedule_verified": True,
        "market_movement_verified": True,
        "reason_codes": ["SPORTSBOOK_MENU"],
        "thesis_key": f"t-{i}",
        "script_key": f"s-{i}",
    }


def test_warm_props_upgrades_and_reports_coverage(client, auth_headers) -> None:
    pending = [_prop(i) for i in range(3)]

    def fake_enrich(rows, slate_date=None, budget_seconds=14.0):
        out = []
        for i, row in enumerate(rows):
            if i == 0:
                out.append(
                    row.model_copy(
                        update={
                            "probability_source": "model",
                            "data_source": "ESPN_PLAYER_PROP_MODEL",
                            "data_quality": 0.8,
                            "missing_fields": [],
                        }
                    )
                )
            else:
                out.append(row)
        return out

    with patch(
        "app.services.player_prop_research.enrich_player_prop_candidates",
        side_effect=fake_enrich,
    ):
        response = client.post(
            "/api/v1/sports/warm-props",
            json={
                "sport": "wnba",
                "date": "2026-09-22",
                "candidates": pending,
                "budget_seconds": 18,
            },
            headers=auth_headers,
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["prop_total"] == 3
    assert body["prop_modeled"] == 1
    assert body["prop_pending"] == 2
    assert body["enriched_this_pass"] == 1
    assert body["ready"] is False
    assert body["candidates"][0]["probability_source"] == "model"


def test_warm_props_ready_when_no_pending(client, auth_headers) -> None:
    rows = [_prop(i, source="model") for i in range(2)]
    response = client.post(
        "/api/v1/sports/warm-props",
        json={"sport": "wnba", "date": "2026-09-22", "candidates": rows},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ready"] is True
    assert body["prop_pending"] == 0
    assert body["coverage_pct"] == 100.0


def test_process_for_path_includes_warm_props() -> None:
    assert process_for_path("/api/v1/sports/warm-props") == "prop_research"
