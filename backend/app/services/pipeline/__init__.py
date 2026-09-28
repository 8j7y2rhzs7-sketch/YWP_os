"""YWP OS edge pipeline — nine stages from verification through calibration."""

from app.services.pipeline.calibration import brier_score, summarize_calibration
from app.services.pipeline.correlation import correlation_matrix, pairwise_correlation
from app.services.pipeline.distribution import estimate_stat_distribution
from app.services.pipeline.market_math import compare_to_market, devig_two_way, implied_from_american
from app.services.pipeline.monte_carlo import simulate_ticket
from app.services.pipeline.runner import PIPELINE_STAGES, run_leg_pipeline, run_ticket_pipeline
from app.services.pipeline.threshold import map_decision_threshold

__all__ = [
    "PIPELINE_STAGES",
    "brier_score",
    "compare_to_market",
    "correlation_matrix",
    "devig_two_way",
    "estimate_stat_distribution",
    "implied_from_american",
    "map_decision_threshold",
    "pairwise_correlation",
    "run_leg_pipeline",
    "run_ticket_pipeline",
    "simulate_ticket",
    "summarize_calibration",
]
