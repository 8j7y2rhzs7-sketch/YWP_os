"""Full-app process evidence collection for Ops Heal."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models import AuditLog, ErrorReport, LearningEvent, User
from app.services.ops_evidence import (
    APP_PROCESS_MOVEMENT,
    collect_all_process_evidence,
    persist_evidence_pack,
    process_for_path,
    proposals_from_process_evidence,
    record_app_movement,
    should_record_movement,
)
from app.services.ops_heal import run_ops_heal_cycle


def _user(db) -> User:
    row = User(
        email="evidence@ywp-os.com",
        password_hash="x",
        name="Evidence",
        timezone="America/New_York",
        role="user",
        subscription_status="active",
    )
    db.add(row)
    db.flush()
    return row


def test_process_for_path_covers_core_surfaces() -> None:
    assert process_for_path("/api/v1/sports/day-forge") == "day_forge"
    assert process_for_path("/api/v1/sports/analyze") == "analyze"
    assert process_for_path("/api/v1/sports/build-ticket") == "decision_board"
    assert process_for_path("/api/v1/tickets") == "tickets"
    assert process_for_path("/api/v1/learning/pulse") == "learning"
    assert process_for_path("/api/v1/hive/progress-reports") == "hive"
    assert process_for_path("/api/v1/ops-heal/run") == "ops_heal"
    assert process_for_path("/api/v1/errors") == "error_reports"


def test_should_record_skips_health_and_dedupes_gets() -> None:
    assert should_record_movement(method="GET", path="/api/v1/health", status_code=200) is False
    assert should_record_movement(method="POST", path="/api/v1/sports/analyze", status_code=201) is True
    assert should_record_movement(method="GET", path="/api/v1/sports/day-forge", status_code=500) is True
    first = should_record_movement(method="GET", path="/api/v1/sports/slate", status_code=200)
    second = should_record_movement(method="GET", path="/api/v1/sports/slate", status_code=200)
    assert first is True
    assert second is False


def test_collect_all_process_evidence_aggregates_streams(db_session) -> None:
    user = _user(db_session)
    record_app_movement(
        db_session,
        method="POST",
        path="/api/v1/sports/analyze",
        status_code=201,
        duration_ms=120.5,
        user_id=user.id,
    )
    record_app_movement(
        db_session,
        method="POST",
        path="/api/v1/sports/build-ticket",
        status_code=500,
        duration_ms=40.0,
        user_id=user.id,
    )
    db_session.add(
        LearningEvent(
            event_type="DAY_FORGE",
            sport="mlb",
            market_type="moneyline",
            analysis={"status": "cooking"},
        )
    )
    db_session.add(
        LearningEvent(
            event_type="TICKET_CREATED",
            sport="mlb",
            market_type="parlay",
            analysis={},
        )
    )
    db_session.add(
        AuditLog(
            user_id=user.id,
            action="TICKET_PLACED",
            entity_type="ticket",
            entity_id="t1",
            details={},
        )
    )
    db_session.add(
        ErrorReport(
            user_id=user.id,
            category="crash",
            message="Internal Server Error",
            screen="Decision Board",
            status="open",
        )
    )
    db_session.flush()

    pack = collect_all_process_evidence(db=db_session, user_id=user.id, hours=72)
    persist_evidence_pack(db=db_session, pack=pack)

    assert pack["summary"]["total_movements"] >= 5
    assert pack["summary"]["processes_active"] >= 3
    by_process = {row["process"]: row for row in pack["process_coverage"]}
    assert by_process["analyze"]["movements"] >= 1
    assert by_process["decision_board"]["errors"] >= 1
    assert by_process["day_forge"]["active"] is True
    assert by_process["tickets"]["active"] is True
    assert by_process["error_reports"]["active"] is True
    assert pack["streams"]["api_movements"]["failures"] >= 1

    movements = (
        db_session.query(LearningEvent)
        .filter(LearningEvent.event_type == APP_PROCESS_MOVEMENT)
        .all()
    )
    assert len(movements) >= 2

    drafts = proposals_from_process_evidence(pack)
    assert isinstance(drafts, list)
    # decision_board failure movement should surface a stabilize proposal
    assert any("decision_board" in str(d.get("fingerprint")) for d in drafts) or any(
        d.get("area") == "decision_board" for d in drafts
    )


def test_ops_heal_cycle_includes_full_process_evidence(db_session, monkeypatch) -> None:
    user = _user(db_session)
    for path, code in (
        ("/api/v1/sports/day-forge", 200),
        ("/api/v1/sports/analyze", 201),
        ("/api/v1/tickets", 201),
        ("/api/v1/sports/settle-day", 200),
        ("/api/v1/learning/pulse", 200),
    ):
        record_app_movement(
            db_session,
            method="POST" if "analyze" in path or path.endswith("tickets") else "GET",
            path=path,
            status_code=code,
            duration_ms=10,
            user_id=user.id,
        )
    db_session.flush()

    monkeypatch.setattr(
        "app.services.ops_heal._rem_run_settle_day",
        lambda **_: (__import__("app.services.ops_heal", fromlist=["RemediationResult"]).RemediationResult(
            remediation_id="run_settle_day", ok=True, detail="ok", evidence={}
        )),
    )

    cycle = run_ops_heal_cycle(
        db=db_session,
        user_id=user.id,
        trigger="evidence_test",
        apply=False,
    )
    assert "evidence" in cycle
    assert cycle["evidence"]["summary"]["total_movements"] >= 5
    assert cycle["evidence"]["summary"]["processes_active"] >= 3
    assert "Evidence:" in cycle["explanation"]


def test_ops_heal_evidence_api(client, auth_headers) -> None:
    listed = client.get("/api/v1/ops-heal/evidence", headers=auth_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["kind"] == "process_evidence" or "summary" in body
    assert "process_coverage" in body
    assert body["summary"]["processes_tracked"] >= 10
