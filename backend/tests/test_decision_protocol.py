"""October 2026 protocol baseline. Live 2026.09.03 cards are not rewritten here."""

from fastapi.testclient import TestClient

from app.services.decision_protocol import (
    PRIOR_PROTOCOL_VERSION,
    PROTOCOL_VERSION,
    FieldRecord,
    ProtocolConfig,
    build_abc,
    build_card,
    build_official_ticket,
    official_max_legs,
    validate_inputs,
)
from app.services.decision_protocol.settings import first_start_back_gate
from app.services.decision_protocol.states import DecisionState, EvidenceKind
from app.services.decision_protocol.tickets import QualifiedLeg
from app.services.decision_protocol.validation import CRITICAL_FIELDS


def _verified(name: str, value: object = "yes") -> FieldRecord:
    return FieldRecord(
        name=name,
        value=value,
        kind=EvidenceKind.VERIFIED,
        source="official",
        confirmed=True,
    )


def _critical() -> list[FieldRecord]:
    return [
        _verified("sport", "nfl"),
        _verified("event", "Steelers at Browns"),
        _verified("start_time", "2026-10-05T17:00:00Z"),
        _verified("identity", "Cleveland Browns"),
        _verified("market", "moneyline"),
    ]


def test_missing_identity_is_hold_and_nothing_is_invented() -> None:
    records = [record for record in _critical() if record.name != "identity"]
    records.append(
        FieldRecord(name="identity", value=None, kind=EvidenceKind.UNKNOWN, confirmed=False)
    )
    result = validate_inputs(records, sport_checks=())
    assert result.state is DecisionState.HOLD
    assert "identity" in result.missing
    assert result.fabricated is False
    assert all(record.value is None or record.name != "identity" for record in result.records)


def test_unconfirmed_fact_does_not_count() -> None:
    records = _critical()
    records[0] = FieldRecord(
        name="sport",
        value="nfl",
        kind=EvidenceKind.ESTIMATE,
        source="guess",
        confirmed=False,
    )
    result = validate_inputs(records, sport_checks=())
    assert result.state is DecisionState.HOLD
    assert "sport" in result.missing


def test_sport_checks_missing_are_hold() -> None:
    result = validate_inputs(_critical())
    assert result.state is DecisionState.HOLD
    assert "game_script" in result.missing


def test_verified_inputs_pass() -> None:
    checks = ("game_script", "matchup", "participation", "opportunity", "weather", "blowout_risk")
    records = _critical() + [_verified(name) for name in checks]
    result = validate_inputs(records)
    assert result.passed is True
    assert result.missing == ()


def test_blank_leg_cap_stays_at_two() -> None:
    assert official_max_legs(None) == 2
    assert official_max_legs(ProtocolConfig(official_max_legs=None)) == 2
    assert official_max_legs(ProtocolConfig(official_max_legs=5)) == 2
    assert official_max_legs(ProtocolConfig(official_max_legs=1)) == 1


def test_no_qualified_play_is_no_bet() -> None:
    ticket = build_official_ticket([QualifiedLeg("1", "a", DecisionState.SKIP, 0.9, "Skip me")])
    assert ticket.state is DecisionState.NO_BET
    assert ticket.legs == ()


def test_official_ticket_never_exceeds_two_legs() -> None:
    legs = [
        QualifiedLeg(str(index), f"p{index}", DecisionState.PLAY, 1 - index * 0.05, f"P{index}")
        for index in range(4)
    ]
    ticket = build_official_ticket(legs, config=ProtocolConfig(official_max_legs=5))
    assert len(ticket.legs) == 2
    assert ticket.legs[0].id == "0"
    assert ticket.legs[1].id == "1"


def test_weak_leg_is_removed_without_a_replacement() -> None:
    legs = [
        QualifiedLeg("strong", "a", DecisionState.PLAY, 0.9, "Strong"),
        QualifiedLeg("weak", "b", DecisionState.PLAY, 0.2, "Weak"),
        QualifiedLeg("other", "c", DecisionState.PLAY, 0.15, "Other"),
    ]
    ticket = build_official_ticket(legs)
    assert [leg.id for leg in ticket.legs] == ["strong"]
    assert ticket.removed == ("Weak",)


def test_ticket_b_uses_different_players_and_c_cannot_bypass() -> None:
    pool = [
        QualifiedLeg("a1", "player-a", DecisionState.PLAY, 0.9, "A"),
        QualifiedLeg("a2", "player-b", DecisionState.PLAY, 0.8, "B"),
        QualifiedLeg("skip", "player-c", DecisionState.SKIP, 0.99, "Not qualified"),
        QualifiedLeg("b1", "player-d", DecisionState.PLAY, 0.7, "D"),
    ]
    cards = build_abc(pool)
    assert {leg.player_key for leg in cards["ticket_a"].legs} == {"player-a", "player-b"}
    assert cards["ticket_b"].legs[0].player_key == "player-d"
    assert all(leg.state is DecisionState.PLAY for leg in cards["ticket_c"].legs)
    assert len(cards["ticket_c"].legs) <= 2
    assert "player-c" not in {leg.player_key for leg in cards["ticket_c"].legs}


def test_failed_check_is_skip_and_a_real_replacement_can_replace() -> None:
    checks = ("game_script", "matchup", "participation", "opportunity", "weather", "blowout_risk")
    validation = validate_inputs(_critical() + [_verified(name) for name in checks])
    blocked = build_card(
        event="Steelers at Browns",
        market="moneyline",
        selection="Browns",
        line="-3",
        validation=validation,
        support="Matchup leans home.",
        strongest_objection="Weather can flip the script.",
        failure_modes=["weather"],
        standalone=True,
        edge=0.04,
    )
    assert blocked.state is DecisionState.SKIP
    assert blocked.exposure_authorized is False
    replaced = build_card(
        event="Steelers at Browns",
        market="team total",
        selection="Under",
        line="42",
        validation=validation,
        support="The total has more cushion.",
        strongest_objection="Pace could rise.",
        failure_modes=["weather"],
        standalone=True,
        edge=0.04,
        replacement_passed=True,
        config=ProtocolConfig(exposure_cap_pct=1.0),
    )
    assert replaced.state is DecisionState.REPLACE
    kinds = set(replaced.evidence_kinds)
    assert EvidenceKind.VERIFIED.value in kinds
    assert EvidenceKind.ESTIMATE.value not in kinds


def test_baseline_keeps_the_prior_version_for_rollback(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/protocol/baseline", headers=auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == PROTOCOL_VERSION
    assert body["prior_version"] == PRIOR_PROTOCOL_VERSION
    assert body["rollback_to"] == PRIOR_PROTOCOL_VERSION
    assert body["official_max_legs"] == 2
    assert body["live_sports_protocol_unchanged"] is True
    assert "NO_BET" in body["states"]
    live = client.get("/api/v1/protocol/current", headers=auth_headers)
    assert live.status_code == 200
    assert live.json()["version"] == "2026.09.03"


def test_critical_field_list_covers_identity() -> None:
    assert "identity" in CRITICAL_FIELDS


def _qualified_card(**overrides: object):
    checks = ("game_script", "matchup", "participation", "opportunity", "weather", "blowout_risk")
    validation = validate_inputs(_critical() + [_verified(name) for name in checks])
    fields = {
        "event": "Steelers at Browns",
        "market": "moneyline",
        "selection": "Browns",
        "line": "-110",
        "validation": validation,
        "support": "Matchup and script both lean home.",
        "strongest_objection": "A late turnover can flip it.",
        "standalone": True,
        "edge": 0.04,
    }
    fields.update(overrides)
    return build_card(**fields)


def test_unset_exposure_cap_does_not_authorize_a_stake() -> None:
    card = _qualified_card()
    assert card.state is DecisionState.PLAY
    assert card.exposure_authorized is False


def test_first_start_back_stays_a_review_until_the_ban_is_set() -> None:
    assert first_start_back_gate(None, is_first_start_back=False) is None
    assert first_start_back_gate(None, is_first_start_back=True) is DecisionState.HOLD
    banned = ProtocolConfig(first_start_back_strikeout_ban=True)
    allowed = ProtocolConfig(first_start_back_strikeout_ban=False)
    assert first_start_back_gate(banned, is_first_start_back=True) is DecisionState.SKIP
    assert first_start_back_gate(allowed, is_first_start_back=True) is None
    card = _qualified_card(is_first_start_back=True)
    assert card.state is DecisionState.HOLD
    held = _qualified_card(replacement_passed=True, validation=validate_inputs([], sport_checks=()))
    assert held.state is DecisionState.HOLD
