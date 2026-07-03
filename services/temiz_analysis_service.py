from __future__ import annotations

from app.models import BarProvider, FirstRedDaySignal
from services.daily_bar_service import DailyBarService
from services.intraday_analysis_service import IntradayAnalysisService


class TemizAnalysisService:
    def __init__(self, provider: BarProvider) -> None:
        self.provider = provider
        self.daily_service = DailyBarService()
        self.intraday_service = IntradayAnalysisService(provider)

    def fetch_daily_bars(self, ticker: str, limit: int = 100):
        return self.provider.get_bars(ticker, timeframe="1Day", limit=limit)
        
    def fetch_intraday_bars(self, ticker: str, limit: int = 500):
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
        
        hod = 0.0
        for bar in intraday_series.bars:
            if bar.high > hod:
                hod = bar.high
                
            if bar.low < prior_close:
                # The exact breakdown price is slightly below prior close
                entry_price = round(prior_close - 0.01, 2)
                vwap_filter_passed = entry_price < vwap if vwap is not None else False
                
                return FirstRedDaySignal(
                    ticker=ticker,
                    consecutive_green_days=green_days,
                    entry_price=entry_price,
                    stop_price=hod,
                    vwap=vwap,
                    prior_day_close=prior_close,
                    vwap_filter_passed=vwap_filter_passed,
                    timestamp=bar.timestamp,
                    confidence="OK",
                    missing_fields=[] if vwap is not None else ["vwap"]
                )
                
        return None
