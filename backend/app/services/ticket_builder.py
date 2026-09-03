from __future__ import annotations

from collections.abc import Callable, Iterable

from app.models import Recommendation
from app.schemas import QuarantineItemOut, RecommendationOut, TicketCardOut
from app.services.board_metrics import (
    card_risk,
    joint_win_probability_disclosure,
    select_weakest_leg,
)
from app.services.ticket_gates import (
    CASH_CARD_KEYS,
    cap_pitcher_k_overs,
    cash_card_k_overs_ok,
    is_pitcher_k_over,
    model_edge_quarantine,
)


def _score(recommendation: Recommendation) -> tuple[float, float, float, float, float, float]:
    return (
        float(recommendation.confidence_score),
        float(recommendation.ywp_rating),
        float(recommendation.vision_score),
        float(recommendation.edge),
        -float(recommendation.miss_by_one_risk),
        -float(recommendation.variance),
    )


def _analysis_rank(recommendation: Recommendation) -> int:
    rank = int(getattr(recommendation, "rank", 0) or 0)
    return rank if rank > 0 else 10_000


def _priority(recommendation: Recommendation) -> tuple:
    """Prefer analysis board rank so #1 eligible picks surface on Max Bet."""
    conf, rating, vision, edge, neg_miss, neg_var = _score(recommendation)
    return (_analysis_rank(recommendation), -conf, -rating, -vision, -edge, -neg_miss, -neg_var)


def _quarantine(item: Recommendation, reason: str) -> QuarantineItemOut:
    rank = int(getattr(item, "rank", 0) or 0)
    selection = getattr(item, "selection", None)
    prefix = f"Analysis rank #{rank}: " if rank > 0 else ""
    return QuarantineItemOut(
        recommendation_id=item.id,
        reason=f"{prefix}{reason}",
        selection=selection,
        analysis_rank=rank if rank > 0 else None,
    )


def _diverse(
    pool: Iterable[Recommendation],
    count: int,
    *,
    existing: set[str] | None = None,
    entity: Callable[[Recommendation], str] | None = None,
) -> list[Recommendation]:
    selected: list[Recommendation] = []
    used_scripts: set[str] = set()
    used_entities = set(existing or set())
    entity = entity or (lambda item: item.player_key or item.event_id)
    for item in sorted(pool, key=_priority):
        item_entity = entity(item)
        if item.script_key in used_scripts or item_entity in used_entities:
            continue
        selected.append(item)
        used_scripts.add(item.script_key)
        used_entities.add(item_entity)
        if len(selected) >= count:
            break
    return selected


def _card(
    key: str, label: str, legs: list[Recommendation], warnings: list[str] | None = None
) -> TicketCardOut:
    warnings = list(warnings or [])
    joint = joint_win_probability_disclosure(legs)
    if not legs:
        warnings.append("No plays qualified. PASS is the official output.")
        confidence = 0
        risk = "none"
        risk_explanation = "No legs; PASS."
        weakest = None
        criterion = None
        explanation = None
    else:
        confidence = round(sum(item.confidence_score for item in legs) / len(legs))
        weakest_item, criterion, explanation = select_weakest_leg(legs)
        weakest = weakest_item.id
        risk, risk_explanation = card_risk(legs)
        high_near_miss = [
            item.selection for item in legs if float(item.miss_by_one_risk) >= 0.55
        ]
        if high_near_miss:
            warnings.append("Elevated miss-by-1 leg(s): " + ", ".join(high_near_miss))
        warnings.append(explanation)
    return TicketCardOut(
        key=key,
        label=label,
        recommendation_ids=[item.id for item in legs],
        legs=[RecommendationOut.model_validate(item) for item in legs],
        risk=risk,
        risk_explanation=risk_explanation,
        confidence_score=confidence,
        quality_score=confidence,
        joint_win_probability=joint["joint_win_probability"],
        joint_probability_status=str(joint["joint_probability_status"]),
        joint_probability_note=joint.get("joint_probability_note"),
        weakest_leg_id=weakest,
        weakest_leg_criterion=criterion,
        weakest_leg_explanation=explanation,
        warnings=warnings,
    )


def build_cards(
    recommendations: list[Recommendation],
    max_legs: int,
    min_rating: float,
    exposed_thesis_keys: set[str] | None = None,
) -> tuple[dict[str, TicketCardOut], list[QuarantineItemOut]]:
    exposed_thesis_keys = exposed_thesis_keys or set()
    quarantined: list[QuarantineItemOut] = []
    best_by_thesis: dict[str, Recommendation] = {}

    for item in recommendations:
        if item.decision not in {"PLAY", "LEAN"}:
            if _analysis_rank(item) <= 10:
                quarantined.append(
                    _quarantine(
                        item,
                        f"{item.decision} is not ticket-eligible (PLAY/LEAN only).",
                    )
                )
            continue
        snap = item.snapshot or {}
        source = str(
            snap.get("probability_source")
            or getattr(item, "data_source", "")
            or ""
        ).lower()
        # Never promote demo/synthetic fixtures onto production official cards.
        from app.core.config import settings

        production_live = (not settings.demo_mode) or settings.env == "production"
        if production_live and (
            snap.get("probability_source") == "demo"
            or "demo" in source
            or "synthetic" in source
        ):
            quarantined.append(
                _quarantine(
                    item,
                    "Demo/synthetic probability cannot enter production official cards.",
                )
            )
            continue
        if float(item.ywp_rating) < min_rating:
            quarantined.append(
                _quarantine(
                    item,
                    f"Below min rating ({float(item.ywp_rating):.2f} < {min_rating}).",
                )
            )
            continue
        if item.thesis_key in exposed_thesis_keys:
            quarantined.append(
                _quarantine(
                    item,
                    "Thesis already has active cash exposure on another ticket.",
                )
            )
            continue
        if model_edge_quarantine(float(item.edge)):
            quarantined.append(
                _quarantine(
                    item,
                    "Model edge exceeds 15 percentage points; quarantined for review.",
                )
            )
            continue
        if float(item.miss_by_one_risk) >= 0.80:
            quarantined.append(
                _quarantine(
                    item,
                    "Critical miss-by-1 risk; remove or use a verified safer line.",
                )
            )
            continue
        current = best_by_thesis.get(item.thesis_key)
        if current is None or _priority(item) < _priority(current):
            if current is not None:
                quarantined.append(
                    _quarantine(
                        current,
                        "Duplicate thesis; higher-ranked / stronger version retained.",
                    )
                )
            best_by_thesis[item.thesis_key] = item
        else:
            quarantined.append(
                _quarantine(
                    item,
                    "Duplicate thesis; higher-ranked / stronger version retained.",
                )
            )

    eligible = sorted(best_by_thesis.values(), key=_priority)
    strongest = eligible[:1]
    safe_pool = [item for item in eligible if float(item.miss_by_one_risk) < 0.55]
    cash_pool = sorted(
        safe_pool,
        key=lambda item: (
            float(item.miss_by_one_risk),
            float(item.variance),
            _analysis_rank(item),
            -item.confidence_score,
        ),
    )
    cash = _diverse(cash_pool, min(2, max_legs))
    core = _diverse(eligible, min(max(3, min(max_legs, 5)), len(eligible) or 1))
    edge_pool = sorted(
        eligible,
        key=lambda item: (
            -float(item.expected_value),
            -item.confidence_score,
            _analysis_rank(item),
        ),
    )
    edge = _diverse(edge_pool, min(3, max_legs))
    elite_two = _diverse(eligible, min(2, max_legs))
    core_3 = _diverse(eligible, min(3, max_legs))
    core_4 = _diverse(eligible, min(4, max_legs))
    core_5 = _diverse(eligible, min(5, max_legs))
    fortress = _diverse(safe_pool, min(3, max_legs))
    handicap_pool = sorted(
        eligible,
        key=lambda item: (
            -float(item.vision_score),
            -float(item.edge),
            -item.confidence_score,
            _analysis_rank(item),
        ),
    )
    handicap = _diverse(handicap_pool, min(3, max_legs))
    no_stress = _diverse(cash_pool, min(3, max_legs))
    scripted_pool = sorted(
        eligible,
        key=lambda item: (
            -float((item.snapshot or {}).get("script_alignment", 0)),
            -item.confidence_score,
            _analysis_rank(item),
        ),
    )
    scripted = _diverse(scripted_pool, min(3, max_legs))
    ghostt_pool = [item for item in edge_pool if float(item.edge) >= 0.03]
    ghostt = _diverse(ghostt_pool, min(4, max_legs))
    quick_cash = _diverse([item for item in eligible if item.quick_cash], min(3, max_legs))
    chain_reaction = _diverse(
        [item for item in eligible if item.chain_reaction_key], min(3, max_legs)
    )

    a = _diverse(eligible, min(3, max_legs))
    a_entities = {item.player_key or item.event_id for item in a}
    b = _diverse(eligible, min(3, max_legs), existing=a_entities)
    c_pool = sorted({item.id: item for item in [*a, *b]}.values(), key=_priority)
    c = _diverse(c_pool, min(3, max_legs))

    cards = {
        "max_bet": _card("max_bet", "Max Bet — strongest single", strongest),
        "elite_two": _card("elite_two", "Elite 2-Pick", elite_two),
        "core_parlay": _card("core_parlay", "Core Parlay", core),
        "core_3": _card("core_3", "Official 3-Pick", core_3),
        "core_4": _card("core_4", "Official 4-Pick", core_4),
        "core_5": _card("core_5", "Official 5-Pick", core_5),
        "cash_builder": _cash_card("cash_builder", "Cash Builder", cash, quarantined),
        "edge_plays": _card("edge_plays", "Edge Plays", edge),
        "fortress": _card("fortress", "Fortress Card", fortress),
        "handicap": _card("handicap", "Handicap Card — biggest cushion", handicap),
        "no_stress": _cash_card("no_stress", "No Stress Card", no_stress, quarantined),
        "scripted": _card("scripted", "Scripted Card", scripted),
        "quick_cash": _cash_card(
            "quick_cash",
            "Quick Cash — early-settlement edge",
            quick_cash,
            quarantined,
        ),
        "chain_reaction": _card(
            "chain_reaction",
            "Chain Reaction — verified trigger paths",
            chain_reaction,
        ),
        "ghostt": _card(
            "ghostt",
            "Ghostt Parlay — genuine mispricing only",
            ghostt,
            ["Higher upside, never built by adding random legs or underdogs."],
        ),
        "comeback": _card(
            "comeback",
            "Comeback Card — no chasing",
            fortress,
            [
                "Built from current qualified edges only; prior losses do not increase "
                "stake or action."
            ],
        ),
        "ticket_a": _card("ticket_a", "Ticket A — strongest plays", a),
        "ticket_b": _card("ticket_b", "Ticket B — different players/theses", b),
        "ticket_c": _card("ticket_c", "Ticket C — best of A + B", c),
    }
    min_legs = {
        "max_bet": 1,
        "elite_two": 2,
        "core_parlay": 2,
        "core_3": 3,
        "core_4": 4,
        "core_5": 5,
        "cash_builder": 1,
        "edge_plays": 2,
        "fortress": 2,
        "handicap": 2,
        "no_stress": 2,
        "scripted": 2,
        "quick_cash": 1,
        "chain_reaction": 2,
        "ghostt": 2,
        "comeback": 2,
        "ticket_a": 2,
        "ticket_b": 2,
        "ticket_c": 2,
    }
    pruned: dict[str, TicketCardOut] = {}
    for key, card in cards.items():
        needed = min_legs.get(key, 1)
        if len(card.legs) >= needed:
            pruned[key] = card
            continue
        if card.legs:
            quarantined.append(
                QuarantineItemOut(
                    recommendation_id=card.legs[0].id,
                    reason=(
                        f"{card.label} needs {needed} legs; only {len(card.legs)} "
                        "survived ticket gates (no filler legs added)."
                    ),
                    selection=card.legs[0].selection,
                    analysis_rank=card.legs[0].rank or None,
                )
            )
    if "max_bet" not in pruned and strongest:
        pruned["max_bet"] = _card("max_bet", "Max Bet — strongest single", strongest)
    if not any(card.legs for card in pruned.values()):
        return {}, quarantined
    return pruned, quarantined


def _cash_card(
    key: str,
    label: str,
    legs: list[Recommendation],
    quarantined: list[QuarantineItemOut],
) -> TicketCardOut:
    capped, rejected = cap_pitcher_k_overs(legs, max_k=1)
    warnings: list[str] = []
    if rejected or not cash_card_k_overs_ok(key, capped):
        for item in legs:
            if is_pitcher_k_over(item) and item.id not in {leg.id for leg in capped}:
                quarantined.append(
                    _quarantine(
                        item,
                        "Cash card rejected extra pitcher strikeout over (max 1).",
                    )
                )
        warnings.append("Pitcher-K overs per cash card cannot exceed 1.")
        if not cash_card_k_overs_ok(key, capped):
            return _card(key, label, [], warnings)
    if key not in CASH_CARD_KEYS:
        return _card(key, label, capped, warnings)
    return _card(key, label, capped, warnings)
