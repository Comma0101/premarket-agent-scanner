from __future__ import annotations

import pytest

from app.models import IntradayBar, IntradayBarSeries
from services.grittani_analysis_service import GrittaniAnalysisService


class FakeBarProvider:
    source_name = "fake-bars"

    def __init__(
        self,
        *,
        daily_bars: list[IntradayBar] | None = None,
        intraday_bars: list[IntradayBar] | None = None,
        raises_on: str | None = None,
    ) -> None:
        self.daily_bars = daily_bars or []
        self.intraday_bars = intraday_bars or []
        self.raises_on = raises_on

    def get_bars(
        self,
        ticker: str,
        timeframe: str = "2Min",
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> IntradayBarSeries:
        if self.raises_on == timeframe:
            raise RuntimeError(f"{timeframe} unavailable")
        bars = self.daily_bars if timeframe == "1Day" else self.intraday_bars
        return IntradayBarSeries(
            ticker=ticker,
            timeframe=timeframe,
            bars=bars,
            source=self.source_name,
            fetched_at="2026-06-29T14:10:00Z",
        )


def _bar(
    *,
    ticker: str = "TEST",
    timestamp: str,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1000,
    timeframe: str = "2Min",
) -> IntradayBar:
    return IntradayBar(
        ticker=ticker,
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        timeframe=timeframe,
    )


def _daily_runup() -> list[IntradayBar]:
    return [
        _bar(
            timestamp="2026-06-24T20:00:00Z",
            open_price=5.0,
            high=5.5,
            low=4.8,
            close=5.0,
            timeframe="1Day",
        ),
        _bar(
            timestamp="2026-06-25T20:00:00Z",
            open_price=14.5,
            high=15.5,
            low=14.0,
            close=15.0,
            timeframe="1Day",
        ),
    ]


def _valid_intraday() -> list[IntradayBar]:
    return [
        _bar(
            timestamp="2026-06-29T13:30:00Z",
            open_price=15.0,
            high=20.0,
            low=15.0,
            close=19.0,
        ),
        _bar(
            timestamp="2026-06-29T13:34:00Z",
            open_price=19.0,
            high=19.0,
            low=12.0,
            close=12.4,
        ),
        _bar(
            timestamp="2026-06-29T13:38:00Z",
            open_price=12.4,
            high=13.4,
            low=12.1,
            close=13.0,
        ),
    ]


def test_detect_morning_panic_valid_signal_carries_reference_data():
    service = GrittaniAnalysisService(
        FakeBarProvider(daily_bars=_daily_runup(), intraday_bars=_valid_intraday())
    )

    signal = service.detect_morning_panic("TEST", rvol=5.5)

    assert signal is not None
    assert signal.ticker == "TEST"
    assert signal.multi_day_run_pct == 200.0
    assert signal.intraday_drop_pct == 40.0
    assert signal.panic_high == 20.0
    assert signal.panic_low == 12.0
    assert signal.bounce_reference_price == 13.0
    assert signal.risk_reference_price == 12.0
    assert signal.prior_day_close == 15.0
    assert signal.vwap is not None
    assert signal.rvol == 5.5
    assert signal.source == "fake-bars"
    assert signal.fetched_at == "2026-06-29T14:10:00Z"
    assert signal.confidence == "OK"
    assert signal.missing_fields == []
    assert signal.notes


@pytest.mark.parametrize("rvol", [None, 4.99])
def test_detect_morning_panic_requires_service_level_rvol_gate(
    rvol: float | None,
) -> None:
    service = GrittaniAnalysisService(
        FakeBarProvider(daily_bars=_daily_runup(), intraday_bars=_valid_intraday())
    )

    assert service.detect_morning_panic("TEST", rvol=rvol) is None


def test_detect_morning_panic_rejects_invalid_timestamp() -> None:
    bars = _valid_intraday()
    bars[-1].timestamp = "not-a-timestamp"
    service = GrittaniAnalysisService(
        FakeBarProvider(daily_bars=_daily_runup(), intraday_bars=bars)
    )

    assert service.detect_morning_panic("TEST", rvol=6.0) is None


def test_detect_morning_panic_rejects_outside_morning_window() -> None:
    bars = [
        _bar(
            timestamp="2026-06-29T15:00:00Z",
            open_price=15.0,
            high=20.0,
            low=15.0,
            close=19.0,
        ),
        _bar(
            timestamp="2026-06-29T15:04:00Z",
            open_price=19.0,
            high=19.0,
            low=12.0,
            close=12.4,
        ),
        _bar(
            timestamp="2026-06-29T15:08:00Z",
            open_price=12.4,
            high=13.4,
            low=12.1,
            close=13.0,
        ),
    ]
    service = GrittaniAnalysisService(
        FakeBarProvider(daily_bars=_daily_runup(), intraday_bars=bars)
    )

    assert service.detect_morning_panic("TEST", rvol=6.0) is None


def test_detect_morning_panic_rejects_red_confirmation_bar() -> None:
    bars = _valid_intraday()
    bars[-1] = _bar(
        timestamp=bars[-1].timestamp,
        open_price=13.2,
        high=13.4,
        low=12.1,
        close=12.8,
    )
    service = GrittaniAnalysisService(
        FakeBarProvider(daily_bars=_daily_runup(), intraday_bars=bars)
    )

    assert service.detect_morning_panic("TEST", rvol=6.0) is None


def test_detect_morning_panic_rejects_empty_bar_sets() -> None:
    assert (
        GrittaniAnalysisService(FakeBarProvider(intraday_bars=_valid_intraday()))
        .detect_morning_panic("TEST", rvol=6.0)
        is None
    )
    assert (
        GrittaniAnalysisService(FakeBarProvider(daily_bars=_daily_runup()))
        .detect_morning_panic("TEST", rvol=6.0)
        is None
    )


def test_detect_morning_panic_surfaces_provider_exceptions() -> None:
    service = GrittaniAnalysisService(
        FakeBarProvider(daily_bars=_daily_runup(), raises_on="2Min")
    )

    with pytest.raises(RuntimeError, match="2Min unavailable"):
        service.detect_morning_panic("TEST", rvol=6.0)
