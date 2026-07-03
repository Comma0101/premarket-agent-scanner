from __future__ import annotations

from app.models import IntradayBarSeries


class IntradayTechnicalsService:
    def compute_ema(self, series: IntradayBarSeries, periods: int) -> list[float | None]:
        """
        Computes the Exponential Moving Average (EMA) for a given number of periods.
        Returns a list of floats corresponding to the bars in the series. 
        The first (periods - 1) entries will be None.
        """
        if not series or not series.bars:
            return []
            
        if len(series.bars) < periods:
            return [None] * len(series.bars)
            
        ema_list: list[float | None] = [None] * len(series.bars)
        
        # Calculate initial SMA for the first 'periods' bars
        sum_close = 0.0
        for i in range(periods):
            sum_close += series.bars[i].close
            
        initial_sma = sum_close / periods
        ema_list[periods - 1] = initial_sma
        
        k = 2.0 / (periods + 1.0)
        
        # Calculate EMA for the rest
        for i in range(periods, len(series.bars)):
            price = series.bars[i].close
            prev_ema = ema_list[i - 1]
            if prev_ema is not None:
                ema_list[i] = (price - prev_ema) * k + prev_ema
                
        return ema_list

    def compute_macd(self, series: IntradayBarSeries, fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, list[float | None]]:
        """
        Computes MACD, Signal Line, and MACD Histogram.
        """
        fast_ema = self.compute_ema(series, fast)
        slow_ema = self.compute_ema(series, slow)
        
        macd_line: list[float | None] = []
        for f, s in zip(fast_ema, slow_ema):
            if f is not None and s is not None:
                macd_line.append(f - s)
            else:
                macd_line.append(None)
                
        # To compute the signal line (EMA of MACD line), we need a temporary series 
        # or a generic EMA function that takes a list of floats.
        # For now, MACD isn't strictly requested by Phase 2, so we omit full signal line logic to keep it simple,
        # but leaving the structure for future expansion if Nate Michaud needs it.
        return {"macd": macd_line}
