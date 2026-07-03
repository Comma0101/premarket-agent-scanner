from app.models import IntradayBar, IntradayBarSeries, utc_now_iso
from services.intraday_analysis_service import IntradayAnalysisService
from tests.test_alpaca_bars import FakeBarProvider


def _make_bar(ticker, timestamp, o, h, low_val, c, v, timeframe="2Min"):
    return IntradayBar(
        ticker=ticker,
        timestamp=timestamp,
        open=o,
        high=h,
        low=low_val,
        close=c,
        volume=v,
        timeframe=timeframe,
    )


def _make_series(ticker, ohlcv_list, timeframe="2Min", source="test"):
    bars = [
        _make_bar(ticker, f"2026-06-29T14:{i:02d}:00Z", o, h, low_val, c, v, timeframe)
        for i, (o, h, low_val, c, v) in enumerate(ohlcv_list)
    ]
    return IntradayBarSeries(
        ticker=ticker,
        timeframe=timeframe,
        bars=bars,
        source=source,
        fetched_at=utc_now_iso(),
    )


def test_compute_vwap_known_values():
    # 2 bars: bar1 TP=100, vol=1000; bar2 TP=110, vol=2000
    # VWAP = (100*1000 + 110*2000) / (1000+2000) = 320000/3000 = 106.67
    series = _make_series("TEST", [
        (99, 102, 98, 100, 1000),
        (109, 112, 108, 110, 2000),
    ])
    svc = IntradayAnalysisService()
    vwap = svc.compute_vwap(series)
    assert vwap is not None
    assert abs(vwap - 106.667) < 0.01


def test_compute_vwap_empty_series():
    series = IntradayBarSeries(ticker="X", timeframe="2Min", bars=[], source="test", fetched_at=utc_now_iso())
    svc = IntradayAnalysisService()
    assert svc.compute_vwap(series) is None


def test_compute_vwap_zero_volume():
    series = _make_series("TEST", [
        (100, 101, 99, 100, 0),
        (100, 101, 99, 100, 0),
    ])
    svc = IntradayAnalysisService()
    assert svc.compute_vwap(series) is None


def test_compute_prior_bar_levels():
    series = _make_series("TEST", [
        (100, 105, 95, 100, 1000),
        (101, 108, 96, 102, 2000),  # prior bar: high=108, low=96
        (103, 110, 97, 104, 3000),  # last bar
    ])
    svc = IntradayAnalysisService()
    high, low = svc.compute_prior_bar_levels(series)
    assert high == 108
    assert low == 96


def test_compute_prior_bar_levels_insufficient_bars():
    series = _make_series("TEST", [(100, 101, 99, 100, 1000)])
    svc = IntradayAnalysisService()
    high, low = svc.compute_prior_bar_levels(series)
    assert high is None
    assert low is None


def test_check_volume_2x_true():
    series = _make_series("TEST", [
        (100, 101, 99, 100, 1000),
        (101, 102, 100, 101, 2500),  # last bar vol 2500 >= 2*1000
    ])
    svc = IntradayAnalysisService()
    assert svc.check_volume_2x(series) is True


def test_check_volume_2x_false():
    series = _make_series("TEST", [
        (100, 101, 99, 100, 1000),
        (101, 102, 100, 101, 1500),  # 1500 < 2*1000
    ])
    svc = IntradayAnalysisService()
    assert svc.check_volume_2x(series) is False


def test_check_volume_2x_insufficient_bars():
    series = _make_series("TEST", [(100, 101, 99, 100, 1000)])
    svc = IntradayAnalysisService()
    assert svc.check_volume_2x(series) is None


def test_consecutive_down_bars():
    # 5 bars, each closing lower than the one before
    series = _make_series("TEST", [
        (105, 106, 104, 105, 1000),
        (104, 105, 103, 104, 1000),
        (103, 104, 102, 103, 1000),
        (102, 103, 101, 102, 1000),
        (101, 102, 100, 101, 2000),  # 4 consecutive down
    ])
    svc = IntradayAnalysisService()
    result = svc.compute_consecutive_bars(series)
    assert result == -4  # negative = down streak


def test_consecutive_up_bars():
    series = _make_series("TEST", [
        (100, 101, 99, 100, 1000),
        (100, 102, 100, 101, 1000),
        (101, 103, 101, 102, 1000),
        (102, 104, 102, 103, 1000),
        (103, 105, 103, 104, 2000),  # 4 consecutive up
    ])
    svc = IntradayAnalysisService()
    result = svc.compute_consecutive_bars(series)
    assert result == 4  # positive = up streak


def test_consecutive_bars_mixed():
    series = _make_series("TEST", [
        (100, 101, 99, 100, 1000),
        (100, 102, 100, 101, 1000),
        (101, 102, 100, 100, 1000),  # down
        (100, 101, 99, 99, 2000),    # down again = 2 consecutive down
    ])
    svc = IntradayAnalysisService()
    result = svc.compute_consecutive_bars(series)
    assert result == -2


def test_compute_rate_of_change():
    # 6 bars; last close=110, 5-bars-ago close=100 → +10%
    series = _make_series("TEST", [
        (100, 101, 99, 100, 1000),  # 5 bars ago
        (101, 102, 100, 101, 1000),
        (102, 103, 101, 102, 1000),
        (103, 104, 102, 103, 1000),
        (104, 105, 103, 104, 1000),
        (110, 111, 109, 110, 2000),  # last bar
    ])
    svc = IntradayAnalysisService()
    roc = svc.compute_rate_of_change(series, bars_back=5)
    assert roc is not None
    assert abs(roc - 10.0) < 0.01


def test_compute_rate_of_change_insufficient_bars():
    series = _make_series("TEST", [
        (100, 101, 99, 100, 1000),
        (101, 102, 100, 101, 1000),
    ])
    svc = IntradayAnalysisService()
    assert svc.compute_rate_of_change(series, bars_back=5) is None


def test_compute_bollinger_width():
    # 20 bars with known std; just verify it returns a positive number
    bars = [(100 + i * 0.1, 100.5 + i * 0.1, 99.5 + i * 0.1, 100 + i * 0.1, 1000) for i in range(20)]
    series = _make_series("TEST", bars)
    svc = IntradayAnalysisService()
    width = svc.compute_bollinger_width(series)
    assert width is not None
    assert width > 0


def test_compute_bollinger_width_insufficient_bars():
    bars = [(100, 101, 99, 100, 1000) for _ in range(10)]
    series = _make_series("TEST", bars)
    svc = IntradayAnalysisService()
    assert svc.compute_bollinger_width(series, period=20) is None


def test_compute_20_period_ma():
    bars = [(100 + i, 101 + i, 99 + i, 100 + i, 1000) for i in range(25)]
    series = _make_series("TEST", bars)
    svc = IntradayAnalysisService()
    ma = svc.compute_20_period_ma(series)
    expected = sum(100 + i for i in range(5, 25)) / 20  # last 20 closes
    assert ma is not None
    assert abs(ma - expected) < 0.01


def test_compute_20_period_ma_insufficient_bars():
    bars = [(100, 101, 99, 100, 1000) for _ in range(15)]
    series = _make_series("TEST", bars)
    svc = IntradayAnalysisService()
    assert svc.compute_20_period_ma(series) is None


def test_detect_long_entry_signal():
    # 3+ consecutive down bars, then a bar that breaks above prior bar high with 2x volume
    series = _make_series("TEST", [
        (110, 111, 109, 110, 1000),  # up
        (109, 110, 108, 109, 1000),  # down
        (108, 109, 107, 108, 1000),  # down
        (107, 108, 106, 107, 1000),  # down (3 consecutive down)
        (108, 110, 107, 109, 2000),  # breaks above prior high (108), vol 2x
    ])
    svc = IntradayAnalysisService()
    signal = svc.detect_entry_signal(series, vwap=108.0)
    assert signal is not None
    assert signal.direction == "long"
    assert signal.entry_price == 109
    assert signal.stop_price == 106  # prior bar low
    assert signal.prior_bar_high == 108
    assert signal.prior_bar_low == 106
    assert signal.volume_2x_confirmed is True
    assert signal.consecutive_bars == -3  # was 3 down before the breakout bar


def test_detect_short_entry_signal():
    # 3+ consecutive up bars, then a bar that breaks below prior bar low with 2x volume
    series = _make_series("TEST", [
        (100, 101, 99, 100, 1000),
        (100, 102, 100, 101, 1000),  # up
        (101, 103, 101, 102, 1000),  # up
        (102, 104, 102, 103, 1000),  # up (3 consecutive up)
        (102, 103, 100, 101, 2000),  # breaks below prior low (102), vol 2x
    ])
    svc = IntradayAnalysisService()
    signal = svc.detect_entry_signal(series, vwap=102.0)
    assert signal is not None
    assert signal.direction == "short"
    assert signal.entry_price == 101
    assert signal.stop_price == 104  # prior bar high
    assert signal.volume_2x_confirmed is True


def test_no_signal_insufficient_consecutive_bars():
    # Only 2 consecutive down bars
    series = _make_series("TEST", [
        (110, 111, 109, 110, 1000),
        (109, 110, 108, 109, 1000),  # down
        (108, 109, 107, 108, 1000),  # down (only 2)
        (109, 110, 107, 109, 2000),
    ])
    svc = IntradayAnalysisService()
    signal = svc.detect_entry_signal(series, vwap=108.0)
    assert signal is None


def test_no_signal_no_volume_2x():
    # 3 consecutive down bars but no 2x volume on last bar
    series = _make_series("TEST", [
        (110, 111, 109, 110, 1000),
        (109, 110, 108, 109, 1000),  # down
        (108, 109, 107, 108, 1000),  # down
        (107, 108, 106, 107, 1000),  # down (3 consecutive)
        (108, 110, 107, 109, 1200),  # vol only 1.2x, not 2x
    ])
    svc = IntradayAnalysisService()
    signal = svc.detect_entry_signal(series, vwap=108.0)
    assert signal is None


def test_no_signal_no_prior_bar_break():
    # 3 consecutive down + 2x volume, but close does NOT break prior bar high
    series = _make_series("TEST", [
        (110, 111, 109, 110, 1000),
        (109, 110, 108, 109, 1000),  # down
        (108, 109, 107, 108, 1000),  # down
        (107, 108, 106, 107, 1000),  # down (prior high = 108)
        (107, 107.5, 106, 107, 2000),  # close 107 <= prior high 108 — no break
    ])
    svc = IntradayAnalysisService()
    signal = svc.detect_entry_signal(series, vwap=108.0)
    assert signal is None


def test_signal_with_missing_vwap():
    series = _make_series("TEST", [
        (110, 111, 109, 110, 1000),
        (109, 110, 108, 109, 1000),
        (108, 109, 107, 108, 1000),
        (107, 108, 106, 107, 1000),
        (108, 110, 107, 109, 2000),
    ])
    svc = IntradayAnalysisService()
    signal = svc.detect_entry_signal(series, vwap=None)
    assert signal is not None
    assert "vwap" in signal.missing_fields
    assert signal.confidence == "LOW_CONFIDENCE"


def test_detect_chop_compression():
    # 20 bars with tiny range — should be chop
    bars = [(100, 100.1, 99.9, 100, 1000) for _ in range(20)]
    series = _make_series("TEST", bars)
    svc = IntradayAnalysisService()
    assert svc.detect_chop(series) is True


def test_detect_chop_expanding():
    # 20 bars with expanding range — should not be chop
    bars = [(100 + i * 2, 100 + i * 2 + 1, 100 + i * 2 - 1, 100 + i * 2, 1000) for i in range(20)]
    series = _make_series("TEST", bars)
    svc = IntradayAnalysisService()
    assert svc.detect_chop(series) is False


def test_detect_chop_insufficient_bars():
    series = _make_series("TEST", [(100, 101, 99, 100, 1000) for _ in range(10)])
    svc = IntradayAnalysisService()
    assert svc.detect_chop(series) is None


def test_fetch_bars_and_analyze():
    fake_series = _make_series("AAPL", [
        (110, 111, 109, 110, 1000),
        (109, 110, 108, 109, 1000),
        (108, 109, 107, 108, 1000),
        (107, 108, 106, 107, 1000),
        (108, 110, 107, 109, 2000),
    ])
    provider = FakeBarProvider({"AAPL": fake_series})
    svc = IntradayAnalysisService(bar_provider=provider)
    series = svc.fetch_bars("AAPL")
    assert len(series.bars) == 5
    signal = svc.detect_entry_signal(series, vwap=108.0)
    assert signal is not None
    assert signal.direction == "long"
