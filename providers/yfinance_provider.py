from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from app.models import AssetProfile, ProviderPriceData, utc_now_iso


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _epoch_to_iso(value: Any) -> str | None:
    try:
        epoch = int(value)
    except (TypeError, ValueError):
        return None
    if epoch <= 0:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).replace(microsecond=0).isoformat()


def _safe_get(mapping: Any, key: str) -> Any:
    try:
        return mapping.get(key)
    except Exception:
        return None


class YFinanceProvider:
    source_name = "yfinance"

    def get_snapshot(self, ticker: str) -> ProviderPriceData:
        normalized = ticker.upper()
        try:
            import yfinance as yf
        except ImportError:
            return ProviderPriceData(
                ticker=normalized,
                source=self.source_name,
                notes=["yfinance package is not installed."],
                error="missing_dependency",
            )

        try:
            yf_ticker = yf.Ticker(normalized)
            info = self._load_info(yf_ticker)
            fast_info = getattr(yf_ticker, "fast_info", {}) or {}

            previous_close = (
                _num(info.get("previousClose"))
                or _num(info.get("regularMarketPreviousClose"))
                or _num(_safe_get(fast_info, "previous_close"))
                or _num(_safe_get(fast_info, "last_close"))
            )

            premarket_price = _num(info.get("preMarketPrice"))
            latest_price = (
                _num(info.get("regularMarketPrice"))
                or _num(_safe_get(fast_info, "last_price"))
                or _num(info.get("currentPrice"))
            )
            timestamp = (
                _epoch_to_iso(info.get("preMarketTime"))
                or _epoch_to_iso(info.get("regularMarketTime"))
                or _epoch_to_iso(info.get("postMarketTime"))
            )

            raw = {
                "previousClose": previous_close,
                "regularMarketPreviousClose": _num(info.get("regularMarketPreviousClose")),
                "preMarketPrice": premarket_price,
                "regularMarketPrice": latest_price,
                "regularMarketTime": info.get("regularMarketTime"),
                "preMarketTime": info.get("preMarketTime"),
                "marketCap": _num(info.get("marketCap")),
                "volume": _num(info.get("volume")),
                "averageVolume": (
                    _num(info.get("averageVolume"))
                    or _num(info.get("averageDailyVolume10Day"))
                    or _num(info.get("averageVolume10days"))
                ),
            }

            notes: list[str] = []
            if premarket_price is not None and timestamp is None:
                notes.append("yfinance returned premarket price without timestamp.")

            return ProviderPriceData(
                ticker=normalized,
                source=self.source_name,
                previous_close=previous_close,
                premarket_price=premarket_price,
                latest_price=latest_price,
                open_price=_num(info.get("regularMarketOpen")),
                high=_num(info.get("regularMarketDayHigh")),
                low=_num(info.get("regularMarketDayLow")),
                volume=_num(info.get("volume")) or _num(info.get("regularMarketVolume")),
                timestamp=timestamp,
                raw=raw,
                notes=notes,
            )
        except Exception as exc:
            return ProviderPriceData(
                ticker=normalized,
                source=self.source_name,
                notes=[f"Failed to fetch yfinance quote: {exc}"],
                error=str(exc),
            )

    def get_profile(self, ticker: str) -> AssetProfile | None:
        normalized = ticker.upper()
        try:
            import yfinance as yf
        except ImportError:
            return None

        try:
            info = self._load_info(yf.Ticker(normalized))
        except Exception:
            return None

        profile = AssetProfile(
            ticker=normalized,
            name=info.get("longName") or info.get("shortName"),
            exchange=info.get("exchange") or info.get("fullExchangeName"),
            sector=info.get("sector"),
            industry=info.get("industry"),
            country=info.get("country"),
            market_cap=_num(info.get("marketCap")),
            shares_outstanding=_num(info.get("sharesOutstanding")),
            float_shares=_num(info.get("floatShares")),
            source=self.source_name,
            profile_updated_at=utc_now_iso(),
        )
        if not any([profile.name, profile.market_cap, profile.exchange]):
            return None
        return profile

    @staticmethod
    def _load_info(yf_ticker: Any) -> dict[str, Any]:
        try:
            info = yf_ticker.get_info()
        except AttributeError:
            info = getattr(yf_ticker, "info", {}) or {}
        return info if isinstance(info, dict) else {}
