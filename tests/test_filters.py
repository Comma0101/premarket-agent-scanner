from app.models import ScanFilters, ScannerResult
from services.gap_scanner import passes_filters


def result(**kwargs):
    base = dict(ticker="A", name=None, universe=None, market_cap=10, previous_close=10, premarket_price=11, latest_price=11, gap_pct=10, volume=None, confidence="OK", notes=None)
    base.update(kwargs)
    return ScannerResult(**base)


def test_market_cap_includes_above_threshold():
    assert passes_filters(result(market_cap=20), ScanFilters(min_market_cap=10))


def test_market_cap_excludes_below_threshold():
    assert not passes_filters(result(market_cap=5), ScanFilters(min_market_cap=10))


def test_market_cap_handles_missing():
    assert not passes_filters(result(market_cap=None), ScanFilters(min_market_cap=10))


def test_direction_up_only():
    assert passes_filters(result(gap_pct=1), ScanFilters(direction="up"))
    assert not passes_filters(result(gap_pct=-1), ScanFilters(direction="up"))


def test_direction_down_only():
    assert passes_filters(result(gap_pct=-1), ScanFilters(direction="down"))
    assert not passes_filters(result(gap_pct=1), ScanFilters(direction="down"))


def test_direction_both():
    assert passes_filters(result(gap_pct=-1), ScanFilters(direction="both"))
    assert passes_filters(result(gap_pct=1), ScanFilters(direction="both"))
