from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Outcome = Literal["WIN", "LOSS", "PUSH", "VOID"]
HiveAction = Literal["accepted", "rejected", "ignored"]


class HivePredictionIn(BaseModel):
    source_recommendation_id: str
    sport: str
    league: str | None = None
    event_id: str
    event_start_at: datetime | None = None
    market: str
    market_scope: str
    selection: str
    line: float | None = None
    odds_american: int | None = None
    model_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_score: float | None = Field(default=None, ge=0.0, le=100.0)
    model_version: str
    protocol_version: str | None = None
    evidence_version: str | None = None
    data_quality: float | None = Field(default=None, ge=0.0, le=1.0)
    feature_flags: dict[str, Any] = Field(default_factory=dict)
    consent_to_hive: bool = True


class HiveActionIn(BaseModel):
    source_recommendation_id: str
    action: HiveAction


class HiveOutcomeIn(BaseModel):
    source_recommendation_id: str
    outcome: Outcome
    verified: bool = False
    result_source: str
    resolved_at: datetime | None = None


class HiveSignalOut(BaseModel):
    sport: str
    league: str | None
    market: str
    market_scope: str
    model_version: str
    eligible_samples: int
    wins: int
    losses: int
    pushes: int
    voids: int
    posterior_rate: float | None
    raw_rate: float | None
    release_version: str
