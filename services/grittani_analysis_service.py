from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.models import BarProvider, GrittaniPanicSignal, IntradayBarSeries
from services.daily_bar_service import DailyBarService
from services.intraday_analysis_service import IntradayAnalysisService


REFERENCE_LEVEL_NOTE = (
    "Morning panic levels are rule-derived scanner references, not execution advice."
)


class GrittaniAnalysisService:
    def __init__(
        self,
        provider: BarProvider,
        *,
        min_run_pct: float = 100.0,
        min_drop_pct: float = 30.0,
        min_rvol: float = 5.0,
    ) -> None:
        self.provider = provider
        self.min_run_pct = min_run_pct
        self.min_drop_pct = min_drop_pct
        self.min_rvol = min_rvol
        self.daily_service = DailyBarService()
        self.intraday_service = IntradayAnalysisService(provider)
        self.ny_tz = ZoneInfo("America/New_York")
        self.window_start = time(9, 30)
        self.window_end = time(10, 0)

    def fetch_daily_bars(self, ticker: str, limit: int = 100) -> IntradayBarSeries:
        return self.provider.get_bars(ticker, timeframe="1Day", limit=limit)

    def fetch_intraday_bars(self, ticker: str, limit: int = 500) -> IntradayBarSeries:
        return self.provider.get_bars(ticker, timeframe="2Min", limit=limit)

    def detect_morning_panic(
        self,
        ticker: str,
        *,
        rvol: float | None = None,
    ) -> GrittaniPanicSignal | None:
        if rvol is None or rvol < self.min_rvol:
            return None

        daily_series = self.fetch_daily_bars(ticker)
        if not daily_series.bars:
            return None

        run_up_pct = self.daily_service.multi_day_run_percent(daily_series, days=15)
        if run_up_pct < self.min_run_pct:
            return None

        prior_close = self.daily_service.prior_day_levels(daily_series).get("close")
        if prior_close is None:
            return None

        intraday_series = self.fetch_intraday_bars(ticker)
        if not intraday_series.bars:
            return None

        vwap = self.intraday_service.compute_vwap(intraday_series)
        return self._detect_from_intraday(
            ticker=ticker,
            intraday_series=intraday_series,
            run_up_pct=run_up_pct,
            prior_close=prior_close,
            vwap=vwap,
            rvol=rvol,
        )

    def _detect_from_intraday(
        self,
        *,
        ticker: str,
        intraday_series: IntradayBarSeries,
        run_up_pct: float,
        prior_close: float,
        vwap: float | None,
        rvol: float,
    ) -> GrittaniPanicSignal | None:
        panic_high: float | None = None
        panic_low: float | None = None
        max_drop_pct: float | None = None
        panic_seen = False

        for bar in intraday_series.bars:
            ny_dt = self._parse_bar_time(bar.timestamp)
            if ny_dt is None:
                return None
            ny_time = ny_dt.time()
            if not self.window_start <= ny_time <= self.window_end:
                continue

            panic_high = bar.high if panic_high is None else max(panic_high, bar.high)
            panic_low = bar.low if panic_low is None else min(panic_low, bar.low)
            if panic_high <= 0:
                return None

            drop_pct = ((panic_high - panic_low) / panic_high) * 100.0
            max_drop_pct = drop_pct
            if drop_pct >= self.min_drop_pct:
                panic_seen = True

            if panic_seen and bar.close > bar.open:
                missing_fields = [] if vwap is not None else ["vwap"]
                return GrittaniPanicSignal(
                    ticker=ticker,
                    multi_day_run_pct=run_up_pct,
                    intraday_drop_pct=max_drop_pct,
                    panic_high=panic_high,
                    panic_low=panic_low,
                    bounce_reference_price=bar.close,
                    risk_reference_price=panic_low,
                    prior_day_close=prior_close,
                    vwap=vwap,
                    rvol=rvol,
                    timestamp=bar.timestamp,
                    source=intraday_series.source,
                    fetched_at=intraday_series.fetched_at,
                    confidence="OK" if not missing_fields else "LOW_CONFIDENCE",
                    missing_fields=missing_fields,
                    notes=[REFERENCE_LEVEL_NOTE],
                )

        return None

    def _parse_bar_time(self, timestamp: str) -> datetime | None:
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            return None
        return dt.astimezone(self.ny_tz)
