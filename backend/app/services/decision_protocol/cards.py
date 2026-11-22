"""A decision card keeps support, the strongest objection, and the final state apart."""

from dataclasses import dataclass, field

from app.services.decision_protocol.settings import (
    ProtocolConfig,
    exposure_authorized,
    first_start_back_gate,
)
from app.services.decision_protocol.states import DecisionState, EvidenceKind
from app.services.decision_protocol.validation import ValidationResult


@dataclass(frozen=True)
class DecisionCard:
    event: str
    market: str
    selection: str
    line: str
    state: DecisionState
    classification: str
    support: str
    strongest_objection: str
    cushion: str
    recent_performance: str
    failure_modes: tuple[str, ...]
    verification: str
    standalone: bool
    correlation: str
    confidence: str = "unscored"
    evidence_kinds: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    protocol_version: str = "2026.10.04"
    sources: tuple[str, ...] = field(default_factory=tuple)
    exposure_authorized: bool = False


def build_card(
    *,
    event: str,
    market: str,
    selection: str,
    line: str,
    validation: ValidationResult,
    support: str,
    strongest_objection: str,
    failure_modes: list[str] | None = None,
    standalone: bool = False,
    edge: float | None = None,
    cushion: str = "",
    recent_performance: str = "",
    correlation: str = "",
    config: ProtocolConfig | None = None,
    is_first_start_back: bool = False,
    replacement_passed: bool = False,
) -> DecisionCard:
    """Qualify the play. A blank edge or a failed check cannot become PLAY."""
    modes = tuple(failure_modes or ())
    kinds = tuple(dict.fromkeys(record.kind.value for record in validation.records))
    sources = tuple(
        record.source
        for record in validation.records
        if record.source and record.kind is EvidenceKind.VERIFIED
    )
    sized = exposure_authorized(config)
    state = DecisionState.PLAY
    verification = "verified"
    if not validation.passed:
        state = DecisionState.HOLD
        verification = "unverified"
    elif modes or not standalone or edge is None or edge <= 0:
        state = DecisionState.SKIP
    starter = first_start_back_gate(config, is_first_start_back=is_first_start_back)
    if state is DecisionState.PLAY and starter is not None:
        state = starter
    if state is not DecisionState.PLAY and replacement_passed and validation.passed:
        state = DecisionState.REPLACE
    return DecisionCard(
        event=event,
        market=market,
        selection=selection,
        line=line,
        state=state,
        classification=state.value,
        support=support,
        strongest_objection=strongest_objection or "No opposing argument was recorded.",
        cushion=cushion or "not recorded",
        recent_performance=recent_performance or "not recorded",
        failure_modes=modes,
        verification=verification,
        standalone=standalone and state is DecisionState.PLAY,
        correlation=correlation or "not reviewed",
        evidence_kinds=kinds,
        missing=validation.missing,
        sources=sources,
        exposure_authorized=sized and state is DecisionState.PLAY,
    )
