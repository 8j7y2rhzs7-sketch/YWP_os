"""Ops Heal — product health contracts + allowlisted remediations."""

from __future__ import annotations

from datetime import datetime, timezone

from app.hive.models import HiveLearningEvent
from app.models import ErrorReport, LearningEvent, User
from app.services.ops_heal import (
    ALLOWED_REMEDIATIONS,
    RemediationResult,
    classify_error_for_heal,
    latest_ops_heal_status,
    list_ops_heal_cycles,
    run_ops_heal_cycle,
)


def _user(db) -> User:
    row = User(
        email="ops-heal@ywp-os.com",
        password_hash="x",
        name="Ops Heal",
        timezone="America/New_York",
        role="user",
        subscription_status="active",
    )
    db.add(row)
    db.flush()
    return row


def _ok(remediation_id: str, **evidence) -> RemediationResult:
    return RemediationResult(
        remediation_id=remediation_id,
        ok=True,
        detail=f"mocked {remediation_id}",
        evidence=evidence,
    )


def test_classify_error_maps_board_and_forge() -> None:
    board = classify_error_for_heal("Internal Server Error", "Decision Board")
    assert "ack_error_reports" in board
    assert "run_settle_day" in board
    assert all(r in ALLOWED_REMEDIATIONS for r in board)

    forge = classify_error_for_heal("STANDING BY forever", "Day Forge")
    assert "probe_day_forge" in forge

    pending = classify_error_for_heal("74 pending sync", "Learning")
    assert "sync_hive_outcomes" in pending
    assert "run_settle_day" in pending


def test_healthy_cycle_persists_and_lists(db_session, monkeypatch) -> None:
    user = _user(db_session)

    def _boom(**_):
        raise AssertionError("should not settle when healthy")

    monkeypatch.setattr("app.services.ops_heal._rem_run_settle_day", _boom)

    cycle = run_ops_heal_cycle(
        db=db_session,
        user_id=user.id,
        timezone_name=user.timezone,
        trigger="test",
        apply=True,
    )
    assert cycle["bot"] == "ops_heal"
    assert cycle["status"] == "healthy"
    assert cycle["planned_remediations"] == []
    assert cycle["applied_remediations"] == []
    ids = {c["contract_id"] for c in cycle["contracts"]}
    assert {
        "day_forge_not_frozen",
        "decision_board_errors",
        "hive_pending_drain",
        "settlement_coverage_gaps",
    } <= ids
    assert all(c["ok"] for c in cycle["contracts"])

    listed = list_ops_heal_cycles(db=db_session, limit=5)
    assert len(listed) == 1
    assert listed[0]["status"] == "healthy"

    status = latest_ops_heal_status(db=db_session)
    assert status["status"] == "healthy"
    assert status["bot"] == "ops_heal"


def test_board_errors_trigger_allowlisted_remediations(db_session, monkeypatch) -> None:
    user = _user(db_session)
    db_session.add(
        ErrorReport(
            user_id=user.id,
            category="crash",
            message="Internal Server Error after analyze",
            screen="Decision Board",
            status="open",
        )
    )
    db_session.flush()

    called: list[str] = []

    monkeypatch.setattr(
        "app.services.ops_heal._rem_run_settle_day",
        lambda **_: called.append("run_settle_day") or _ok("run_settle_day", items=0),
    )
    monkeypatch.setattr(
        "app.services.ops_heal._rem_sync_hive",
        lambda **_: called.append("sync_hive_outcomes") or _ok("sync_hive_outcomes", updated=0),
    )

    cycle = run_ops_heal_cycle(
        db=db_session,
        user_id=user.id,
        timezone_name=user.timezone,
        trigger="test_board",
        apply=True,
    )
    assert cycle["status"] == "critical"
    assert "ack_error_reports" in cycle["planned_remediations"]
    assert "run_settle_day" in cycle["planned_remediations"]
    assert "run_settle_day" in called
    assert "sync_hive_outcomes" in called

    applied_ids = [r["remediation_id"] for r in cycle["applied_remediations"]]
    assert "ack_error_reports" in applied_ids

    report = db_session.query(ErrorReport).one()
    assert report.status == "triaged_by_ops_heal"


def test_hive_pending_drain_warns_and_plans_settle(db_session, monkeypatch) -> None:
    user = _user(db_session)
    now = datetime.now(timezone.utc)
    for i in range(22):
        db_session.add(
            HiveLearningEvent(
                idempotency_key=f"ops-pending-{i}",
                contributor_key="anon-test",
                source_recommendation_id=f"rec-{i}",
                sport="mlb",
                league="MLB",
                event_id=f"ev-{i}",
                event_start_at=now,
                market="moneyline",
                market_scope="full_game",
                selection="A",
                model_probability=0.55,
                quality_score=70.0,
                model_version="test",
                protocol_version="ywp",
                evidence_version="e",
                data_quality=0.8,
                feature_flags={},
                outcome=None,
            )
        )
    db_session.flush()

    monkeypatch.setattr(
        "app.services.ops_heal._rem_run_settle_day",
        lambda **_: _ok("run_settle_day"),
    )
    monkeypatch.setattr(
        "app.services.ops_heal._rem_sync_hive",
        lambda **_: _ok("sync_hive_outcomes"),
    )

    cycle = run_ops_heal_cycle(
        db=db_session,
        user_id=user.id,
        trigger="test_pending",
        apply=True,
    )
    pending_c = next(c for c in cycle["contracts"] if c["contract_id"] == "hive_pending_drain")
    assert pending_c["ok"] is False
    assert "run_settle_day" in cycle["planned_remediations"]
    assert cycle["status"] in {"degraded", "critical"}


def test_observe_only_skips_apply(db_session) -> None:
    user = _user(db_session)
    db_session.add(
        ErrorReport(
            user_id=user.id,
            category="crash",
            message="Internal Server Error",
            screen="analysis",
            status="open",
        )
    )
    db_session.flush()

    cycle = run_ops_heal_cycle(
        db=db_session,
        user_id=user.id,
        trigger="observe",
        apply=False,
    )
    assert cycle["planned_remediations"]
    assert cycle["applied_remediations"] == []
    assert db_session.query(ErrorReport).one().status == "open"


def test_coverage_gaps_contract(db_session, monkeypatch) -> None:
    user = _user(db_session)
    now = datetime.now(timezone.utc)
    for i in range(12):
        db_session.add(
            LearningEvent(
                event_type="SETTLEMENT_COVERAGE_GAP",
                sport="kbo",
                market_type="moneyline",
                analysis={"detail": f"gap-{i}"},
                created_at=now,
            )
        )
    db_session.flush()

    monkeypatch.setattr(
        "app.services.ops_heal._rem_run_settle_day",
        lambda **_: _ok("run_settle_day"),
    )
    monkeypatch.setattr(
        "app.services.ops_heal._rem_record_gaps",
        lambda **_: _ok("record_coverage_gaps", gap_count=12),
    )

    cycle = run_ops_heal_cycle(
        db=db_session,
        user_id=user.id,
        trigger="gaps",
        apply=True,
    )
    gaps_c = next(c for c in cycle["contracts"] if c["contract_id"] == "settlement_coverage_gaps")
    assert gaps_c["ok"] is False
    assert "record_coverage_gaps" in cycle["planned_remediations"]


def test_ops_heal_api_endpoints(client, auth_headers, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.ops_heal._rem_run_settle_day",
        lambda **_: _ok("run_settle_day"),
    )

    idle = client.get("/api/v1/ops-heal/status", headers=auth_headers)
    assert idle.status_code == 200
    assert idle.json()["status"] == "idle"
    assert idle.json().get("proposals_pending", 0) == 0

    ran = client.post("/api/v1/ops-heal/run?apply=true", headers=auth_headers)
    assert ran.status_code == 200
    body = ran.json()
    assert body["bot"] == "ops_heal"
    assert "contracts" in body
    assert "proposals_pending" in body

    status = client.get("/api/v1/ops-heal/status", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["status"] in {"healthy", "degraded", "critical"}

    cycles = client.get("/api/v1/ops-heal/cycles?limit=5", headers=auth_headers)
    assert cycles.status_code == 200
    assert cycles.json()["bot"] == "ops_heal"
    assert len(cycles.json()["cycles"]) >= 1


def test_improvement_proposals_collect_analyze_and_human_review(db_session, monkeypatch) -> None:
    from app.services.ops_heal import list_ops_heal_proposals, review_ops_heal_proposal

    user = _user(db_session)
    db_session.add(
        ErrorReport(
            user_id=user.id,
            category="crash",
            message="Internal Server Error after analyze",
            screen="Decision Board",
            status="open",
        )
    )
    db_session.add(
        ErrorReport(
            user_id=user.id,
            category="crash",
            message="Internal Server Error again",
            screen="Decision Board",
            status="open",
        )
    )
    db_session.flush()

    monkeypatch.setattr(
        "app.services.ops_heal._rem_run_settle_day",
        lambda **_: _ok("run_settle_day"),
    )
    monkeypatch.setattr(
        "app.services.ops_heal._rem_sync_hive",
        lambda **_: _ok("sync_hive_outcomes"),
    )

    cycle = run_ops_heal_cycle(
        db=db_session,
        user_id=user.id,
        trigger="test_proposals",
        apply=True,
    )
    assert cycle["proposals_pending"] >= 1
    assert cycle["proposals_drafted"]

    pending = list_ops_heal_proposals(db=db_session, status="pending", limit=20)
    assert pending
    boardish = [p for p in pending if "fingerprint" in p and "decision_board" in str(p.get("fingerprint"))]
    assert boardish or any("error_cluster" in str(p.get("fingerprint")) for p in pending)
    for row in pending:
        assert row["status"] == "pending"
        assert row.get("recommended_change")
        assert row.get("implements_when") == "human_checks_in"

    # Second cycle refreshes sightings instead of duplicating fingerprints.
    before_count = len(pending)
    run_ops_heal_cycle(
        db=db_session,
        user_id=user.id,
        trigger="test_proposals_again",
        apply=True,
    )
    again = list_ops_heal_proposals(db=db_session, status="pending", limit=40)
    assert len(again) == before_count
    assert any(int(p.get("sightings") or 1) >= 2 for p in again)

    target = again[0]
    reviewed = review_ops_heal_proposal(
        db=db_session,
        proposal_id=target["id"],
        action="implemented",
        reviewer_user_id=user.id,
        note="shipped in check-in",
    )
    assert reviewed["status"] == "implemented"
    assert reviewed["review_note"] == "shipped in check-in"
    still_pending = list_ops_heal_proposals(db=db_session, status="pending", limit=40)
    assert all(p["id"] != target["id"] for p in still_pending)


def test_ops_heal_proposals_api_review(client, auth_headers, monkeypatch) -> None:
    from app.core.database import SessionLocal
    from app.models import ErrorReport as ER
    from app.models import User as U

    monkeypatch.setattr(
        "app.services.ops_heal._rem_run_settle_day",
        lambda **_: _ok("run_settle_day"),
    )
    monkeypatch.setattr(
        "app.services.ops_heal._rem_sync_hive",
        lambda **_: _ok("sync_hive_outcomes"),
    )

    db = SessionLocal()
    try:
        user = db.query(U).filter(U.email == "owner@ywp-os.com").one()
        for i in range(2):
            db.add(
                ER(
                    user_id=user.id,
                    category="crash",
                    message="Internal Server Error",
                    screen="Decision Board",
                    status="open",
                )
            )
        db.commit()
    finally:
        db.close()

    ran = client.post("/api/v1/ops-heal/run", headers=auth_headers)
    assert ran.status_code == 200

    listed = client.get("/api/v1/ops-heal/proposals?status=pending", headers=auth_headers)
    assert listed.status_code == 200
    proposals = listed.json()["proposals"]
    assert proposals
    proposal_id = proposals[0]["id"]

    reviewed = client.post(
        f"/api/v1/ops-heal/proposals/{proposal_id}/review",
        headers=auth_headers,
        json={"action": "dismissed", "note": "not this week"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "dismissed"

    leftover = client.get("/api/v1/ops-heal/proposals?status=pending", headers=auth_headers)
    assert all(p["id"] != proposal_id for p in leftover.json()["proposals"])
