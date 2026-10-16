"""October 4, 2026 decision protocol baseline.

This sits beside the live 2026.09.03 sports protocol. It does not replace
that protocol until a versioned cut is approved. Missing settings do not
relax a mandatory gate, and missing facts are never filled in.
"""

from app.services.decision_protocol.baseline import (
    PRIOR_PROTOCOL_VERSION,
    PROTOCOL_VERSION,
    baseline_manifest,
)
from app.services.decision_protocol.cards import DecisionCard, build_card
from app.services.decision_protocol.settings import ProtocolConfig, official_max_legs
from app.services.decision_protocol.states import DecisionState
from app.services.decision_protocol.tickets import TicketBuild, build_abc, build_official_ticket
from app.services.decision_protocol.validation import FieldRecord, validate_inputs

__all__ = [
    "PRIOR_PROTOCOL_VERSION",
    "PROTOCOL_VERSION",
    "DecisionCard",
    "DecisionState",
    "FieldRecord",
    "ProtocolConfig",
    "TicketBuild",
    "baseline_manifest",
    "build_abc",
    "build_card",
    "build_official_ticket",
    "official_max_legs",
    "validate_inputs",
]
