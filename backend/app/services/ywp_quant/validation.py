"""Input verification gate. Missing facts become explicit blockers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


VALID_STATUSES = {"pregame", "live"}


def validate_leg(leg: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    required = ("id", "event_id", "market", "direction", "line", "verification")
    for key in required:
        if key not in leg:
            issues.append(f"MISSING_{key.upper()}")
    verification = leg.get("verification", {})
    for key in ("event_confirmed", "line_confirmed", "role_confirmed", "source_timestamp"):
        if not verification.get(key):
            issues.append(f"UNVERIFIED_{key.upper()}")
    if verification.get("status") not in VALID_STATUSES:
        issues.append("EVENT_NOT_AVAILABLE")
    timestamp = verification.get("source_timestamp")
    if timestamp:
        try:
            seen = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - seen.astimezone(timezone.utc)).total_seconds() / 3600
            max_age = float(verification.get("max_age_hours", 12))
            if age_hours > max_age:
                issues.append("STALE_SOURCE")
            if age_hours < -0.25:
                issues.append("FUTURE_SOURCE_TIMESTAMP")
        except (ValueError, TypeError):
            issues.append("INVALID_SOURCE_TIMESTAMP")
    direction = str(leg.get("direction", "")).lower()
    if direction not in {"over", "under", "yes", "no"}:
        issues.append("INVALID_DIRECTION")
    groups = leg.get("observation_groups", [])
    direct = leg.get("direct_probability")
    if not groups and direct is None:
        issues.append("NO_MODEL_INPUT")
    for group in groups:
        values = group.get("values", [])
        if len(values) < 2:
            issues.append(f"TOO_FEW_VALUES_{group.get('name', 'GROUP')}")
    return sorted(set(issues))


def verification_score(leg: dict[str, Any], issues: list[str]) -> float:
    hard = sum(issue.startswith(("MISSING_", "UNVERIFIED_", "INVALID_", "EVENT_")) for issue in issues)
    soft = len(issues) - hard
    return max(0.0, 1.0 - 0.18 * hard - 0.06 * soft)
