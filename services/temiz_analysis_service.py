from __future__ import annotations

from app.models import BarProvider, FirstRedDaySignal, IntradayBarSeries
from services.daily_bar_service import DailyBarService
from services.intraday_analysis_service import IntradayAnalysisService


REFERENCE_LEVEL_NOTE = (
    "First red day levels are rule-derived scanner references, not execution advice."
)


class TemizAnalysisService:
    def __init__(self, provider: BarProvider) -> None:
        self.provider = provider
        self.daily_service = DailyBarService()
        self.intraday_service = IntradayAnalysisService(provider)

    def fetch_daily_bars(self, ticker: str, limit: int = 100) -> IntradayBarSeries:
        return self.provider.get_bars(ticker, timeframe="1Day", limit=limit)

    def fetch_intraday_bars(self, ticker: str, limit: int = 500) -> IntradayBarSeries:
        return self.provider.get_bars(ticker, timeframe="2Min", limit=limit)

    def detect_first_red_day(self, ticker: str) -> FirstRedDaySignal | None:
        daily_series = self.fetch_daily_bars(ticker)
        green_days = self.daily_service.consecutive_green_days(daily_series)

        if green_days < 3:
            return None

        prior_levels = self.daily_service.prior_day_levels(daily_series)
        prior_close = prior_levels.get("close")
        if prior_close is None:
            return None

        intraday_series = self.fetch_intraday_bars(ticker)
        if not intraday_series.bars:
            return None

        vwap = self.intraday_service.compute_vwap(intraday_series)
        if vwap is None:
            return None

        hod_before_breakdown = None
        for bar in intraday_series.bars:
            if bar.low < prior_close:
                vwap_filter_passed = prior_close < vwap
                if not vwap_filter_passed:
                    return None

                return FirstRedDaySignal(
                    ticker=ticker,
                    consecutive_green_days=green_days,
                    breakdown_reference_price=prior_close,
                    risk_reference_price=hod_before_breakdown,
                    prior_day_close=prior_close,
                    hod_before_breakdown=hod_before_breakdown,
                    breakdown_bar_low=bar.low,
                    vwap=vwap,
                    vwap_filter_passed=vwap_filter_passed,
                    timestamp=bar.timestamp,
                    source=intraday_series.source,
                    fetched_at=intraday_series.fetched_at,
                    confidence="OK",
                    missing_fields=(
                        [] if hod_before_breakdown is not None else ["risk_reference"]
                    ),
                    notes=[REFERENCE_LEVEL_NOTE],
                )

            if hod_before_breakdown is None or bar.high > hod_before_breakdown:
                hod_before_breakdown = bar.high

        return None
