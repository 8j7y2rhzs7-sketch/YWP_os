"""Official decision states. They are not collapsed into one score."""

from enum import StrEnum


class DecisionState(StrEnum):
    PLAY = "PLAY"
    HOLD = "HOLD"
    SKIP = "SKIP"
    REPLACE = "REPLACE"
    NO_BET = "NO_BET"


class EvidenceKind(StrEnum):
    VERIFIED = "verified"
    ESTIMATE = "estimate"
    JUDGMENT = "judgment"
    UNKNOWN = "unknown"
