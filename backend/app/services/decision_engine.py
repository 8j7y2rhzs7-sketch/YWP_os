from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.core.config import settings
from app.schemas import CandidateInput, Decision, RiskProfile
from app.services.readiness import candidate_readiness, candidate_verification_gaps


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def american_to_decimal(odds: int) -> float:
    if odds > 0:
        return 1 + odds / 100
    return 1 + 100 / abs(odds)


def implied_probability(odds: int) -> float:
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def input_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def money(value: float, places: str = "0.000001") -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


@dataclass(slots=True)
class Evaluation:
    candidate: CandidateInput
    payload: dict[str, Any]
    implied_probability: float
    adjusted_probability: float
    edge: float
    expected_value: float
    confidence_score: int
    vision_score: float
    ywp_intelligence_score: float
    miss_by_one_risk: float
    reliability: float
    stability: float
    risk: str
    risk_tier: str
    variance_rating: str
    edge_class: str
    expected_value_label: str
    suggested_stake_pct: float
    decision: str
    recommendation_tier: str
    reason_codes: list[str]
    warnings: list[str]
    reasoning_summary: str
    input_hash: str


class DecisionEngine:
    """Deterministic YWP v3 scoring plus constitutional and loss-audit gates."""

    def evaluate(
        self,
        candidate: CandidateInput,
        risk_profile: RiskProfile = RiskProfile.balanced,
        now: datetime | None = None,
        learned_weights: dict[str, float] | None = None,
    ) -> Evaluation:
        now = now or datetime.now(UTC)
        payload = candidate.model_dump(mode="json")
        implied = implied_probability(candidate.american_odds)

        quality = clamp(candidate.data_quality - 0.035 * len(candidate.missing_fields), 0, 1)
        warnings: list[str] = []
        reasons = list(dict.fromkeys(candidate.reason_codes))
        hard_skip_reasons: list[str] = []
        confidence_penalty = 0.0

        readiness = candidate_readiness(candidate)
        if readiness == "PARTIAL":
            gaps = candidate_verification_gaps(candidate)
            hard_skip_reasons.append(
                "Official play blocked until required research is verified: "
                + ", ".join(gaps)
                + "."
            )
            reasons.append("RESEARCH_INCOMPLETE")
        if candidate.probability_source == "market_implied":
            hard_skip_reasons.append(
                "Sportsbook implied probability is not an independent YWP projection."
            )
            reasons.append("NO_INDEPENDENT_PROBABILITY")

        age_seconds = max(0, (now - candidate.source_timestamp).total_seconds())
        stale_limit = 120 if candidate.market_period == "live" else 6 * 60 * 60
        if age_seconds > stale_limit:
            warnings.append("Provider snapshot is stale for this market period.")
            reasons.append("STALE_DATA")
            quality = max(0, quality - 0.15)
            confidence_penalty += 8

        if candidate.missing_fields:
            warnings.append("Missing fields: " + ", ".join(candidate.missing_fields))
            reasons.append("MISSING_DATA")
            confidence_penalty += min(12, len(candidate.missing_fields) * 2)

        verification_checks = {
            "schedule": candidate.schedule_verified,
            "current form": candidate.current_form_verified,
            "actual L5/L10": candidate.l5_l10_verified,
            "lineup": candidate.lineup_confirmed,
            "injuries": candidate.injuries_verified,
            "weather": candidate.weather_verified,
            "starter": candidate.starter_confirmed,
            "motivation/rotation": candidate.motivation_rotation_verified,
            "home/away": candidate.home_away_verified,
            "market movement": candidate.market_movement_verified,
            "sport-specific sweep": candidate.sport_specific_sweep_complete,
        }
        unverified = [name for name, passed in verification_checks.items() if not passed]
        if unverified:
            warnings.append("Unverified: " + ", ".join(unverified))
            reasons.append("VERIFICATION_GAP")
            confidence_penalty += min(12, len(unverified) * 2.5)

        # Confidence contracts toward 50 when provider quality is weak.
        # This prevents false precision.
        estimated = candidate.estimated_probability
        adjusted = 0.5 + (estimated - 0.5) * (0.70 + 0.30 * quality)

        # Provider factors may move probability only slightly.
        # The provider estimate remains primary.
        if candidate.factors:
            average_factor = sum(candidate.factors.values()) / len(candidate.factors)
            adjusted += average_factor * 0.015 * quality
        if learned_weights:
            # Learned weights default at 0.10. Drift above/below nudges probability slightly.
            for feature, weight in learned_weights.items():
                adjusted += (float(weight) - 0.10) * 0.04 * quality
        adjusted = clamp(adjusted, 0.02, 0.98)

        edge = adjusted - implied
        decimal_odds = american_to_decimal(candidate.american_odds)
        expected_value = adjusted * (decimal_odds - 1) - (1 - adjusted)
        edge_strength = clamp(max(edge, 0) / 0.12, 0, 1)

        confirmed_sources = sum(
            1 for source_status in candidate.source_status.values() if source_status == "confirmed"
        )
        source_reliability = (
            confirmed_sources / len(candidate.source_status) if candidate.source_status else quality
        )
        reliability = clamp(0.70 * quality + 0.30 * source_reliability, 0, 1)
        verification_rate = sum(verification_checks.values()) / len(verification_checks)
        stability = clamp(
            0.35 * candidate.role_stability
            + 0.30 * verification_rate
            + 0.20 * (1 - candidate.variance)
            + 0.15 * quality,
            0,
            1,
        )

        hit_rate = candidate.recent_hit_rate if candidate.recent_hit_rate is not None else estimated
        cushion_component = (
            0.5
            if candidate.average_cushion is None
            else clamp(0.5 + candidate.average_cushion / (2 * candidate.cushion_scale), 0, 1)
        )
        vision_score = 10 * (
            0.30 * hit_rate
            + 0.25 * cushion_component
            + 0.20 * candidate.matchup_score
            + 0.15 * candidate.script_alignment
            + 0.10 * candidate.multiple_paths_score
        )

        miss_rate = candidate.miss_by_one_count_l10 / 10
        cushion_risk = (
            0.5
            if candidate.average_cushion is None
            else clamp(1 - candidate.average_cushion / candidate.cushion_scale, 0, 1)
        )
        miss_by_one_risk = clamp(
            0.35 * miss_rate
            + 0.30 * cushion_risk
            + 0.15 * candidate.variance
            + 0.10 * (1 - candidate.role_stability)
            + 0.10 * (1 - candidate.multiple_paths_score)
            + min(0.20, candidate.ticket_killer_count * 0.04),
            0,
            1,
        )
        if miss_by_one_risk >= 0.55:
            warnings.append(
                "Miss-by-1 risk is elevated: thin cushion or repeated near-miss history "
                "makes this a potential ticket-killer leg."
            )
            reasons.append("MISS_BY_ONE_RISK")
            confidence_penalty += 6 if miss_by_one_risk < 0.80 else 10
        if miss_by_one_risk >= 0.80 and not candidate.safer_alternative:
            hard_skip_reasons.append(
                "Miss-by-1 risk is critical and no safer available line was supplied."
            )
            reasons.append("MISS_BY_ONE_GATE_FAILED")

        confidence = round(
            68 + 19 * quality + 15 * edge_strength - 14 * candidate.variance - confidence_penalty
        )

        if candidate.market_is_pitcher_strikeout_over:
            if candidate.first_start_back and not candidate.normal_workload_confirmed:
                hard_skip_reasons.append(
                    "Pitcher strikeout over blocked: first MLB appearance after injury "
                    "without a verified normal workload."
                )
                reasons.append("FIRST_START_BACK_EXCLUSION")
            if not candidate.k_duration_verified:
                hard_skip_reasons.append(
                    "Pitcher strikeout over blocked: expected batters faced, pitch count, "
                    "innings, contact profile, or pull behavior is unverified."
                )
                reasons.append("K_DURATION_GATE_FAILED")

        if (
            candidate.base_line is not None
            and candidate.line is not None
            and candidate.line > candidate.base_line
            and not candidate.alt_line_approved
        ):
            hard_skip_reasons.append(
                "Higher alternate line lacks its own cushion and hit-rate approval."
            )
            reasons.append("LINE_ESCALATION_BLOCKED")

        if (
            candidate.low_alt_over
            and candidate.credible_scoring_paths < 2
            and not candidate.dominant_scoring_path_verified
        ):
            hard_skip_reasons.append(
                "Low alternate over lacks two credible scoring paths or one verified dominant path."
            )
            reasons.append("LOW_TOTAL_TWO_PATH_GATE_FAILED")

        if candidate.heavily_juiced_filler and not candidate.independent_value_verified:
            hard_skip_reasons.append("Heavily priced filler leg has no independent value case.")
            reasons.append("FILLER_LEG_TAX")

        if candidate.game_status != "PRE_GAME":
            hard_skip_reasons.append(
                f"Game status is {candidate.game_status}; only PRE_GAME markets are eligible."
            )
            reasons.append("GAME_NOT_PRE_GAME")

        if candidate.market_status != "OPEN":
            hard_skip_reasons.append(
                f"Market status is {candidate.market_status}; only OPEN markets are eligible."
            )
            reasons.append("MARKET_NOT_OPEN")

        if abs(edge) > 0.15:
            hard_skip_reasons.append(
                "Model edge exceeds 15 percentage points and is quarantined for review."
            )
            reasons.append("MODEL_EDGE_QUARANTINE")

        if candidate.previous_game_recency_only:
            hard_skip_reasons.append(
                "Case depends on the previous game's score rather than rebuilt inputs."
            )
            reasons.append("PREVIOUS_GAME_RECENCY_BLOCK")

        if candidate.bullpen_game and not candidate.bullpen_verified:
            warnings.append("Opener/bullpen sequencing and availability are not fully verified.")
            reasons.append("BULLPEN_GAME_VARIANCE")
            confidence -= 8

        soccer_ml = candidate.sport.lower() == "soccer" and "moneyline" in candidate.market_type
        ninety_minute = candidate.market_period.lower() in {"90_min", "90_minutes", "regulation"}
        if (
            soccer_ml
            and ninety_minute
            and candidate.is_knockout
            and candidate.extra_time_available
            and (candidate.draw_probability or 0) >= 0.25
        ):
            hard_skip_reasons.append(
                "90-minute moneyline has a material draw/extra-time trap; use a qualified "
                "advance market only if its price has edge."
            )
            reasons.append("EXTRA_TIME_TRAP")

        if quality < settings.minimum_data_quality:
            hard_skip_reasons.append("Data quality is below the YWP minimum.")
            reasons.append("DATA_QUALITY_BAD")

        if edge < settings.minimum_edge or expected_value <= 0:
            hard_skip_reasons.append("Current price does not provide a clean positive edge.")
            reasons.extend(["NO_CLEAN_EDGE", "ODDS_TOO_EXPENSIVE"])

        confidence = int(clamp(confidence, 35, 97))
        if hard_skip_reasons:
            decision = Decision.skip.value
            confidence = min(confidence, 69)
        elif confidence >= 85 and edge >= 0.03:
            decision = Decision.play.value
        elif confidence >= 75 and edge >= settings.minimum_edge:
            decision = Decision.lean.value
        elif confidence >= 70:
            decision = Decision.watch.value
        else:
            decision = Decision.skip.value
            reasons.append("CONFIDENCE_BELOW_THRESHOLD")

        volatility = candidate.variance + (1 - quality) * 0.5
        if abs(candidate.american_odds) >= 300 or volatility >= 0.72:
            risk = "high"
        elif volatility >= 0.48:
            risk = "medium_high"
        elif volatility >= 0.30:
            risk = "medium"
        else:
            risk = "low"

        risk_tier = {
            "low": "Minimal",
            "medium": "Moderate",
            "medium_high": "Elevated",
            "high": "Speculative",
        }[risk]
        if candidate.variance < 0.25:
            variance_rating = "Low"
        elif candidate.variance < 0.48:
            variance_rating = "Medium"
        elif candidate.variance < 0.72:
            variance_rating = "High"
        else:
            variance_rating = "Very High"

        if edge >= 0.08 and confidence >= 90:
            edge_class = "Elite"
        elif edge >= 0.05:
            edge_class = "Strong"
        elif edge >= 0.03:
            edge_class = "Moderate"
        elif edge >= settings.minimum_edge:
            edge_class = "Marginal"
        else:
            edge_class = "No Edge"
        expected_value_label = (
            "Positive"
            if expected_value > 0.01
            else "Negative"
            if expected_value < -0.01
            else "Neutral"
        )

        yis = 10 * (
            0.30 * (confidence / 100)
            + 0.20 * (vision_score / 10)
            + 0.15 * reliability
            + 0.15 * stability
            + 0.10 * quality
            + 0.10 * clamp((expected_value + 0.02) / 0.18, 0, 1)
        )
        if decision == Decision.skip.value:
            yis = min(yis, 5.9)

        if decision == Decision.skip.value:
            suggested_stake_pct = 0.0
        elif confidence >= 92 and risk in {"low", "medium"}:
            suggested_stake_pct = 0.02
        elif confidence >= 85:
            suggested_stake_pct = 0.0125
        else:
            suggested_stake_pct = 0.005
        if risk_profile == RiskProfile.conservative:
            suggested_stake_pct *= 0.75
        elif risk_profile == RiskProfile.aggressive:
            suggested_stake_pct = min(0.025, suggested_stake_pct * 1.15)

        if decision == Decision.skip.value:
            tier = "stay_away"
        elif confidence >= 90 and risk == "low":
            tier = "cash_builder"
        elif confidence >= 88:
            tier = "core_parlay"
        elif expected_value >= 0.08:
            tier = "edge_play"
        else:
            tier = "support"

        warnings.extend(hard_skip_reasons)
        reasons = list(dict.fromkeys(reasons))
        reasoning_parts = list(candidate.reasoning)
        if edge > 0:
            reasoning_parts.append(
                f"Quality-adjusted probability is {adjusted:.1%} versus {implied:.1%} implied."
            )
        if hard_skip_reasons:
            reasoning_parts.append("Official YWP output: SKIP / NO PLAY.")
        if not reasoning_parts:
            reasoning_parts.append(
                "Recommendation is derived only from the supplied structured inputs."
            )

        return Evaluation(
            candidate=candidate,
            payload=payload,
            implied_probability=implied,
            adjusted_probability=adjusted,
            edge=edge,
            expected_value=expected_value,
            confidence_score=confidence,
            vision_score=round(vision_score, 2),
            ywp_intelligence_score=round(yis, 2),
            miss_by_one_risk=round(miss_by_one_risk, 4),
            reliability=round(reliability, 4),
            stability=round(stability, 4),
            risk=risk,
            risk_tier=risk_tier,
            variance_rating=variance_rating,
            edge_class=edge_class,
            expected_value_label=expected_value_label,
            suggested_stake_pct=round(suggested_stake_pct, 4),
            decision=decision,
            recommendation_tier=tier,
            reason_codes=reasons,
            warnings=list(dict.fromkeys(warnings)),
            reasoning_summary=" ".join(reasoning_parts),
            input_hash=input_hash(payload),
        )

    def rank(self, evaluations: list[Evaluation]) -> list[Evaluation]:
        gated = self.apply_slate_integrity_gates(evaluations)
        priority = {
            Decision.play.value: 0,
            Decision.lean.value: 1,
            Decision.watch.value: 2,
            Decision.skip.value: 3,
        }
        return sorted(
            gated,
            key=lambda item: (
                priority[item.decision],
                -item.confidence_score,
                -item.edge,
                item.candidate.variance,
            ),
        )

    def apply_slate_integrity_gates(self, evaluations: list[Evaluation]) -> list[Evaluation]:
        from collections import Counter

        counts = Counter(
            round(item.candidate.estimated_probability, 4) for item in evaluations
        )
        anomalous = {prob for prob, count in counts.items() if count >= 3}
        if not anomalous:
            return evaluations
        for item in evaluations:
            key = round(item.candidate.estimated_probability, 4)
            if key not in anomalous:
                continue
            self._force_skip(
                item,
                "DATA_ANOMALY",
                "Three or more candidates share an identical model probability.",
            )
        return evaluations

    @staticmethod
    def _force_skip(evaluation: Evaluation, code: str, message: str) -> None:
        if code not in evaluation.reason_codes:
            evaluation.reason_codes.append(code)
        if message not in evaluation.warnings:
            evaluation.warnings.append(message)
        evaluation.decision = Decision.skip.value
        evaluation.recommendation_tier = "stay_away"
        evaluation.suggested_stake_pct = 0.0
        evaluation.ywp_intelligence_score = min(evaluation.ywp_intelligence_score, 5.9)
        if "Official YWP output: SKIP / NO PLAY." not in evaluation.reasoning_summary:
            evaluation.reasoning_summary = (
                f"{evaluation.reasoning_summary} Official YWP output: SKIP / NO PLAY."
            ).strip()


decision_engine = DecisionEngine()
