from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from typing import Any, Literal, Protocol


Confidence = Literal[
    "OK",
    "LOW_CONFIDENCE",
    "CONFLICT",
    "MISSING_PREMARKET_PRICE",
    "MISSING_PREVIOUS_CLOSE",
    "MISSING_MARKET_CAP",
    "STALE_DATA",
    "ERROR",
]

Direction = Literal["up", "down", "both"]


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def model_to_dict(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        raw = asdict(value)
    elif isinstance(value, dict):
        raw = dict(value)
    else:
        raise TypeError(f"Cannot convert {type(value)!r} to dict.")

    for key, item in list(raw.items()):
        if isinstance(item, datetime):
            raw[key] = item.isoformat()
    return raw


@dataclass
class AssetProfile:
    ticker: str
    name: str | None = None
    exchange: str | None = None
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    market_cap: float | None = None
    shares_outstanding: float | None = None
    float_shares: float | None = None
    source: str | None = None
    profile_updated_at: str | None = None
    is_active: int = 1


@dataclass
class ProviderPriceData:
    ticker: str
    source: str
    previous_close: float | None = None
    premarket_price: float | None = None
    latest_price: float | None = None
    open_price: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    timestamp: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def has_any_price(self) -> bool:
        return self.premarket_price is not None or self.latest_price is not None


@dataclass
class CombinedSnapshot:
    ticker: str
    timestamp: str | None
    previous_close: float | None
    premarket_price: float | None
    latest_price: float | None
    open_price: float | None
    high: float | None
    low: float | None
    volume: float | None
    source_primary: str | None
    source_secondary: str | None
    confidence: Confidence
    sources: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    market_cap: float | None = None
    raw_yfinance_json: str | None = None
    raw_alpaca_json: str | None = None
    yfinance_data: ProviderPriceData | None = None
    alpaca_data: ProviderPriceData | None = None


@dataclass
class ScanFilters:
    min_market_cap: float | None = 0
    max_market_cap: float | None = None
    min_gap_abs: float | None = 0
    direction: Direction = "both"
    include_low_confidence: bool = True


@dataclass
class ScannerResult:
    ticker: str
    name: str | None
    universe: str | None
    market_cap: float | None
    previous_close: float | None
    premarket_price: float | None
    latest_price: float | None
    gap_pct: float | None
    volume: float | None
    confidence: Confidence
    notes: str | None
    sources: list[str] = field(default_factory=list)
    timestamp: str | None = None
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class ScanRunOutput:
    run_id: str
    universe: str | None
    started_at: str
    completed_at: str | None
    status: str
    results: list[ScannerResult]
    notes: list[str] = field(default_factory=list)


class PriceProvider(Protocol):
    source_name: str

    def get_snapshot(self, ticker: str) -> ProviderPriceData:
        ...


class ProfileProvider(Protocol):
    source_name: str

    def get_profile(self, ticker: str) -> AssetProfile | None:
        ...
