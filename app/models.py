from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
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
SmallCapGrade = Literal["A_WATCH", "B_WATCH", "C_WATCH", "REJECT"]
BreitsteinGrade = Literal["A_WATCH", "B_WATCH", "C_WATCH", "REJECT"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    average_volume: float | None = None
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
    min_volume: float | None = None
    min_rel_volume: float | None = None
    include_low_confidence: bool = True


@dataclass
class SmallCapScannerPreset:
    name: str
    cap_tiers: list[str]
    direction: Direction = "up"
    min_gap_abs: float = 5.0
    min_volume: float | None = None
    min_rel_volume: float | None = 2.0
    include_low_confidence: bool = False
    missing_fields: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# Market-cap tiers (USD). Upper bound is exclusive; None means no upper bound.
CAP_TIERS: dict[str, tuple[float, float | None]] = {
    "nano": (0, 50e6),
    "micro": (50e6, 300e6),
    "small": (300e6, 2e9),
    "mid": (2e9, 10e9),
    "large": (10e9, 200e9),
    "mega": (200e9, None),
}


def resolve_cap_tier(name: str) -> tuple[float, float | None]:
    key = name.strip().lower()
    if key not in CAP_TIERS:
        valid = ", ".join(CAP_TIERS)
        raise ValueError(f"Unknown cap tier: {name}. Valid tiers: {valid}.")
    return CAP_TIERS[key]


def make_scan_filters(
    *,
    cap_tier: str | None = None,
    min_market_cap: float | None = 0,
    max_market_cap: float | None = None,
    min_gap_abs: float | None = 0,
    direction: Direction = "both",
    min_volume: float | None = None,
    min_rel_volume: float | None = None,
    include_low_confidence: bool = True,
) -> ScanFilters:
    """Build ScanFilters, expanding a cap tier into market-cap bounds.

    Explicit min_market_cap / max_market_cap take precedence over the tier.
    """
    if cap_tier:
        tier_min, tier_max = resolve_cap_tier(cap_tier)
        if not min_market_cap:
            min_market_cap = tier_min
        if max_market_cap is None:
            max_market_cap = tier_max
    return ScanFilters(
        min_market_cap=min_market_cap or 0,
        max_market_cap=max_market_cap,
        min_gap_abs=min_gap_abs or 0,
        direction=direction,
        min_volume=min_volume,
        min_rel_volume=min_rel_volume,
        include_low_confidence=include_low_confidence,
    )


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
    rel_volume: float | None = None
    gap_dollar: float | None = None
    # What the gap's effective price actually is: "premarket" (genuine premarket
    # quote), "last_trade" (most recent regular/last trade — off-session this is a
    # stale prior-session price, so the gap is NOT premarket), or None.
    gap_basis: str | None = None
    sources: list[str] = field(default_factory=list)
    timestamp: str | None = None
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class FilingEvent:
    ticker: str
    form_type: str
    filed_at: str
    accession_number: str
    description: str | None = None
    source_url: str | None = None
    risk_tags: list[str] = field(default_factory=list)


@dataclass
class CatalystEvent:
    ticker: str
    headline: str
    published_at: str | None
    source: str
    url: str | None = None
    summary: str | None = None
    confidence: str = "UNKNOWN"
    catalyst_quality: str | None = None
    recency_minutes: float | None = None


@dataclass
class FormerRunnerEvent:
    ticker: str
    event_date: str
    max_gap_pct: float | None = None
    max_volume: float | None = None
    source_run_id: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class SmallCapEvidence:
    ticker: str
    float_shares: float | None = None
    shares_outstanding: float | None = None
    float_source: str | None = None
    exchange: str | None = None
    is_low_float: bool | None = None
    float_rotation: float | None = None
    filings: list[FilingEvent] = field(default_factory=list)
    catalysts: list[CatalystEvent] = field(default_factory=list)
    former_runner: FormerRunnerEvent | None = None
    missing_fields: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass
class BreitsteinCandidate:
    ticker: str
    name: str | None
    market_cap: float | None
    gap_pct: float | None
    gap_dollar: float | None
    volume: float | None
    rel_volume: float | None
    confidence: Confidence
    gap_basis: str | None
    cap_tier: str | None
    abnormal_move: bool | None
    consecutive_days_direction: int | None
    has_catalyst: bool | None
    score: int = 0
    grade: BreitsteinGrade = "REJECT"
    matched_signals: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    evidence: SmallCapEvidence | None = None
    timestamp: str | None = None


@dataclass
class BreitsteinScanOutput:
    preset: str
    run_ids: list[str]
    candidate_count: int
    candidates: list[BreitsteinCandidate]
    phase: str = "1"
    notes: list[str] = field(default_factory=list)


@dataclass
class SmallCapCandidate:
    ticker: str
    name: str | None
    market_cap: float | None
    gap_pct: float | None
    gap_dollar: float | None
    volume: float | None
    rel_volume: float | None
    confidence: Confidence
    score: int
    grade: SmallCapGrade
    gap_basis: str | None = None
    matched_signals: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    evidence: SmallCapEvidence | None = None
    timestamp: str | None = None


@dataclass
class SmallCapScanOutput:
    preset: str
    run_ids: list[str]
    candidate_count: int
    candidates: list[SmallCapCandidate]
    notes: list[str] = field(default_factory=list)
    rejected_count: int = 0
    rejected: list[SmallCapCandidate] = field(default_factory=list)
    zero_result_reason: str | None = None
    relax_suggestions: list[str] = field(default_factory=list)


@dataclass
class ScanRunOutput:
    run_id: str
    universe: str | None
    started_at: str
    completed_at: str | None
    status: str
    results: list[ScannerResult]
    notes: list[str] = field(default_factory=list)


@dataclass
class IntradayBar:
    ticker: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    timeframe: str = "2Min"


@dataclass
class IntradayBarSeries:
    ticker: str
    timeframe: str
    bars: list[IntradayBar]
    source: str
    fetched_at: str


@dataclass
class BreitsteinEntrySignal:
    ticker: str
    direction: str
    entry_price: float | None
    stop_price: float | None
    target_price: float | None
    prior_bar_high: float | None
    prior_bar_low: float | None
    vwap: float | None
    vwap_filter_passed: bool | None
    volume_2x_confirmed: bool | None
    consecutive_bars: int | None
    rate_of_change: float | None
    bollinger_width: float | None
    timestamp: str
    confidence: str
    missing_fields: list[str] = field(default_factory=list)


@dataclass
class FirstRedDaySignal:
    ticker: str
    consecutive_green_days: int
    breakdown_reference_price: float | None
    risk_reference_price: float | None
    prior_day_close: float | None
    hod_before_breakdown: float | None
    breakdown_bar_low: float | None
    vwap: float | None
    vwap_filter_passed: bool | None
    timestamp: str
    source: str | None
    fetched_at: str | None
    confidence: str
    missing_fields: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class GrittaniPanicSignal:
    ticker: str
    multi_day_run_pct: float | None
    intraday_drop_pct: float | None
    panic_high: float | None
    panic_low: float | None
    bounce_reference_price: float | None
    risk_reference_price: float | None
    prior_day_close: float | None
    vwap: float | None
    rvol: float | None
    timestamp: str
    source: str | None
    fetched_at: str | None
    confidence: str
    missing_fields: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class PriceProvider(Protocol):
    source_name: str

    def get_snapshot(self, ticker: str) -> ProviderPriceData:
        ...


class ProfileProvider(Protocol):
    source_name: str

    def get_profile(self, ticker: str) -> AssetProfile | None:
        ...


class BarProvider(Protocol):
    source_name: str

    def get_bars(
        self,
        ticker: str,
        timeframe: str = "2Min",
        start: str | None = None,
        end: str | None = None,
        limit: int = 100,
    ) -> IntradayBarSeries:
        ...
