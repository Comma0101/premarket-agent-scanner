from services.confidence import calculate_gap_pct


def test_positive_gap():
    assert calculate_gap_pct(110, 100) == 10


def test_negative_gap():
    assert calculate_gap_pct(90, 100) == -10


def test_zero_gap():
    assert calculate_gap_pct(100, 100) == 0


def test_missing_previous_close():
    assert calculate_gap_pct(100, None) is None


def test_previous_close_zero():
    assert calculate_gap_pct(100, 0) is None
