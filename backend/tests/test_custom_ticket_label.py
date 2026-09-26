from app.api.tickets import _custom_label


def test_custom_label_matches_leg_count() -> None:
    assert _custom_label(1) == "Custom 1-leg"
    assert _custom_label(2) == "Custom 2-legs"
    assert _custom_label(5) == "Custom 5-legs"
