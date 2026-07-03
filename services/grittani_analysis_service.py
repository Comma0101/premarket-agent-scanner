from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

from app.models import GrittaniPanicSignal
from services.daily_bar_service import DailyBarService


class GrittaniAnalysisService:
    def __init__(self, provider: Any) -> None:
        self.provider = provider
        self.daily_service = DailyBarService()
        self.ny_tz = ZoneInfo("America/New_York")
        
    def detect_morning_panic(self, ticker: str) -> GrittaniPanicSignal | None:
        if not hasattr(self.provider, "get_bars"):
            return None
            
        # 1. Fetch Daily Bars for 15-day lookback (Multi-day run-up)
        try:
            daily_series = self.provider.get_bars(ticker, "1Day", limit=15)
        except Exception:
            return None
            
        run_up_pct = self.daily_service.multi_day_run_percent(daily_series, days=15)
        if run_up_pct < 100.0:
            return None  # Grittani requires a massive 1-3 week run
            
        # 2. Fetch Intraday Bars
        try:
            intraday_series = self.provider.get_bars(ticker, "2Min", limit=30)
        except Exception:
            return None
            
        if not intraday_series or not intraday_series.bars:
            return None
            
        last_bar = intraday_series.bars[-1]
        
        # 3. Check Time of Day (09:30 - 10:00 AM NY)
        try:
            dt = datetime.fromisoformat(last_bar.timestamp.replace("Z", "+00:00"))
            ny_time = dt.astimezone(self.ny_tz)
            if not (ny_time.hour == 9 and 30 <= ny_time.minute <= 59):
                # We also accept hour 10:00 exactly if it's a closed bar
                if not (ny_time.hour == 10 and ny_time.minute == 0):
                    return None
        except ValueError:
            pass
            
        # 4. Check Intraday Drop (>= 30%)
        day_high = 0.0
        current_low = float("inf")
        for bar in intraday_series.bars:
            if bar.high > day_high:
                day_high = bar.high
            if bar.low < current_low:
                current_low = bar.low
                
        if day_high == 0:
            return None
            
        drop_pct = ((day_high - current_low) / day_high) * 100.0
        if drop_pct < 30.0:
            return None
            
        # 5. Check Confirmation (First Green Bar)
        # A green bar means close > open
        if last_bar.close <= last_bar.open:
            return None # Still panicking
            
        return GrittaniPanicSignal(
            ticker=ticker,
            multi_day_run_pct=run_up_pct,
            intraday_drop_pct=drop_pct,
            entry_price=last_bar.close,
            stop_price=current_low,
            timestamp=last_bar.timestamp,
            confidence="OK",
        )
