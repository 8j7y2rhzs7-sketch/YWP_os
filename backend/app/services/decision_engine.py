from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.core.config import settings
from app.schemas import CandidateInput, Decision, RiskProfile
from app.services.board_metrics import outlier_review_reasons
from app.services.calculation_discipline import (
    heavy_juice_blockers,
    identity_blockers,
    line_shave_blockers,
    market_series_blockers,
    minutes_not_production_blockers,
    protective_dog_spread_blockers,
    wait_reasons,
)
from app.services.pipeline.market_math import compare_to_market
from app.services.pipeline.runner import run_leg_pipeline
from app.services.readiness import (
    ESPN_TEAM_MARKET_SPORTS,
    OUTDOOR_WEATHER_SPORTS,
    candidate_readiness,
    candidate_verification_gaps,
    is_mlb_team_market,
)


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


# Board flatteners often pre-fill a generic string — that is NOT a verified safer line.
_PLACEHOLDER_SAFER_PREFIXES = (
    "Safer version of ",
    "Pick a different market",
    "Use a lower line only if",
)


def verified_safer_alternative(text: str | None) -> bool:
    """True only when a concrete safer line was supplied (not a sheet placeholder)."""
    if not text or not str(text).strip():
        return False
    cleaned = str(text).strip()
    return not any(cleaned.startswith(prefix) for prefix in _PLACEHOLDER_SAFER_PREFIXES)


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
        # Local YWP_DEMO_MODE fixtures may PLAY for end-to-end testing.
        # Production / non-demo runs never promote demo/synthetic probabilities.
        if (readiness == "DEMO" or candidate.probability_source == "demo") and not settings.demo_mode:
            hard_skip_reasons.append(
                "Official play blocked: demo/synthetic probability is not live evidence."
            )
            reasons.append("DEMO_DATA")
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
            "injuries": candidate.injuries_verified,
            "motivation/rotation": candidate.motivation_rotation_verified,
            "home/away": candidate.home_away_verified,
            "market movement": candidate.market_movement_verified,
            "sport-specific sweep": candidate.sport_specific_sweep_complete,
        }
        sport_l = (candidate.sport or "").lower()
        # No certified lineup feed for ESPN team sports / KBO — do not scare the board.
        # MLB full-game markets also skip lineup as a hard unverified flag (orders post late).
        if sport_l not in ESPN_TEAM_MARKET_SPORTS and sport_l != "kbo" and not is_mlb_team_market(
            candidate
        ):
            verification_checks["lineup"] = candidate.lineup_confirmed
            verification_checks["starter"] = candidate.starter_confirmed
        elif is_mlb_team_market(candidate):
            verification_checks["starter"] = candidate.starter_confirmed
        if sport_l in OUTDOOR_WEATHER_SPORTS:
            verification_checks["weather"] = candidate.weather_verified
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
            for _feature, weight in learned_weights.items():
                adjusted += (float(weight) - 0.10) * 0.04 * quality
        adjusted = clamp(adjusted, 0.02, 0.98)

        # Stage 5 — compare model fair p to de-vigged (or vig-proxy) market.
        market_cmp = compare_to_market(
            model_probability=adjusted,
            american_odds=candidate.american_odds,
            opposite_american_odds=candidate.opposite_american_odds,
        )
        fair_implied = float(market_cmp["fair_implied_probability"])
        implied = fair_implied  # edge/EV use fair market, not raw vig-inflated implied
        edge = adjusted - fair_implied
        decimal_odds = american_to_decimal(candidate.american_odds)
        expected_value = adjusted * (decimal_odds - 1) - (1 - adjusted)
        edge_strength = clamp(max(edge, 0) / 0.12, 0, 1)
        payload["market_comparison"] = market_cmp
        payload["raw_implied_probability"] = market_cmp["raw_implied_probability"]
        payload["fair_implied_probability"] = fair_implied

        confirmed_sources = sum(
            1 for source_status in candidate.source_status.values() if source_status == "confirmed"
        )
        source_reliability = (
            confirmed_sources / len(candidate.source_status) if candidate.source_status else quality
        )
        reliability = clamp(0.70 * quality + 0.30 * source_reliability, 0, 1)
        verification_rate = sum(verification_checks.values()) / len(verification_checks)
        role_stability = (
            0.5 if candidate.role_stability is None else float(candidate.role_stability)
        )
        matchup_score = (
            0.5 if candidate.matchup_score is None else float(candidate.matchup_score)
        )
        script_alignment = (
            0.5 if candidate.script_alignment is None else float(candidate.script_alignment)
        )
        multiple_paths = (
            0.5
            if candidate.multiple_paths_score is None
            else float(candidate.multiple_paths_score)
        )
        miss_by_one_count = (
            0
            if candidate.miss_by_one_count_l10 is None
            else int(candidate.miss_by_one_count_l10)
        )
        stability = clamp(
            0.35 * role_stability
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
            + 0.20 * matchup_score
            + 0.15 * script_alignment
            + 0.10 * multiple_paths
        )

        miss_rate = miss_by_one_count / 10
        cushion_risk = (
            0.5
            if candidate.average_cushion is None
            else clamp(1 - candidate.average_cushion / candidate.cushion_scale, 0, 1)
        )
        miss_by_one_risk = clamp(
            0.35 * miss_rate
            + 0.30 * cushion_risk
            + 0.15 * candidate.variance
            + 0.10 * (1 - role_stability)
            + 0.10 * (1 - multiple_paths)
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
        market_l = str(candidate.market_type or "").lower()
        is_modeled_prop_sport = (
            sport_l in {"wnba", "nba", "basketball", "nfl", "ncaaf", "mlb"}
            and (
                market_l.startswith("player_")
                or market_l.startswith("pitcher_")
                or market_l.startswith("batter_")
                or "strikeout" in market_l
            )
        )
        # Mimic the human filter: thin player-prop closes never become official plays,
        # even when the sheet pre-filled a generic safer_alternative string.
        if is_modeled_prop_sport and miss_by_one_risk >= 0.55:
            hard_skip_reasons.append(
                "Player prop blocked: elevated miss-by-1 / thin-cushion profile."
            )
            reasons.append("PROP_THIN_CLOSE_GATE")
        elif is_modeled_prop_sport and candidate.average_cushion is not None:
            from app.services.player_prop_research import min_prop_cushion

            floor = min_prop_cushion(candidate)
            if float(candidate.average_cushion) < floor:
                hard_skip_reasons.append(
                    f"Player prop blocked: average L10 cushion below the {floor:g} minimum."
                )
                reasons.append("PROP_CUSHION_GATE")
        elif miss_by_one_risk >= 0.80 and not verified_safer_alternative(
            candidate.safer_alternative
        ):
            hard_skip_reasons.append(
                "Miss-by-1 risk is critical and no verified safer line was supplied "
                "(placeholder text does not count)."
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

        # Weekly-report calculation discipline (lessons 1–4, 11–12).
        for code in identity_blockers(candidate):
            hard_skip_reasons.append(
                "Identity verification failed before any market math could run "
                f"({code})."
            )
            reasons.append(code)
        for code in market_series_blockers(candidate):
            hard_skip_reasons.append(
                "Exact market series (L5/L10 / median vs line) is missing or fails "
                f"the offered threshold ({code})."
            )
            reasons.append(code)
        for code in line_shave_blockers(candidate):
            hard_skip_reasons.append(
                "Shorter line is not automatically safer without outcome-distribution "
                f"evidence ({code})."
            )
            reasons.append(code)
        for code in protective_dog_spread_blockers(candidate):
            hard_skip_reasons.append(
                "Protective underdog spread lacks an affirmative matchup/script/cushion "
                f"case ({code})."
            )
            reasons.append(code)
        for code in minutes_not_production_blockers(candidate):
            hard_skip_reasons.append(
                "Minutes/opportunity alone are not production evidence for this volume "
                f"prop ({code})."
            )
            reasons.append(code)
        for code in heavy_juice_blockers(
            american_odds=int(candidate.american_odds),
            edge=float(edge),
            independent_value_verified=bool(candidate.independent_value_verified),
            heavily_juiced_filler=bool(candidate.heavily_juiced_filler),
        ):
            hard_skip_reasons.append(
                "Heavy juice / short price is not evidence of safety without independent "
                f"edge ({code})."
            )
            reasons.append(code)

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

        from app.services.board_metrics import FORM_PROP_OUTLIER_EDGE_REVIEW

        form_prop = bool(candidate.l5_l10_verified) and candidate.probability_source in {
            "model",
            "manual_verified",
        } and (
            str(candidate.market_type or "").startswith("player_")
            or str(candidate.market_type or "").startswith("pitcher_")
            or "strikeout" in str(candidate.market_type or "").lower()
            or str(candidate.data_source or "") == "ESPN_PLAYER_PROP_MODEL"
            or "MLB_STATS" in str(candidate.data_source or "").upper()
        )
        outlier_codes = outlier_review_reasons(
            adjusted_probability=adjusted,
            american_odds=candidate.american_odds,
            probability_source=candidate.probability_source,
            edge_review_threshold=FORM_PROP_OUTLIER_EDGE_REVIEW if form_prop else None,
        )
        review_reasons: list[str] = []
        if outlier_codes:
            review_reasons.extend(
                [
                    "Model probability is an unresolved outlier versus the sportsbook "
                    "break-even price and requires REVIEW before any official card."
                ]
            )
            reasons.extend(outlier_codes)
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
        wait_codes = wait_reasons(candidate, hard_skip_reasons + reasons)
        fatal_codes = {
            "IDENTITY_PLAYER_KEY_MISSING",
            "IDENTITY_SELECTION_TOO_THIN",
            "IDENTITY_EVENT_MISSING",
            "HEAVY_JUICE_NOT_SAFETY",
            "FILLER_LEG_TAX",
            "PROTECTIVE_DOG_WITHOUT_AFFIRMATIVE_CASE",
            "LINE_SHAVE_WITHOUT_DISTRIBUTION",
            "MARKET_MEDIAN_DOES_NOT_CLEAR_LINE",
            "MARKET_SERIES_TOO_SHORT",
            "MARKET_SERIES_UNPARSEABLE",
            "PROP_THIN_CLOSE_GATE",
            "PROP_CUSHION_GATE",
            "MISS_BY_ONE_GATE_FAILED",
            "NO_CLEAN_EDGE",
            "ODDS_TOO_EXPENSIVE",
            "DEMO_DATA",
            "NO_INDEPENDENT_PROBABILITY",
            "DATA_QUALITY_BAD",
            "GAME_NOT_PRE_GAME",
            "MARKET_NOT_OPEN",
            "FIRST_START_BACK_EXCLUSION",
            "K_DURATION_GATE_FAILED",
            "LINE_ESCALATION_BLOCKED",
            "LOW_TOTAL_TWO_PATH_GATE_FAILED",
            "PREVIOUS_GAME_RECENCY_BLOCK",
            "EXTRA_TIME_TRAP",
        }
        has_fatal = bool(set(reasons) & fatal_codes)
        if hard_skip_reasons and has_fatal:
            decision = Decision.skip.value
            confidence = min(confidence, 69)
        elif hard_skip_reasons and wait_codes and not has_fatal:
            # Lesson 13 — incomplete evidence → WAIT / NO PICK YET.
            decision = Decision.wait.value
            confidence = min(confidence, 72)
            reasons.extend(wait_codes)
            reasons.append("NO_PICK_YET")
            warnings.append("WAIT — evidence incomplete. Correct output can be NO BET.")
        elif hard_skip_reasons:
            decision = Decision.skip.value
            confidence = min(confidence, 69)
        elif review_reasons:
            # Unresolved calibration / mapping outliers — visible REVIEW, never official PLAY.
            decision = Decision.review.value
            confidence = min(confidence, 80)
            warnings.extend(review_reasons)
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
        elif decision == Decision.wait.value:
            yis = min(yis, 6.2)
        elif decision == Decision.review.value:
            yis = min(yis, 6.5)

        if decision in {Decision.skip.value, Decision.review.value, Decision.wait.value}:
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
        elif decision == Decision.wait.value:
            tier = "wait"
        elif decision == Decision.review.value:
            tier = "review"
        elif confidence >= 90 and risk == "low" and miss_by_one_risk < 0.55:
            tier = "cash_builder"
        elif (
            confidence >= 88
            and miss_by_one_risk < 0.55
            and risk in {"low", "medium"}
        ):
            # Multi-leg tag only when the leg itself is not a ticket-killer.
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
                f"Quality-adjusted probability is {adjusted:.1%} versus "
                f"{fair_implied:.1%} fair (de-vigged) implied."
            )
        if hard_skip_reasons:
            reasoning_parts.append("Official YWP output: SKIP / NO PLAY.")
        elif review_reasons:
            reasoning_parts.append(
                "Official YWP output: REVIEW — excluded from official cards until "
                "the probability outlier is resolved (not capped away)."
            )
        if not reasoning_parts:
            reasoning_parts.append(
                "Recommendation is derived only from the supplied structured inputs."
            )

        market_l = str(candidate.market_type or "").lower()
        selection_l = str(candidate.selection or "").lower()
        is_over = "over" in market_l or " over " in f" {selection_l} "
        line_f = float(candidate.line) if candidate.line is not None else None
        mean_f = None
        if line_f is not None and candidate.average_cushion is not None:
            mean_f = line_f + float(candidate.average_cushion) if is_over else line_f - float(
                candidate.average_cushion
            )
        pipe = run_leg_pipeline(
            decision=decision,
            confidence_score=confidence,
            edge=edge,
            miss_by_one_risk=miss_by_one_risk,
            reason_codes=reasons,
            model_probability=adjusted,
            american_odds=candidate.american_odds,
            opposite_american_odds=candidate.opposite_american_odds,
            line=line_f,
            is_over=is_over,
            mean=mean_f,
            sigma=None,
            hit_rate=candidate.recent_hit_rate,
            cushion_scale=float(candidate.cushion_scale),
            verification_status=readiness,
            role_stability=candidate.role_stability,
            context_scores={
                "matchup_score": candidate.matchup_score,
                "script_alignment": candidate.script_alignment,
                "multiple_paths_score": candidate.multiple_paths_score,
                "role_stability": candidate.role_stability,
            },
            readiness=readiness,
        )
        payload["pipeline"] = pipe
        payload["pipeline_threshold"] = pipe["pipeline_threshold"]
        payload["pipeline_distribution"] = pipe["distribution"]
        payload["model_probability"] = adjusted

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

    def apply_hive_calibration(
        self,
        evaluation: Evaluation,
        hive_probability: float,
        *,
        shift_applied: float,
    ) -> Evaluation:
        """Apply a bounded Hive calibration to a finished evaluation.

        Fail-closed: never undoes research / independent-probability hard skips.
        May only change edge/EV/decision among candidates that already had a
        usable independent model probability.
        """
        blocked = {
            "RESEARCH_INCOMPLETE",
            "NO_INDEPENDENT_PROBABILITY",
            "DATA_QUALITY_BAD",
            "DATA_ANOMALY",
            "PREVIOUS_GAME_RECENCY_BLOCK",
            "EXTRA_TIME_TRAP",
        }
        if any(code in evaluation.reason_codes for code in blocked):
            return evaluation

        implied = evaluation.implied_probability
        adjusted = clamp(float(hive_probability), 0.01, 0.99)
        market_cmp = compare_to_market(
            model_probability=adjusted,
            american_odds=evaluation.candidate.american_odds,
            opposite_american_odds=evaluation.candidate.opposite_american_odds,
        )
        fair_implied = float(market_cmp["fair_implied_probability"])
        implied = fair_implied
        edge = adjusted - fair_implied
        expected_value = adjusted * american_to_decimal(evaluation.candidate.american_odds) - 1
        confidence = evaluation.confidence_score
        evaluation.payload["market_comparison"] = market_cmp
        evaluation.payload["fair_implied_probability"] = fair_implied

        # Drop edge-only skip reasons so we can re-evaluate them from the Hive probability.
        soft_edge_codes = {"NO_CLEAN_EDGE", "ODDS_TOO_EXPENSIVE", "CONFIDENCE_BELOW_THRESHOLD"}
        reasons = [code for code in evaluation.reason_codes if code not in soft_edge_codes]
        warnings = list(evaluation.warnings)

        if "HIVE_CALIBRATION" not in reasons:
            reasons.append("HIVE_CALIBRATION")
        warnings.append(
            f"Hive calibration shifted model probability by {shift_applied:+.3%} "
            f"(bounded living evidence)."
        )

        hard_skip = False
        if edge < settings.minimum_edge or expected_value <= 0:
            hard_skip = True
            reasons.extend(["NO_CLEAN_EDGE", "ODDS_TOO_EXPENSIVE"])

        if hard_skip:
            decision = Decision.skip.value
            confidence = min(confidence, 69)
        elif evaluation.decision == Decision.review.value or "MODEL_EDGE_QUARANTINE" in reasons:
            decision = Decision.review.value
            confidence = min(confidence, 80)
        elif confidence >= 85 and edge >= 0.03:
            decision = Decision.play.value
        elif confidence >= 75 and edge >= settings.minimum_edge:
            decision = Decision.lean.value
        elif confidence >= 70:
            decision = Decision.watch.value
        else:
            decision = Decision.skip.value
            reasons.append("CONFIDENCE_BELOW_THRESHOLD")

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

        quality = clamp(evaluation.candidate.data_quality, 0, 1)
        yis = 10 * (
            0.30 * (confidence / 100)
            + 0.20 * (evaluation.vision_score / 10)
            + 0.15 * evaluation.reliability
            + 0.15 * evaluation.stability
            + 0.10 * quality
            + 0.10 * clamp((expected_value + 0.02) / 0.18, 0, 1)
        )
        if decision == Decision.skip.value:
            yis = min(yis, 5.9)
            tier = "stay_away"
            suggested_stake_pct = 0.0
        elif decision == Decision.review.value:
            yis = min(yis, 6.5)
            tier = "review"
            suggested_stake_pct = 0.0
        elif confidence >= 90 and evaluation.risk == "low" and evaluation.miss_by_one_risk < 0.55:
            tier = "cash_builder"
            suggested_stake_pct = evaluation.suggested_stake_pct
        elif (
            confidence >= 88
            and evaluation.miss_by_one_risk < 0.55
            and evaluation.risk in {"low", "medium"}
        ):
            tier = "core_parlay"
            suggested_stake_pct = evaluation.suggested_stake_pct
        elif expected_value >= 0.08:
            tier = "edge_play"
            suggested_stake_pct = evaluation.suggested_stake_pct
        else:
            tier = "support"
            suggested_stake_pct = evaluation.suggested_stake_pct

        summary = evaluation.reasoning_summary
        hive_note = (
            f" Living Hive calibration applied ({shift_applied:+.3%}); "
            f"working probability {adjusted:.1%} vs {implied:.1%} implied."
        )
        if "Living Hive calibration" not in summary:
            summary = f"{summary}{hive_note}".strip()

        evaluation.adjusted_probability = adjusted
        evaluation.edge = edge
        evaluation.expected_value = expected_value
        evaluation.confidence_score = confidence
        evaluation.decision = decision
        evaluation.recommendation_tier = tier
        evaluation.edge_class = edge_class
        evaluation.expected_value_label = expected_value_label
        evaluation.ywp_intelligence_score = round(yis, 2)
        evaluation.suggested_stake_pct = round(suggested_stake_pct, 4)
        evaluation.reason_codes = list(dict.fromkeys(reasons))
        evaluation.warnings = list(dict.fromkeys(warnings))
        evaluation.reasoning_summary = summary
        evaluation.payload["hive_working_probability"] = adjusted
        evaluation.payload["pre_hive_probability"] = evaluation.payload.get(
            "model_probability", evaluation.payload.get("pre_hive_probability")
        )
        return evaluation

    def rank(self, evaluations: list[Evaluation]) -> list[Evaluation]:
        gated = self.apply_slate_integrity_gates(evaluations)
        priority = {
            Decision.play.value: 0,
            Decision.lean.value: 1,
            Decision.watch.value: 2,
            Decision.review.value: 3,
            Decision.skip.value: 4,
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
