from __future__ import annotations

from app.models import BarProvider, BreitsteinEntrySignal, IntradayBarSeries


class IntradayAnalysisService:
    def __init__(self, bar_provider: BarProvider | None = None) -> None:
        self.bar_provider = bar_provider

    def fetch_bars(
        self,
        ticker: str,
        timeframe: str = "2Min",
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> IntradayBarSeries:
        if self.bar_provider is None:
            from providers.alpaca_provider import AlpacaProvider

            self.bar_provider = AlpacaProvider()
        return self.bar_provider.get_bars(ticker, timeframe, start or "", end or "", limit)

    def compute_vwap(self, series: IntradayBarSeries) -> float | None:
        if not series.bars:
            return None
        cumulative_tp_vol = 0.0
        cumulative_vol = 0.0
        for bar in series.bars:
            typical_price = (bar.high + bar.low + bar.close) / 3
            cumulative_tp_vol += typical_price * bar.volume
            cumulative_vol += bar.volume
        if cumulative_vol == 0:
            return None
        return cumulative_tp_vol / cumulative_vol

    def compute_prior_bar_levels(
        self, series: IntradayBarSeries
    ) -> tuple[float | None, float | None]:
        if len(series.bars) < 2:
            return None, None
        prior = series.bars[-2]
        return prior.high, prior.low

    def check_volume_2x(self, series: IntradayBarSeries) -> bool | None:
        if len(series.bars) < 2:
            return None
        last_vol = series.bars[-1].volume
        prior_vol = series.bars[-2].volume
        if prior_vol == 0:
            return None
        return last_vol >= 2 * prior_vol

    def compute_consecutive_bars(self, series: IntradayBarSeries) -> int | None:
        if not series.bars:
            return None
        count = 0
        last_close = series.bars[-1].close
        for i in range(len(series.bars) - 2, -1, -1):
            bar_close = series.bars[i].close
            if (last_close >= bar_close) == (series.bars[-1].close >= series.bars[-2].close if len(series.bars) >= 2 else True):
                count += 1
                last_close = bar_close
            else:
                break
        if len(series.bars) >= 2 and series.bars[-1].close < series.bars[-2].close:
            return -count
        return count

    def compute_rate_of_change(
        self, series: IntradayBarSeries, bars_back: int = 5
    ) -> float | None:
        if len(series.bars) <= bars_back:
            return None
        current = series.bars[-1].close
        past = series.bars[-(bars_back + 1)].close
        if past == 0:
            return None
        return (current - past) / past * 100

    def compute_bollinger_width(
        self, series: IntradayBarSeries, period: int = 20, num_std: float = 2.0
    ) -> float | None:
        if len(series.bars) < period:
            return None
        closes = [bar.close for bar in series.bars[-period:]]
        mean = sum(closes) / period
        variance = sum((c - mean) ** 2 for c in closes) / period
        std = variance ** 0.5
        upper = mean + num_std * std
        lower = mean - num_std * std
        if mean == 0:
            return None
        return (upper - lower) / mean * 100

    def compute_20_period_ma(
        self, series: IntradayBarSeries, period: int = 20
    ) -> float | None:
        if len(series.bars) < period:
            return None
        closes = [bar.close for bar in series.bars[-period:]]
        return sum(closes) / period

    def detect_entry_signal(
        self, series: IntradayBarSeries, vwap: float | None
    ) -> BreitsteinEntrySignal | None:
        if len(series.bars) < 4:
            return None

        streak_series = IntradayBarSeries(
            ticker=series.ticker,
            timeframe=series.timeframe,
            bars=series.bars[:-1],
            source=series.source,
            fetched_at=series.fetched_at
        )
        consecutive = self.compute_consecutive_bars(streak_series)
        if consecutive is None or abs(consecutive) < 3:
            return None

        vol_2x = self.check_volume_2x(series)
        if not vol_2x:
            return None

        prior_high, prior_low = self.compute_prior_bar_levels(series)
        last_bar = series.bars[-1]
        missing: list[str] = []

        if vwap is None:
            missing.append("vwap")

        if consecutive < 0:
            direction = "long"
            if last_bar.close <= (prior_high or float("inf")):
                return None
            entry_price = last_bar.close
            stop_price = prior_low
            target_price = self.compute_20_period_ma(series)
            vwap_filter = vwap is None or last_bar.close > vwap
        else:
            direction = "short"
            if last_bar.close >= (prior_low or 0):
                return None
            entry_price = last_bar.close
            stop_price = prior_high
            target_price = self.compute_20_period_ma(series)
            vwap_filter = vwap is None or last_bar.close < vwap

        return BreitsteinEntrySignal(
            ticker=series.ticker,
            direction=direction,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            prior_bar_high=prior_high,
            prior_bar_low=prior_low,
            vwap=vwap,
            vwap_filter_passed=vwap_filter,
            volume_2x_confirmed=True,
            consecutive_bars=consecutive,
            rate_of_change=self.compute_rate_of_change(series),
            bollinger_width=self.compute_bollinger_width(series),
            timestamp=last_bar.timestamp,
            confidence="OK" if not missing else "LOW_CONFIDENCE",
            missing_fields=missing,
        )

    def detect_chop(
        self, series: IntradayBarSeries, width_threshold: float = 1.0
    ) -> bool | None:
        width = self.compute_bollinger_width(series)
        if width is None:
            return None
        return width < width_threshold
