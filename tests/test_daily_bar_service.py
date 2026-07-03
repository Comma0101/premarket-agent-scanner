from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import IntradayBar, IntradayBarSeries
from services.daily_bar_service import DailyBarService


def _make_bar(ticker, timestamp, o, h, low_val, c, v, timeframe="1Day"):
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


def _make_series(ticker, ohlcv_list, dates, timeframe="1Day", source="test"):
    bars = [
        _make_bar(ticker, date, o, h, low_val, c, v, timeframe)
        for date, (o, h, low_val, c, v) in zip(dates, ohlcv_list)
    ]
    return IntradayBarSeries(
        ticker=ticker,
        timeframe=timeframe,
        bars=bars,
        source=source,
        fetched_at="2026-06-29T14:00:00Z",
    )


def test_consecutive_green_days():
    svc = DailyBarService()
    
    # 3 green days leading up to today
    # Note: today's date is 2026-06-29 (as per standard system time), so let's mock it
    # We will just pass dates that are in the past to avoid the _get_completed_bars popping them,
    # or we can pass today's date and let it pop.
    
    dates = [
        "2026-06-24T04:00:00Z",
        "2026-06-25T04:00:00Z",
        "2026-06-26T04:00:00Z",
        "2026-06-27T04:00:00Z",  # Completed yesterday
    ]
    ohlcv = [
        (10.0, 11.0, 9.0, 10.5, 100),
        (10.5, 12.0, 10.0, 11.5, 100), # Green (11.5 > 10.5)
        (11.5, 13.0, 11.0, 12.5, 100), # Green (12.5 > 11.5)
        (12.5, 14.0, 12.0, 13.5, 100), # Green (13.5 > 12.5)
    ]
    
    series = _make_series("AAPL", ohlcv, dates)
    assert svc.consecutive_green_days(series) == 3


def test_consecutive_green_days_interrupted():
    svc = DailyBarService()
    dates = [
        "2026-06-24T04:00:00Z",
        "2026-06-25T04:00:00Z",
        "2026-06-26T04:00:00Z",
        "2026-06-27T04:00:00Z",
    ]
    ohlcv = [
        (10.0, 11.0, 9.0, 10.5, 100),
        (10.5, 12.0, 10.0, 11.5, 100), # Green
        (11.5, 13.0, 11.0, 11.0, 100), # Red (11.0 < 11.5)
        (11.0, 14.0, 11.0, 12.0, 100), # Green
    ]
    
    series = _make_series("AAPL", ohlcv, dates)
    # Only 1 green day before the end
    assert svc.consecutive_green_days(series) == 1


def test_multi_day_run_percent():
    svc = DailyBarService()
    dates = [
        "2026-06-24T04:00:00Z",
        "2026-06-25T04:00:00Z",
        "2026-06-26T04:00:00Z",
        "2026-06-27T04:00:00Z",
    ]
    ohlcv = [
        (10.0, 11.0, 9.0, 10.0, 100),
        (10.5, 12.0, 10.0, 11.0, 100), 
        (11.5, 13.0, 11.0, 12.5, 100), 
        (12.5, 14.0, 12.0, 15.0, 100), 
    ]
    
    series = _make_series("AAPL", ohlcv, dates)
    # run percent over 3 days (from index 0 to 3)
    # start close = 10.0, end close = 15.0 => 50%
    assert svc.multi_day_run_percent(series, days=3) == 50.0
    
    # over 1 day
    # start close = 12.5, end close = 15.0 => 20%
    assert svc.multi_day_run_percent(series, days=1) == 20.0


def test_prior_day_levels():
    svc = DailyBarService()
    dates = [
        "2026-06-24T04:00:00Z",
        "2026-06-25T04:00:00Z",
    ]
    ohlcv = [
        (10.0, 11.0, 9.0, 10.5, 100),
        (10.5, 12.0, 10.0, 11.5, 100),
    ]
    
    series = _make_series("AAPL", ohlcv, dates)
    levels = svc.prior_day_levels(series)
    assert levels["close"] == 11.5
    assert levels["high"] == 12.0
    assert levels["low"] == 10.0
    assert levels["open"] == 10.5


def test_excludes_today_bar():
    # If a bar has today's date, it should be excluded from historical calculations
    fixed_now = datetime(2026, 7, 1, 9, 45, tzinfo=ZoneInfo("America/New_York"))
    svc = DailyBarService(now_provider=lambda: fixed_now)
    today_iso = fixed_now.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z")
    
    dates = [
        "2026-06-25T04:00:00Z",
        "2026-06-26T04:00:00Z",
        today_iso, # incomplete today bar
    ]
    ohlcv = [
        (10.0, 11.0, 9.0, 10.5, 100),
        (10.5, 12.0, 10.0, 11.5, 100), # completed yesterday
        (11.5, 13.0, 11.0, 12.0, 100), # today (should be ignored)
    ]
    
    series = _make_series("AAPL", ohlcv, dates)
    
    # prior day levels should return yesterday's levels (11.5 close) not today's
    levels = svc.prior_day_levels(series)
    assert levels["close"] == 11.5
    
    # consecutive green days should be 1 (yesterday was green, today is ignored)
    assert svc.consecutive_green_days(series) == 1
