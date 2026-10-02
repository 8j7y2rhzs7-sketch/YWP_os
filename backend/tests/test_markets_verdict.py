"""Shared verdict ladder matches the sports thresholds, including WAIT."""

from app.services.core.verdict import (
    PLAY_EDGE,
    assign_verdict,
    edge_class_label,
    quarter_kelly_stake,
)
from app.services.decision_engine import _edge_class_label
from app.services.ywp_quant.sizing import fractional_kelly


def test_edge_class_matches_sports_engine() -> None:
    samples = [
        (0.09, 95, []),
        (0.06, 80, []),
        (0.04, 80, []),
        (0.02, 80, []),
        (0.0, 90, []),
        (0.10, 95, ["OUTLIER_EDGE"]),
        (0.10, 95, ["MODEL_EDGE_QUARANTINE"]),
    ]
    for edge, confidence, reasons in samples:
        assert edge_class_label(edge, confidence, reasons) == _edge_class_label(
            edge, confidence, reasons
        )


def test_play_lean_watch_skip_thresholds() -> None:
    play = assign_verdict(edge=PLAY_EDGE, expected_value=0.04, confidence=90)
    assert play.decision == "PLAY"
    assert play.suggested_stake_pct > 0

    lean = assign_verdict(edge=0.02, expected_value=0.02, confidence=78)
    assert lean.decision == "LEAN"

    watch = assign_verdict(edge=0.02, expected_value=0.02, confidence=72)
    assert watch.decision == "WATCH"

    quiet = assign_verdict(edge=0.02, expected_value=0.02, confidence=60)
    assert quiet.decision == "SKIP"
    assert "CONFIDENCE_BELOW_THRESHOLD" in quiet.reason_codes
    assert quiet.suggested_stake_pct == 0


def test_wait_when_evidence_is_incomplete_and_edge_exists() -> None:
    verdict = assign_verdict(
        edge=0.04,
        expected_value=0.05,
        confidence=92,
        reasons=["SOURCE_UNCONFIRMED"],
        hard_skip_reasons=["A second price source did not confirm this quote."],
        wait_codes=["SOURCE_UNCONFIRMED"],
    )
    assert verdict.decision == "WAIT"
    assert verdict.tier == "wait"
    assert verdict.suggested_stake_pct == 0
    assert "NO_PICK_YET" in verdict.reason_codes


def test_no_edge_is_skip_not_wait() -> None:
    verdict = assign_verdict(
        edge=0.001,
        expected_value=-0.01,
        confidence=92,
        reasons=["SOURCE_UNCONFIRMED"],
        hard_skip_reasons=["A second price source did not confirm this quote."],
        wait_codes=["SOURCE_UNCONFIRMED"],
    )
    assert verdict.decision == "SKIP"
    assert "NO_CLEAN_EDGE" in verdict.reason_codes


def test_review_blocks_play() -> None:
    verdict = assign_verdict(
        edge=0.08,
        expected_value=0.1,
        confidence=95,
        review_reasons=["Contract rules do not match the model question."],
    )
    assert verdict.decision == "REVIEW"
    assert verdict.suggested_stake_pct == 0


def test_quarter_kelly_matches_sports_sizer() -> None:
    shared = quarter_kelly_stake(0.62, -110, lower_90=0.55)
    direct = fractional_kelly(0.62, -110, fraction=0.25, lower_90=0.55)
    assert shared["recommended_stake_pct"] == direct["recommended_stake_pct"]
    assert shared["fraction"] == 0.25
