"""Stage 1. A missing critical fact is HOLD. Nothing is invented to fill it."""

from dataclasses import dataclass, field

from app.services.decision_protocol.baseline import SPORT_REQUIRED_CHECKS
from app.services.decision_protocol.states import DecisionState, EvidenceKind

CRITICAL_FIELDS: tuple[str, ...] = (
    "sport",
    "event",
    "start_time",
    "identity",
    "market",
)


@dataclass(frozen=True)
class FieldRecord:
    name: str
    value: object | None
    kind: EvidenceKind
    source: str | None = None
    confirmed: bool = False


@dataclass(frozen=True)
class ValidationResult:
    state: DecisionState
    missing: tuple[str, ...]
    records: tuple[FieldRecord, ...] = field(default_factory=tuple)
    fabricated: bool = False

    @property
    def passed(self) -> bool:
        return self.state is not DecisionState.HOLD and not self.missing


def _record_map(records: tuple[FieldRecord, ...] | list[FieldRecord]) -> dict[str, FieldRecord]:
    return {record.name: record for record in records}


def _is_present(record: FieldRecord | None) -> bool:
    if record is None or record.value is None or record.value == "":
        return False
    if record.kind is EvidenceKind.UNKNOWN or not record.confirmed:
        return False
    return record.kind is EvidenceKind.VERIFIED


def validate_inputs(
    records: list[FieldRecord],
    *,
    critical: tuple[str, ...] = CRITICAL_FIELDS,
    sport_checks: tuple[str, ...] | None = None,
) -> ValidationResult:
    """Confirm critical inputs. Unconfirmed or unknown values do not count."""
    found = _record_map(records)
    missing = tuple(name for name in critical if not _is_present(found.get(name)))
    sport = found.get("sport")
    sport_name = str(sport.value).lower() if sport and sport.value else ""
    required = sport_checks
    if required is None and sport_name in SPORT_REQUIRED_CHECKS:
        required = SPORT_REQUIRED_CHECKS[sport_name]
    if required and _is_present(sport):
        missing = missing + tuple(name for name in required if not _is_present(found.get(name)))
    if missing:
        return ValidationResult(
            state=DecisionState.HOLD,
            missing=missing,
            records=tuple(records),
        )
    return ValidationResult(state=DecisionState.PLAY, missing=(), records=tuple(records))
