from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from app.config import get_config
from app.models import ProviderPriceData
from providers.yfinance_provider import _num

if TYPE_CHECKING:
    from app.models import IntradayBarSeries


class AlpacaProvider:
    source_name = "alpaca"
    base_url = "https://data.alpaca.markets/v2"

    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        config = get_config()
        self.api_key = api_key if api_key is not None else config.alpaca_api_key
        self.secret_key = secret_key if secret_key is not None else config.alpaca_secret_key
        self.db_path = db_path

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.secret_key)

    def get_snapshot(self, ticker: str) -> ProviderPriceData:
        normalized = ticker.upper()
        if not self.is_configured:
            return ProviderPriceData(
                ticker=normalized,
                source=self.source_name,
                notes=["Alpaca key missing; using non-Alpaca sources only."],
                error="missing_credentials",
            )

        notes: list[str] = []
        raw: dict[str, Any] = {}
        previous_close = None
        latest_trade_price = None
        latest_price = None
        open_price = None
        high = None
        low = None
        volume = None
        timestamp = None

        try:
            trade_payload = self._request(f"/stocks/{normalized}/trades/latest", {"feed": "iex"})
            raw["latest_trade"] = trade_payload
            trade = trade_payload.get("trade") if isinstance(trade_payload, dict) else None
            if isinstance(trade, dict):
                latest_trade_price = _num(trade.get("p"))
                latest_price = latest_trade_price
                timestamp = _normalize_timestamp(trade.get("t"))
                volume = _num(trade.get("s"))
        except Exception as exc:
            notes.append(f"Alpaca latest trade unavailable: {exc}")

        try:
            bar_payload = self._request(f"/stocks/{normalized}/bars/latest", {"feed": "iex"})
            raw["latest_bar"] = bar_payload
            bar = bar_payload.get("bar") if isinstance(bar_payload, dict) else None
            if isinstance(bar, dict):
                latest_price = latest_price or _num(bar.get("c"))
                open_price = _num(bar.get("o"))
                high = _num(bar.get("h"))
                low = _num(bar.get("l"))
                volume = volume or _num(bar.get("v"))
                timestamp = timestamp or _normalize_timestamp(bar.get("t"))
        except Exception as exc:
            notes.append(f"Alpaca latest bar unavailable: {exc}")

        try:
            previous_close, previous_raw = self.get_previous_close(normalized)
            raw["previous_close_bars"] = previous_raw
        except Exception as exc:
            notes.append(f"Alpaca previous close unavailable: {exc}")

        if latest_trade_price is None and latest_price is None:
            notes.append("Alpaca has no recent IEX print for this ticker.")

        return ProviderPriceData(
            ticker=normalized,
            source=self.source_name,
            previous_close=previous_close,
            premarket_price=latest_trade_price or latest_price,
            latest_price=latest_price,
            open_price=open_price,
            high=high,
            low=low,
            volume=volume,
            timestamp=timestamp,
            raw=raw,
            notes=notes,
        )

    def get_previous_close(self, ticker: str) -> tuple[float | None, dict[str, Any]]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=14)
        payload = self._request(
            f"/stocks/{ticker.upper()}/bars",
            {
                "timeframe": "1Day",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "limit": 10,
                "adjustment": "raw",
                "feed": "iex",
                "sort": "desc",
            },
        )
        bars = payload.get("bars", []) if isinstance(payload, dict) else []
        if not isinstance(bars, list):
            return None, payload if isinstance(payload, dict) else {}

        today_et = datetime.now(ZoneInfo("America/New_York")).date()
        fallback = None
        for bar in bars:
            if not isinstance(bar, dict):
                continue
            close = _num(bar.get("c"))
            if close is None:
                continue
            fallback = fallback or close
            timestamp = _parse_datetime(bar.get("t"))
            if timestamp is None:
                continue
            if timestamp.astimezone(ZoneInfo("America/New_York")).date() < today_et:
                return close, payload
        return fallback, payload

    def get_bars(
        self,
        ticker: str,
        timeframe: str = "2Min",
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> "IntradayBarSeries":
        from app.models import IntradayBar, IntradayBarSeries, utc_now_iso

        if not self.is_configured:
            return IntradayBarSeries(
                ticker=ticker.upper(),
                timeframe=timeframe,
                bars=[],
                source=self.source_name,
                fetched_at=utc_now_iso(),
            )

        now = datetime.now(timezone.utc)
        default_start, default_end = _default_bar_window(timeframe, limit, now)
        if not start:
            start = default_start.isoformat()
        if not end:
            end = default_end.isoformat()
        sort = _bar_sort(timeframe)

        payload = self._request(
            f"/stocks/{ticker.upper()}/bars",
            {
                "timeframe": timeframe,
                "start": start,
                "end": end,
                "limit": limit,
                "adjustment": "raw",
                "feed": "iex",
                "sort": sort,
            },
        )

        raw_bars = payload.get("bars") if isinstance(payload, dict) else []
        if not isinstance(raw_bars, list):
            raw_bars = []
        if sort == "desc":
            raw_bars = list(reversed(raw_bars))

        bars = []
        for bar in raw_bars:
            if not isinstance(bar, dict):
                continue
            bars.append(
                IntradayBar(
                    ticker=ticker.upper(),
                    timestamp=_normalize_timestamp(bar.get("t")),
                    open=_num(bar.get("o")) or 0.0,
                    high=_num(bar.get("h")) or 0.0,
                    low=_num(bar.get("l")) or 0.0,
                    close=_num(bar.get("c")) or 0.0,
                    volume=_num(bar.get("v")) or 0.0,
                    timeframe=timeframe,
                )
            )

        return IntradayBarSeries(
            ticker=ticker.upper(),
            timeframe=timeframe,
            bars=bars,
            source=self.source_name,
            fetched_at=utc_now_iso(),
        )

    def _request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("requests package is not installed.") from exc

        response = requests.get(
            f"{self.base_url}{endpoint}",
            params=params,
            headers={
                "APCA-API-KEY-ID": self.api_key or "",
                "APCA-API-SECRET-KEY": self.secret_key or "",
            },
            timeout=15,
        )
        if response.status_code in {401, 403}:
            raise RuntimeError("Alpaca credentials rejected.")
        if response.status_code == 429:
            raise RuntimeError("Alpaca rate limit reached.")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _normalize_timestamp(value: Any) -> str | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _default_bar_window(
    timeframe: str,
    limit: int,
    now: datetime,
) -> tuple[datetime, datetime]:
    if _is_daily_timeframe(timeframe):
        return now - timedelta(days=max(30, limit * 2)), now
    return now - timedelta(hours=4), now


def _bar_sort(timeframe: str) -> str:
    if _is_daily_timeframe(timeframe):
        return "desc"
    return "asc"


def _is_daily_timeframe(timeframe: str) -> bool:
    return timeframe.strip().lower() in {"1day", "1d", "day"}
