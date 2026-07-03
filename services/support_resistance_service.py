from __future__ import annotations

from dataclasses import dataclass

from app.models import IntradayBarSeries


@dataclass
class PivotLevel:
    price: float
    pivot_type: str  # "support" or "resistance"
    timestamp: str


class SupportResistanceService:
    def detect_daily_pivots(self, history: IntradayBarSeries, left_bars: int = 3, right_bars: int = 3) -> list[PivotLevel]:
        """
        Detects fractal pivots (support/resistance) from daily bar history.
        A resistance pivot is a high preceded by 'left_bars' lower highs and followed by 'right_bars' lower highs.
        A support pivot is a low preceded by 'left_bars' higher lows and followed by 'right_bars' higher lows.
        """
        if not history or not history.bars or len(history.bars) < left_bars + right_bars + 1:
            return []
            
        pivots: list[PivotLevel] = []
        bars = history.bars
        
        for i in range(left_bars, len(bars) - right_bars):
            # Check for Resistance (High Pivot)
            is_resistance = True
            current_high = bars[i].high
            for j in range(1, left_bars + 1):
                if bars[i - j].high >= current_high:
                    is_resistance = False
                    break
            if is_resistance:
                for j in range(1, right_bars + 1):
                    if bars[i + j].high >= current_high:
                        is_resistance = False
                        break
                        
            if is_resistance:
                pivots.append(PivotLevel(current_high, "resistance", bars[i].timestamp))
                
            # Check for Support (Low Pivot)
            is_support = True
            current_low = bars[i].low
            for j in range(1, left_bars + 1):
                if bars[i - j].low <= current_low:
                    is_support = False
                    break
            if is_support:
                for j in range(1, right_bars + 1):
                    if bars[i + j].low <= current_low:
                        is_support = False
                        break
                        
            if is_support:
                pivots.append(PivotLevel(current_low, "support", bars[i].timestamp))
                
        return pivots
