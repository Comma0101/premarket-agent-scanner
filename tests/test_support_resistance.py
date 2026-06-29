from app.models import IntradayBar, IntradayBarSeries
from services.support_resistance_service import SupportResistanceService


def _make_daily(h: float, low_val: float, ts: str = "2026-06-25T00:00:00Z") -> IntradayBar:
    return IntradayBar(
        ticker="TEST",
        timestamp=ts,
        open=10.0,
        high=h,
        low=low_val,
        close=10.0,
        volume=1000,
        timeframe="1Day"
    )


def test_detect_daily_pivots():
    svc = SupportResistanceService()
    
    # We need left=2, right=2 for a quicker test (total 5 bars min)
    bars = [
        _make_daily(h=10.0, low_val=5.0, ts="day1"),
        _make_daily(h=11.0, low_val=4.0, ts="day2"),
        _make_daily(h=15.0, low_val=3.0, ts="day3"),  # Peak high (resistance), Peak low (support)
        _make_daily(h=12.0, low_val=4.0, ts="day4"),
        _make_daily(h=11.0, low_val=5.0, ts="day5"),
    ]
    history = IntradayBarSeries("TEST", "1Day", bars, "mock", "now")
    
    pivots = svc.detect_daily_pivots(history, left_bars=2, right_bars=2)
    
    assert len(pivots) == 2
    
    # Resistance pivot
    res = [p for p in pivots if p.pivot_type == "resistance"][0]
    assert res.price == 15.0
    assert res.timestamp == "day3"
    
    # Support pivot
    sup = [p for p in pivots if p.pivot_type == "support"][0]
    assert sup.price == 3.0
    assert sup.timestamp == "day3"


def test_no_pivots():
    svc = SupportResistanceService()
    # Continuous uptrend, no fractal pivots
    bars = [
        _make_daily(h=10.0, low_val=5.0, ts="day1"),
        _make_daily(h=11.0, low_val=6.0, ts="day2"),
        _make_daily(h=12.0, low_val=7.0, ts="day3"),
        _make_daily(h=13.0, low_val=8.0, ts="day4"),
        _make_daily(h=14.0, low_val=9.0, ts="day5"),
    ]
    history = IntradayBarSeries("TEST", "1Day", bars, "mock", "now")
    
    pivots = svc.detect_daily_pivots(history, left_bars=2, right_bars=2)
    assert len(pivots) == 0
