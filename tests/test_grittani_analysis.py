from app.models import IntradayBar, IntradayBarSeries
from services.grittani_analysis_service import GrittaniAnalysisService


class MockProvider:
    def __init__(self, intraday_bars: list[IntradayBar], daily_bars: list[IntradayBar]):
        self.intraday_bars = intraday_bars
        self.daily_bars = daily_bars

    def get_bars(self, ticker: str, timeframe: str, limit: int = 15) -> IntradayBarSeries:
        if timeframe == "1Day":
            return IntradayBarSeries(ticker, timeframe, self.daily_bars, "mock", "now")
        return IntradayBarSeries(ticker, timeframe, self.intraday_bars, "mock", "now")


def _make_bar(ts: str, o: float, h: float, low_val: float, c: float) -> IntradayBar:
    return IntradayBar("TEST", ts, o, h, low_val, c, 1000)


def test_grittani_panic_trigger():
    # 1. Daily bars (15 days). Start at 5.0, end at 15.0 (200% run-up)
    daily = [
        _make_bar("day1", 5.0, 5.0, 5.0, 5.0),
        _make_bar("day14", 15.0, 15.0, 15.0, 15.0),
        _make_bar("day15_incomplete", 15.0, 15.0, 15.0, 15.0),  # today's incomplete daily bar
    ]
    
    # 2. Intraday bars (09:30 to 09:40 NY time)
    # NY Time is UTC-4 during EDT (let's just use 13:30Z for 09:30 NY)
    intraday = [
        # Spikes to 20.0
        _make_bar("2026-06-25T13:30:00Z", 15.0, 20.0, 15.0, 19.0),
        # Crashes to 12.0 (Drop from 20.0 to 12.0 is 40%)
        _make_bar("2026-06-25T13:35:00Z", 19.0, 19.0, 12.0, 12.5),
        # First green confirmation bar (close > open)
        _make_bar("2026-06-25T13:40:00Z", 12.5, 13.5, 12.0, 13.0),
    ]
    
    provider = MockProvider(intraday, daily)
    svc = GrittaniAnalysisService(provider)
    
    signal = svc.detect_morning_panic("TEST")
    
    assert signal is not None
    assert signal.multi_day_run_pct == 200.0  # (15 - 5) / 5
    assert signal.intraday_drop_pct == 40.0   # (20 - 12) / 20
    assert signal.entry_price == 13.0
    assert signal.stop_price == 12.0


def test_grittani_panic_no_runup():
    # Start 10.0, End 11.0 (10% run)
    daily = [
        _make_bar("day1", 10.0, 10.0, 10.0, 10.0),
        _make_bar("day14", 11.0, 11.0, 11.0, 11.0),
        _make_bar("day15", 11.0, 11.0, 11.0, 11.0),
    ]
    intraday = [
        _make_bar("2026-06-25T13:30:00Z", 15.0, 20.0, 15.0, 19.0),
        _make_bar("2026-06-25T13:35:00Z", 19.0, 19.0, 12.0, 12.5),
        _make_bar("2026-06-25T13:40:00Z", 12.5, 13.5, 12.0, 13.0),
    ]
    
    provider = MockProvider(intraday, daily)
    svc = GrittaniAnalysisService(provider)
    signal = svc.detect_morning_panic("TEST")
    assert signal is None


def test_grittani_panic_small_drop():
    daily = [
        _make_bar("day1", 5.0, 5.0, 5.0, 5.0),
        _make_bar("day14", 15.0, 15.0, 15.0, 15.0),
        _make_bar("day15", 15.0, 15.0, 15.0, 15.0),
    ]
    # Drop from 20 to 16 is only 20%
    intraday = [
        _make_bar("2026-06-25T13:30:00Z", 15.0, 20.0, 15.0, 19.0),
        _make_bar("2026-06-25T13:35:00Z", 19.0, 19.0, 16.0, 16.5),
        _make_bar("2026-06-25T13:40:00Z", 16.5, 17.5, 16.0, 17.0),
    ]
    
    provider = MockProvider(intraday, daily)
    svc = GrittaniAnalysisService(provider)
    signal = svc.detect_morning_panic("TEST")
    assert signal is None
