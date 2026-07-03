from app.models import IntradayBar, IntradayBarSeries
from services.intraday_technicals_service import IntradayTechnicalsService


def _make_bar(close_val: float) -> IntradayBar:
    return IntradayBar(
        ticker="TEST",
        timestamp="2026-06-25T14:00:00Z",
        open=close_val,
        high=close_val,
        low=close_val,
        close=close_val,
        volume=100,
        timeframe="2Min",
    )


def test_compute_ema():
    svc = IntradayTechnicalsService()
    
    # 5 bars, periods = 3
    # Prices: 10, 11, 12, 13, 14
    bars = [_make_bar(v) for v in [10.0, 11.0, 12.0, 13.0, 14.0]]
    series = IntradayBarSeries("TEST", "2Min", bars, "mock", "now")
    
    ema = svc.compute_ema(series, periods=3)
    
    assert len(ema) == 5
    assert ema[0] is None
    assert ema[1] is None
    
    # Initial SMA = (10+11+12)/3 = 11.0
    assert ema[2] == 11.0
    
    # K = 2 / (3 + 1) = 0.5
    # EMA[3] = (13 - 11) * 0.5 + 11 = 12.0
    assert ema[3] == 12.0
    
    # EMA[4] = (14 - 12) * 0.5 + 12 = 13.0
    assert ema[4] == 13.0


def test_compute_ema_not_enough_bars():
    svc = IntradayTechnicalsService()
    bars = [_make_bar(10.0), _make_bar(11.0)]
    series = IntradayBarSeries("TEST", "2Min", bars, "mock", "now")
    
    ema = svc.compute_ema(series, periods=3)
    assert ema == [None, None]
