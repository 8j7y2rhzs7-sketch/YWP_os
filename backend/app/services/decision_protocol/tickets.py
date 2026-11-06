"""Official tickets are built only from plays that already qualify on their own."""

from dataclasses import dataclass

from app.services.decision_protocol.settings import ProtocolConfig, official_max_legs
from app.services.decision_protocol.states import DecisionState


@dataclass(frozen=True)
class QualifiedLeg:
    id: str
    player_key: str
    state: DecisionState
    reliability: float
    label: str


@dataclass(frozen=True)
class TicketBuild:
    name: str
    state: DecisionState
    legs: tuple[QualifiedLeg, ...]
    removed: tuple[str, ...] = ()
    note: str = ""


def _plays(legs: list[QualifiedLeg]) -> list[QualifiedLeg]:
    return [leg for leg in legs if leg.state is DecisionState.PLAY]


def _drop_weakest(ranked: list[QualifiedLeg]) -> tuple[list[QualifiedLeg], tuple[str, ...]]:
    """Drop a second leg that is much less reliable. Do not invent a replacement."""
    if len(ranked) < 2:
        return ranked, ()
    lead, second = ranked[0], ranked[1]
    if second.reliability < lead.reliability * 0.5:
        return [lead], (second.label,)
    return ranked, ()


def build_official_ticket(
    legs: list[QualifiedLeg],
    *,
    config: ProtocolConfig | None = None,
    name: str = "official",
) -> TicketBuild:
    qualified = sorted(_plays(legs), key=lambda leg: leg.reliability, reverse=True)
    if not qualified:
        return TicketBuild(
            name=name,
            state=DecisionState.NO_BET,
            legs=(),
            note="No selection qualified. NO BET is the official output.",
        )
    cap = official_max_legs(config)
    chosen, removed = _drop_weakest(qualified[:cap])
    return TicketBuild(
        name=name,
        state=DecisionState.PLAY,
        legs=tuple(chosen),
        removed=removed,
        note="Built only from standalone plays.",
    )


def build_abc(
    pool: list[QualifiedLeg],
    *,
    config: ProtocolConfig | None = None,
) -> dict[str, TicketBuild]:
    """A is the best plays. B uses different players. C cannot skip the rules."""
    ticket_a = build_official_ticket(pool, config=config, name="ticket_a")
    used = {leg.player_key for leg in ticket_a.legs}
    others = [leg for leg in pool if leg.player_key not in used]
    ticket_b = build_official_ticket(others, config=config, name="ticket_b")
    if not ticket_b.legs:
        ticket_b = TicketBuild(
            name="ticket_b",
            state=DecisionState.NO_BET,
            legs=(),
            note="No qualified different-player alternative. NO BET.",
        )
    combined = [leg for leg in (*ticket_a.legs, *ticket_b.legs) if leg.state is DecisionState.PLAY]
    ticket_c = build_official_ticket(combined, config=config, name="ticket_c")
    return {"ticket_a": ticket_a, "ticket_b": ticket_b, "ticket_c": ticket_c}
