from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import IntradayBar, IntradayBarSeries


class DailyBarService:
    def __init__(self, now_provider: Callable[[], datetime] | None = None) -> None:
        self.ny_tz = ZoneInfo("America/New_York")
        self._now_provider = now_provider

    def _now_ny(self) -> datetime:
        now = self._now_provider() if self._now_provider else datetime.now(self.ny_tz)
        if now.tzinfo is None:
            return now.replace(tzinfo=self.ny_tz)
        return now.astimezone(self.ny_tz)

    def _get_completed_bars(self, series: IntradayBarSeries) -> list[IntradayBar]:
        """Returns the list of bars excluding today's incomplete bar."""
        if not series or not series.bars:
            return []
        
        bars = series.bars.copy()
        
        try:
            last_timestamp = bars[-1].timestamp.replace("Z", "+00:00")
            dt = datetime.fromisoformat(last_timestamp)
            ny_date = dt.astimezone(self.ny_tz).date()
            today_date = self._now_ny().date()

            if ny_date == today_date:
                bars.pop()
        except ValueError:
            pass
            
        return bars

    def consecutive_green_days(self, series: IntradayBarSeries) -> int:
        """Counts consecutive days where close > previous day's close."""
        bars = self._get_completed_bars(series)
        if len(bars) < 2:
            return 0
            
        count = 0
        for i in range(len(bars) - 1, 0, -1):
            curr_bar = bars[i]
            prev_bar = bars[i - 1]
            if curr_bar.close > prev_bar.close:
                count += 1
            else:
                break
        return count

    def multi_day_run_percent(self, series: IntradayBarSeries, days: int = 3) -> float:
        """Calculates percentage return from N days ago to the most recent completed close."""
        bars = self._get_completed_bars(series)
        if len(bars) < 2:
            return 0.0
            
        current_close = bars[-1].close
        start_index = max(0, len(bars) - 1 - days)
        start_close = bars[start_index].close
        
        if start_close == 0:
            return 0.0
            
        return ((current_close - start_close) / start_close) * 100.0

    def prior_day_levels(self, series: IntradayBarSeries) -> dict[str, float | None]:
        """Returns the open, high, low, and close of the most recent completed day."""
        bars = self._get_completed_bars(series)
        if not bars:
            return {"close": None, "low": None, "high": None, "open": None}
            
        prior_bar = bars[-1]
        return {
            "close": prior_bar.close,
            "low": prior_bar.low,
            "high": prior_bar.high,
            "open": prior_bar.open,
        }
