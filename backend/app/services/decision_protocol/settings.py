"""Unresolved settings stay configurable. A blank setting cannot loosen a gate."""

from dataclasses import dataclass, field

from app.services.decision_protocol.states import DecisionState

OFFICIAL_MAX_LEGS = 2


@dataclass(frozen=True)
class ProtocolConfig:
    """None means the owner has not decided. It is not a hidden default."""

    official_max_legs: int | None = OFFICIAL_MAX_LEGS
    exposure_cap_pct: float | None = None
    first_start_back_strikeout_ban: bool | None = None
    minimum_cushion_by_market: dict[str, float] | None = None
    auto_approve_rule_changes: bool = False
    notes: dict[str, str] = field(default_factory=dict)


def official_max_legs(config: ProtocolConfig | None = None) -> int:
    """The official parlay cap is two. A missing or looser value does not raise it."""
    if config is None or config.official_max_legs is None:
        return OFFICIAL_MAX_LEGS
    requested = int(config.official_max_legs)
    if requested < 1:
        return 1
    return min(requested, OFFICIAL_MAX_LEGS)


def exposure_authorized(config: ProtocolConfig | None) -> bool:
    """A blank cap is not a number and not permission to size a bet."""
    if config is None or config.exposure_cap_pct is None:
        return False
    return config.exposure_cap_pct > 0


def first_start_back_gate(
    config: ProtocolConfig | None, *, is_first_start_back: bool
) -> DecisionState | None:
    """Unset ban stays a review, not a silent pass and not a made-up ban."""
    if not is_first_start_back:
        return None
    if config is None or config.first_start_back_strikeout_ban is None:
        return DecisionState.HOLD
    if config.first_start_back_strikeout_ban:
        return DecisionState.SKIP
    return None
