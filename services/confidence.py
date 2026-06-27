from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.models import CombinedSnapshot, Confidence, ProviderPriceData


def calculate_gap_pct(premarket_price: float | None, previous_close: float | None) -> float | None:
    if premarket_price is None or previous_close is None or previous_close == 0:
        return None
    return ((premarket_price - previous_close) / previous_close) * 100


def is_premarket(now: datetime | None = None, tz_name: str = "America/New_York") -> bool:
    tz = ZoneInfo(tz_name)
    current = (now or datetime.now(tz)).astimezone(tz)
    minutes = current.hour * 60 + current.minute
    return 4 * 60 <= minutes < 9 * 60 + 30


def session_note(now: datetime | None = None, tz_name: str = "America/New_York") -> str | None:
    if is_premarket(now, tz_name):
        return None
    return "Current time is outside premarket session. Using latest available extended/regular price."


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_stale(timestamp: str | None, now: datetime | None = None, threshold_minutes: int = 15) -> bool:
    parsed = _parse_ts(timestamp)
    if parsed is None:
        return False
    current = now or datetime.now(parsed.tzinfo)
    if current.tzinfo is None and parsed.tzinfo is not None:
        current = current.replace(tzinfo=parsed.tzinfo)
    return current - parsed > timedelta(minutes=threshold_minutes)


def determine_confidence(
    *,
    snapshot: CombinedSnapshot,
    market_cap: float | None,
    profile_is_stale: bool = False,
    now: datetime | None = None,
) -> Confidence:
    if any(src.error and src.error not in {"missing_credentials"} for src in [snapshot.yfinance_data, snapshot.alpaca_data] if src):
        if snapshot.previous_close is None and snapshot.premarket_price is None:
            return "ERROR"
    if snapshot.previous_close is None:
        return "MISSING_PREVIOUS_CLOSE"
    if snapshot.premarket_price is None:
        return "MISSING_PREMARKET_PRICE"
    if market_cap is None:
        return "MISSING_MARKET_CAP"
    if snapshot.timestamp and is_stale(snapshot.timestamp, now=now):
        return "STALE_DATA"
    if _has_conflicting_gap(snapshot.yfinance_data, snapshot.alpaca_data):
        return "CONFLICT"
    price_sources = [src for src in [snapshot.yfinance_data, snapshot.alpaca_data] if src and src.has_any_price and not src.error]
    if len(price_sources) < 2 or profile_is_stale or snapshot.volume is None:
        return "LOW_CONFIDENCE"
    return "OK"


def _has_conflicting_gap(yf: ProviderPriceData | None, alpaca: ProviderPriceData | None) -> bool:
    if not yf or not alpaca:
        return False
    yf_price = yf.premarket_price or yf.latest_price
    alpaca_price = alpaca.premarket_price or alpaca.latest_price
    yf_prev = yf.previous_close
    alpaca_prev = alpaca.previous_close or yf_prev
    yf_gap = calculate_gap_pct(yf_price, yf_prev)
    alpaca_gap = calculate_gap_pct(alpaca_price, alpaca_prev)
    if yf_gap is None or alpaca_gap is None:
        return False
    abs_diff = abs(yf_gap - alpaca_gap)
    rel_diff = abs_diff / max(abs(yf_gap), 0.0001)
    return abs_diff > 1.5 or rel_diff > 0.25
