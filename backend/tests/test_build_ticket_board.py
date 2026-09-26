"""Decision Board build-ticket must stay fast on large prop analyses."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from app.models import Recommendation, User
from app.services.ticket_builder import build_cards


def _rec(
    db_session,
    user: User,
    *,
    analysis_id: str,
    rank: int,
    decision: str,
    selection: str = "Player Under 3.5 rebounds",
) -> Recommendation:
    snap = {
        "probability_source": "model" if decision in {"PLAY", "LEAN"} else "market_implied",
        "game_status": "PRE_GAME",
        "market_status": "OPEN",
        "start_time": datetime.now(UTC).isoformat(),
        # Broken timestamp shapes must not 500 RecommendationOut.
        "price_timestamp": "not-a-real-timestamp" if rank == 1 else datetime.now(UTC).isoformat(),
    }
    row = Recommendation(
        analysis_id=analysis_id,
        created_by_user_id=user.id,
        candidate_id=f"cand-{rank}-{uuid4().hex[:8]}",
        event_id=f"event-{rank % 12}",
        event_name="Toronto Tempo @ Chicago Sky",
        sport="wnba",
        league="WNBA",
        slate_date=date.today(),
        mode="pregame",
        market_type="player_rebounds",
        market_period="full_game",
        selection=f"{selection} #{rank}",
        line=Decimal("3.5"),
        american_odds=114,
        estimated_probability=Decimal("0.450000"),
        implied_probability=Decimal("0.467290"),
        adjusted_probability=Decimal("0.450000"),
        edge=Decimal("0.050000"),
        expected_value=Decimal("0.040000"),
        confidence_score=90 if decision == "PLAY" else 50,
        ywp_rating=Decimal("8.30") if decision == "PLAY" else Decimal("5.00"),
        vision_score=Decimal("7.00"),
        miss_by_one_risk=Decimal("0.2000"),
        reliability=Decimal("0.7000"),
        stability=Decimal("0.7000"),
        variance=Decimal("0.2800"),
        data_quality=Decimal("0.7300"),
        risk="medium",
        risk_tier="Moderate",
        variance_rating="Medium",
        edge_class="Edge",
        expected_value_label="Positive",
        suggested_stake_pct=Decimal("0.0100"),
        decision=decision,
        recommendation_tier="cash_builder" if decision == "PLAY" else "support",
        rank=rank,
        reason_codes=["OK"] if decision == "PLAY" else ["SKIP"],
        reasoning_summary="test",
        warnings=[],
        safer_alternative=None,
        higher_upside=None,
        invalidation_conditions=[],
        live_trigger=None,
        hedge=None,
        quick_cash=False,
        chain_reaction_key=None,
        thesis_key=f"thesis-{rank % 30:03d}",
        script_key=f"script-{rank % 20:03d}",
        player_key=f"player-{rank}",
        data_source="TEST",
        source_timestamp=datetime.now(UTC),
        model_version="ywp-sports-v3.1.0",
        protocol_version="2026.09.03",
        input_hash=f"hash-{rank}",
        snapshot=snap,
    )
    db_session.add(row)
    return row


def test_build_cards_tolerates_null_script_alignment() -> None:
    """PARTIAL WNBA props often ship snapshot.script_alignment=null — must not 500."""
    from datetime import UTC, date, datetime
    from decimal import Decimal
    from uuid import uuid4

    from app.models import Recommendation

    plays = []
    for i in range(27):
        plays.append(
            Recommendation(
                id=str(uuid4()),
                analysis_id=str(uuid4()),
                created_by_user_id=str(uuid4()),
                candidate_id=f"cand-{i}",
                event_id=f"event-{i % 8}",
                event_name="Sun @ Dream",
                sport="wnba",
                league="WNBA",
                slate_date=date.today(),
                mode="pregame",
                market_type="player_points_over",
                market_period="full_game",
                selection=f"Player {i} Over 12.5 points",
                line=Decimal("12.5"),
                american_odds=-110,
                estimated_probability=Decimal("0.550000"),
                implied_probability=Decimal("0.523810"),
                adjusted_probability=Decimal("0.550000"),
                edge=Decimal("0.040000"),
                expected_value=Decimal("0.030000"),
                confidence_score=90,
                ywp_rating=Decimal("8.20"),
                vision_score=Decimal("7.00"),
                miss_by_one_risk=Decimal("0.2000"),
                reliability=Decimal("0.7000"),
                stability=Decimal("0.7000"),
                variance=Decimal("0.2800"),
                data_quality=Decimal("0.7300"),
                risk="medium",
                risk_tier="Moderate",
                variance_rating="Medium",
                edge_class="Edge",
                expected_value_label="Positive",
                suggested_stake_pct=Decimal("0.0100"),
                decision="PLAY",
                recommendation_tier="cash_builder",
                rank=i + 1,
                reason_codes=["OK"],
                reasoning_summary="test",
                warnings=[],
                safer_alternative=None,
                higher_upside=None,
                invalidation_conditions=[],
                live_trigger=None,
                hedge=None,
                quick_cash=False,
                chain_reaction_key=None,
                thesis_key=f"thesis-{i}",
                script_key=f"script-{i}",
                player_key=f"player-{i}",
                data_source="ESPN_PLAYER_PROP_MODEL",
                source_timestamp=datetime.now(UTC),
                model_version="ywp-sports-v3.1.0",
                protocol_version="2026.09.03",
                input_hash=f"hash-{i}",
                created_at=datetime.now(UTC),
                snapshot={
                    "probability_source": "model",
                    "game_status": "PRE_GAME",
                    "market_status": "OPEN",
                    "script_alignment": None,
                    "start_time": datetime.now(UTC).isoformat(),
                },
            )
        )
    cards, quarantined = build_cards(plays, max_legs=5, min_rating=6.5)
    assert "max_bet" in cards
    assert cards["max_bet"].legs
    assert isinstance(quarantined, list)


def test_build_cards_tolerates_bad_price_timestamp(db_session, client, auth_headers) -> None:
    me = client.get("/api/v1/users/me", headers=auth_headers)
    assert me.status_code == 200, me.text
    from app.models import User

    user = db_session.get(User, me.json()["id"])
    assert user is not None
    analysis_id = str(uuid4())
    plays = [
        _rec(db_session, user, analysis_id=analysis_id, rank=i + 1, decision="PLAY")
        for i in range(5)
    ]
    db_session.commit()
    cards, quarantined = build_cards(plays, max_legs=5, min_rating=6.5)
    assert "max_bet" in cards
    assert cards["max_bet"].legs
    assert isinstance(quarantined, list)


def test_build_ticket_skips_bulk_stay_away_on_large_board(
    client, auth_headers, db_session
) -> None:
    me = client.get("/api/v1/users/me", headers=auth_headers)
    assert me.status_code == 200, me.text
    from app.models import User

    user = db_session.get(User, me.json()["id"])
    assert user is not None
    analysis_id = str(uuid4())
    for i in range(27):
        _rec(db_session, user, analysis_id=analysis_id, rank=i + 1, decision="PLAY")
    for i in range(27, 120):
        _rec(db_session, user, analysis_id=analysis_id, rank=i + 1, decision="SKIP")
    db_session.commit()

    response = client.post(
        "/api/v1/sports/build-ticket",
        json={
            "analysis_id": analysis_id,
            "max_legs": 5,
            "min_rating": 6.5,
            "risk_profile": "balanced",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["official_pass"] is False
    assert body["stay_away"] == []
    assert body["cards"]
    assert "max_bet" in body["cards"]
