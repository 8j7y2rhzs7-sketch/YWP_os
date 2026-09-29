from app.services.metacognition import (
    list_metacognition_feed,
    reflect_on_decision,
    reflect_on_self_improve_cycle,
)


def test_reflect_on_decision_skip_research():
    meta = reflect_on_decision(
        decision="SKIP",
        reason_codes=["RESEARCH_INCOMPLETE", "NO_INDEPENDENT_PROBABILITY"],
        warnings=["Missing fields: form"],
        reasoning_summary="Official YWP output: SKIP / NO PLAY.",
        selection="Georgia Amoore Over 8.5 points",
        hive_meta={"used": False, "reason": "insufficient_hive_sample"},
        probability_source="market_implied",
    )
    assert meta["kind"] == "decision"
    assert "WHY" not in meta["why"]  # field itself is the why text
    assert "Strict Mode" in meta["why"] or "blocked" in meta["why"].lower()
    assert "Hive" in meta["system_impact"] or "SKIP" in meta["system_impact"]
    assert "Warm prop" in meta["next_time"] or "research" in meta["next_time"].lower()


def test_reflect_on_decision_play_with_hive():
    meta = reflect_on_decision(
        decision="PLAY",
        reason_codes=["INDEPENDENT_MODEL"],
        warnings=[],
        reasoning_summary="Model edge cleared gates.",
        selection="Team A ML",
        hive_meta={"used": True, "shift_applied": 0.02},
        probability_source="model",
    )
    assert "PLAY" in meta["why"]
    assert "calibration" in meta["why"].lower() or "Hive" in meta["why"]
    assert "tickets" in meta["system_impact"].lower()
    assert "Sync Scores" in meta["next_time"]


def test_reflect_on_self_improve_promoted():
    meta = reflect_on_self_improve_cycle(
        promoted=True,
        winner="inhibit_worst_bucket",
        explanation="Promoted inhibit_worst_bucket.",
        baseline={"brier": 0.22, "n": 40},
        trials=[{"idea": "a"}, {"idea": "b"}],
        trigger="settle",
        sport="wnba",
    )
    assert meta["kind"] == "self_improve"
    assert "Promoted" in meta["system_impact"]
    assert "roll" in meta["next_time"].lower() or "Watch" in meta["next_time"]


def test_list_metacognition_feed_backfills_missing_block():
    feed = list_metacognition_feed(
        cycles=[
            {
                "id": "c1",
                "created_at": "2026-09-23T00:00:00+00:00",
                "promoted": False,
                "winner": "current",
                "explanation": "Kept current.",
                "baseline": {"brier": 0.2, "n": 10},
                "trial_count": 3,
            }
        ],
        limit=5,
    )
    assert len(feed) == 1
    assert feed[0]["metacognition"]["why"]
    assert feed[0]["metacognition"]["system_impact"]
    assert feed[0]["metacognition"]["next_time"]
