"""Metacognition — the system explaining itself.

Three questions on every reflection:
  1. why          — why did we do what we did?
  2. system_impact — how does that choice affect the system?
  3. next_time    — what should we do differently next time?

This is not marketing copy. It is the audit trail the engine uses to stay
honest about its own process (gates, Hive blend, self-improve cycles).
"""

from __future__ import annotations

from typing import Any


def reflection(
    *,
    why: str,
    system_impact: str,
    next_time: str,
    subject: str | None = None,
    kind: str = "decision",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "subject": subject,
        "why": why.strip(),
        "system_impact": system_impact.strip(),
        "next_time": next_time.strip(),
    }


def reflect_on_decision(
    *,
    decision: str,
    reason_codes: list[str] | None,
    warnings: list[str] | None,
    reasoning_summary: str | None,
    selection: str | None = None,
    hive_meta: dict[str, Any] | None = None,
    probability_source: str | None = None,
) -> dict[str, Any]:
    """Build metacognition for one graded candidate."""
    codes = [str(c) for c in (reason_codes or [])]
    warns = [str(w) for w in (warnings or [])]
    hive = hive_meta if isinstance(hive_meta, dict) else {}
    decision_u = (decision or "SKIP").upper()
    source = (probability_source or "").lower()

    why_parts: list[str] = []
    if decision_u in {"PLAY", "LEAN"}:
        why_parts.append(
            f"Issued {decision_u} because independent research cleared Strict Mode gates."
        )
    elif decision_u == "WATCH":
        why_parts.append("Issued WATCH — edge or verification is incomplete, not a forced fill.")
    else:
        why_parts.append(
            f"Issued {decision_u} because one or more constitutional gates blocked a play."
        )
    if codes:
        why_parts.append("Gate codes: " + ", ".join(codes[:8]) + ".")
    if source == "market_implied":
        why_parts.append("Probability was sportsbook-implied only — not an independent model.")
    elif source in {"model", "manual_verified"}:
        why_parts.append("Probability came from an independent model / verified form path.")
    if hive.get("used"):
        shift = hive.get("shift_applied")
        why_parts.append(
            f"Hive applied a bounded calibration shift ({shift:+.4f})."
            if isinstance(shift, (int, float))
            else "Hive applied a bounded calibration shift."
        )
    elif hive.get("reason"):
        why_parts.append(f"Hive did not blend: {hive.get('reason')}.")
    if reasoning_summary:
        why_parts.append(str(reasoning_summary)[:280])

    impact_parts: list[str] = []
    if decision_u in {"PLAY", "LEAN"}:
        impact_parts.append(
            "This pick can enter tickets, Lock Check, settlement, and Hive training if placed."
        )
    else:
        impact_parts.append(
            "SKIP/REVIEW stays off official cards — protects Hive from training on ungated noise."
        )
    if "MARKET_NOT_OPEN" in codes or "GAME_NOT_PRE_GAME" in codes:
        impact_parts.append("Closed/live markets cannot be locked or learned as pre-game process.")
    if hive.get("used"):
        impact_parts.append(
            "Hive shift changes displayed edge for this bucket only within constitutional caps."
        )
    if warns:
        impact_parts.append("Open warnings: " + "; ".join(warns[:3]) + ".")

    next_parts: list[str] = []
    if "RESEARCH_INCOMPLETE" in codes or "NO_INDEPENDENT_PROBABILITY" in codes:
        next_parts.append(
            "Warm prop research until modeled, then re-LAUNCH — do not force a PLAY."
        )
    elif "STALE_DATA" in codes:
        next_parts.append("Refresh the raw slate so provider timestamps are current.")
    elif "MARKET_NOT_OPEN" in codes:
        next_parts.append("Drop closed legs before Lock Check; rebuild from open books only.")
    elif decision_u in {"PLAY", "LEAN"}:
        next_parts.append(
            "After the game, Sync Scores so Hive can ask whether this process deserved the grade."
        )
    else:
        next_parts.append(
            "Keep fail-closed. Next cycle should only promote if settled history proves a better tactic."
        )
    if hive.get("reason") == "insufficient_hive_sample":
        next_parts.append("Need more settled samples in this bucket before Hive may blend.")
    if hive.get("reason") == "bucket_inhibited_by_self_improve":
        next_parts.append(
            "This bucket is inhibited by self-improve — clear only if a later cycle proves recovery."
        )

    return reflection(
        kind="decision",
        subject=(selection or "")[:180] or None,
        why=" ".join(why_parts),
        system_impact=" ".join(impact_parts),
        next_time=" ".join(next_parts),
    )


def reflect_on_self_improve_cycle(
    *,
    promoted: bool,
    winner: str,
    explanation: str,
    baseline: dict[str, Any] | None,
    trials: list[dict[str, Any]] | None,
    trigger: str | None = None,
    sport: str | None = None,
) -> dict[str, Any]:
    """Build metacognition for one Hive invent→simulate→promote cycle."""
    baseline = baseline or {}
    trials = trials or []
    brier = baseline.get("brier")
    n = baseline.get("n")

    why = (
        f"Ran a self-improvement cycle ({trigger or 'auto'}) on "
        f"{sport or 'all sports'} settled history"
        + (f" with n={n}, baseline Brier={brier}." if n is not None else ".")
        + f" Tried {len(trials)} bounded idea(s)."
    )
    if promoted:
        system_impact = (
            f"Promoted tactic '{winner}'. Future analyze blends for matching buckets "
            "will use the new policy caps/inhibits — still inside constitutional ceilings."
        )
        next_time = (
            "Watch the next settle window. If Brier regresses, a later cycle can roll "
            "tactics back by promoting a better challenger."
        )
    else:
        system_impact = (
            f"Kept current policy. Challenger '{winner}' did not beat baseline by the "
            "promotion ε — live blends unchanged."
        )
        next_time = (
            "Collect more verified WIN/LOSS samples, then run another cycle. "
            "Do not loosen gates just to invent motion."
        )
    if explanation:
        why = f"{why} {explanation}"

    return reflection(
        kind="self_improve",
        subject=f"hive-cycle:{winner}",
        why=why,
        system_impact=system_impact,
        next_time=next_time,
    )


def list_metacognition_feed(
    *,
    cycles: list[dict[str, Any]],
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Normalize stored cycle rows into a Learning-tab metacognition feed."""
    feed: list[dict[str, Any]] = []
    for row in cycles:
        meta = row.get("metacognition")
        if not isinstance(meta, dict):
            meta = reflect_on_self_improve_cycle(
                promoted=bool(row.get("promoted")),
                winner=str(row.get("winner") or "current"),
                explanation=str(row.get("explanation") or ""),
                baseline=row.get("baseline") if isinstance(row.get("baseline"), dict) else {},
                trials=[{"idea": "restored"}] * int(row.get("trial_count") or 0),
                trigger="history",
            )
        feed.append(
            {
                "id": row.get("id"),
                "created_at": row.get("created_at"),
                "promoted": row.get("promoted"),
                "winner": row.get("winner"),
                "metacognition": meta,
            }
        )
        if len(feed) >= limit:
            break
    return feed
