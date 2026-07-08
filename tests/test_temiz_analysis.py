from app.models import IntradayBar, IntradayBarSeries
from services.temiz_analysis_service import TemizAnalysisService


class MockBarProvider:
    def __init__(self, daily_bars=None, intraday_bars=None):
        self.daily_bars = daily_bars or []
        self.intraday_bars = intraday_bars or []
        self.source_name = "mock"

    def get_bars(
        self,
        ticker: str,
        timeframe: str,
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> IntradayBarSeries:
        if timeframe == "1Day":
            return IntradayBarSeries(
                ticker,
                timeframe,
                self.daily_bars,
                self.source_name,
                "2026-06-29T14:00:00Z",
            )
        return IntradayBarSeries(
            ticker,
            timeframe,
            self.intraday_bars,
            self.source_name,
            "2026-06-29T14:00:00Z",
        )


def _make_bar(
    ticker: str,
    c: float,
    h: float = 10.0,
    low_val: float = 9.0,
    o: float = 9.5,
    tf: str = "1Day",
    ts: str = "2026-06-25T14:00:00Z",
) -> IntradayBar:
    return IntradayBar(
        ticker=ticker,
        timestamp=ts,
        open=o,
        high=h,
        low=low_val,
        close=c,
        volume=100,
        timeframe=tf,
    )


def test_detect_first_red_day_valid():
    daily = [
        _make_bar("AAPL", 10.0, ts="2026-06-21T04:00:00Z"),
        _make_bar("AAPL", 11.0, ts="2026-06-22T04:00:00Z"),
        _make_bar("AAPL", 12.0, ts="2026-06-23T04:00:00Z"),
        _make_bar("AAPL", 13.0, ts="2026-06-24T04:00:00Z"),  # prior close = 13.0
    ]
    intraday = [
        _make_bar(
            "AAPL",
            13.5,
            h=14.0,
            low_val=13.1,
            tf="2Min",
            ts="2026-06-25T13:30:00Z",
        ),
        _make_bar(
            "AAPL",
            12.9,
            h=13.5,
            low_val=12.5,
            tf="2Min",
            ts="2026-06-25T13:32:00Z",
        ),
    ]
    svc = TemizAnalysisService(MockBarProvider(daily, intraday))
    signal = svc.detect_first_red_day("AAPL")

    assert signal is not None
    assert signal.ticker == "AAPL"
    assert signal.consecutive_green_days == 3
    assert signal.prior_day_close == 13.0
    assert signal.breakdown_reference_price == 13.0
    assert signal.risk_reference_price == 14.0
    assert signal.breakdown_bar_low == 12.5
    assert signal.vwap_filter_passed is True
    assert signal.source == "mock"
    assert signal.confidence == "OK"
    assert signal.notes


def test_reject_not_enough_green_days():
    daily = [
        _make_bar("AAPL", 10.0, ts="2026-06-21T04:00:00Z"),
        _make_bar("AAPL", 11.0, ts="2026-06-22T04:00:00Z"),
        _make_bar("AAPL", 9.0, ts="2026-06-23T04:00:00Z"),  # breaks streak
        _make_bar("AAPL", 13.0, ts="2026-06-24T04:00:00Z"),
    ]
    intraday = [
        _make_bar(
            "AAPL",
            12.9,
            h=13.5,
            low_val=12.5,
            tf="2Min",
            ts="2026-06-25T13:32:00Z",
        ),
    ]
    svc = TemizAnalysisService(MockBarProvider(daily, intraday))
    assert svc.detect_first_red_day("AAPL") is None


def test_reject_no_breakdown():
    daily = [
        _make_bar("AAPL", 11.0, ts="2026-06-22T04:00:00Z"),
        _make_bar("AAPL", 12.0, ts="2026-06-23T04:00:00Z"),
        _make_bar("AAPL", 13.0, ts="2026-06-24T04:00:00Z"),
    ]
    intraday = [
        _make_bar(
            "AAPL",
            13.5,
            h=14.0,
            low_val=13.1,
            tf="2Min",
            ts="2026-06-25T13:30:00Z",
        ),
    ]
    svc = TemizAnalysisService(MockBarProvider(daily, intraday))
    assert svc.detect_first_red_day("AAPL") is None


def test_reject_breakdown_above_vwap():
    daily = [
        _make_bar("AAPL", 10.0, ts="2026-06-21T04:00:00Z"),
        _make_bar("AAPL", 11.0, ts="2026-06-22T04:00:00Z"),
        _make_bar("AAPL", 12.0, ts="2026-06-23T04:00:00Z"),
        _make_bar("AAPL", 13.0, ts="2026-06-24T04:00:00Z"),
    ]
    intraday = [
        _make_bar(
            "AAPL",
            12.0,
            h=12.5,
            low_val=11.9,
            tf="2Min",
            ts="2026-06-25T13:30:00Z",
        ),
    ]
    svc = TemizAnalysisService(MockBarProvider(daily, intraday))
    assert svc.detect_first_red_day("AAPL") is None
