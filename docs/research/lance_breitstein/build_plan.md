# Lance Breitstein Agent Build Plan

This document provides detailed, step-by-step instructions for building the
Lance Breitstein mean-reversion scanner agent. Read AGENTS.md first. Follow the
prime directive: never invent a number.

The build is split into two phases. Phase 1 uses existing data (no new
providers). Phase 2 adds intraday bar data and the full scanner.

---

## Phase 1: Breitstein Underlying Watchlist (Existing Data)

Build a `BreitsteinScannerService` that composes the existing `ScannerService`
to surface mean-reversion candidates from premarket/equity snapshot data. This
requires NO new providers, NO new data, NO new API keys.

### 1.1 Scanner Preset

Create `data/scanner_presets.yaml` entry:

```yaml
breitstein_mean_reversion_v0:
  cap_tiers: [small, mid, large, mega]
  direction: both
  min_gap_abs: 3.0
  min_volume: 500000
  min_rel_volume: 3.0
  include_low_confidence: false
  missing_fields: [intraday_bars, vwap, order_flow, footprint, news_classification]
  notes:
    - "Phase 1 underlying watchlist only."
    - "No intraday entry triggers until Phase 2 bar data and VWAP are available."
    - "Do not infer emotional capitulation from price/volume without catalyst context."
```

### 1.2 New Model: BreitsteinCandidate

Add to `app/models.py`:

```python
@dataclass
class BreitsteinCandidate:
    ticker: str
    name: str | None
    market_cap: float | None
    gap_pct: float | None
    gap_dollar: float | None
    volume: float | None
    rel_volume: float | None
    confidence: str
    gap_basis: str | None
    cap_tier: str | None
    abnormal_move: bool | None
    consecutive_days_direction: int | None
    has_catalyst: bool | None
    score: int = 0
    grade: str = "REJECT"
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
```

Also add: `BreitsteinGrade = Literal["A_WATCH", "B_WATCH", "C_WATCH", "REJECT"]`

### 1.3 New Service: BreitsteinScannerService

Create `services/breitstein_scanner_service.py`.

The service follows the same composition pattern as `SmallCapScannerService`:
compose `ScannerService` + `PresetService` + evidence, add Breitstein-specific
grading.

```python
class BreitsteinScannerService:
    def __init__(
        self,
        scanner_service: ScannerService | None = None,
        preset_service: PresetService | None = None,
        evidence_service: SmallCapEvidenceEnricher | None = None,
        market_universe_provider: object | None = None,
    ) -> None:
        ...
```

**Key method: `scan()`**
1. Load preset `breitstein_mean_reversion_v0`
2. Build `ScanFilters` from preset (direction=both, min_gap=3, min_rvol=3)
3. Call `self.scanner_service.scan()` with the filters
4. For each `ScannerResult`, compute Breitstein-specific signals:
   - `abnormal_move`: gap_pct >= 2x normal daily range (approximate: gap_pct >= 5 for stable stocks, >= 3 for volatile)
   - `consecutive_days_direction`: from daily data if available, else None
   - `has_catalyst`: from evidence enrichment (filings, news)
   - `cap_tier`: mid/large/mega preferred
5. Grade each candidate

**Key method: `grade_breitstein_candidate()`**

Scoring rubric (max 100):

| Signal | Points | Condition |
| --- | --- | --- |
| Abnormal move | +25 | gap_pct >= 5% (or >= 3% for large/mega cap) |
| High RVOL | +20 | rel_volume >= 3 |
| Direction both | +10 | gap-down included (mean reversion works both ways) |
| Cap tier fit | +15 | mid, large, or mega cap |
| Clean confidence | +10 | confidence == "OK" |
| Has catalyst | +10 | fresh news or filing catalyst present |
| Gap-down flush | +10 | direction is "down" (flush-out / capitulation is primary setup) |

Grade thresholds:
- >= 75 → A_WATCH
- >= 55 → B_WATCH
- >= 35 → C_WATCH
- else → REJECT

Apply risk gates (these cap grades):
- If confidence in UNUSABLE_CONFIDENCE → REJECT
- If `gap_basis != premarket` or `confidence != OK` → max B_WATCH
- If cap tier is not mid/large/mega → max B_WATCH
- If no catalyst and no abnormal move → max B_WATCH (can't confirm emotional dislocation)
- If gap < 3% and RVOL < 2 → REJECT (no participation, no dislocation)

### 1.4 New Agent Tool

Add to `agent_tools/definitions.py` TOOLS list:

```python
{
    "type": "function",
    "function": {
        "name": "scan_breitstein",
        "description": "Scan for Lance Breitstein-style mean-reversion-after-capitulation candidates. Phase 1: identifies underlyings with abnormal moves, high RVOL, and catalysts. Phase 2 (future): adds intraday entry triggers.",
        "parameters": {
            "type": "object",
            "properties": {
                "preset_name": {"type": "string", "default": "breitstein_mean_reversion_v0"},
                "universe": {"type": ["string", "array"], "description": "Universe name(s)"},
                "watchlist": {"type": ["string", "array"], "description": "Watchlist name(s)"},
                "tickers": {"type": "array", "items": {"type": "string"}, "description": "Explicit ticker list"},
                "all_universes": {"type": "boolean", "default": false},
                "market": {"type": "string", "description": "Market universe (e.g. 'active')"},
                "market_limit": {"type": "integer", "description": "Optional smoke-test cap for market scans"},
                "max_workers": {"type": "integer", "description": "Optional bounded worker count"},
            },
        },
    },
},
```

Add to `_DISPATCH`:
```python
"scan_breitstein": tools.scan_breitstein,
```

Add to `agent_tools/tools.py`:

```python
def scan_breitstein(
    *,
    preset_name: str = "breitstein_mean_reversion_v0",
    universe: str | list[str] | None = None,
    watchlist: str | list[str] | None = None,
    tickers: list[str] | str | None = None,
    all_universes: bool = False,
    market: str | None = None,
    market_limit: int | None = None,
    max_workers: int | None = None,
    service: BreitsteinScannerService | None = None,
) -> dict[str, Any]:
    ...
```

Follow the same pattern as `scan_small_caps()`: lazy-import the service,
run scan, serialize results using a `_breitstein_candidate_to_dict()` helper.
If no selection is provided, default to `watchlist="HOT_ACTIVE"` instead of
`all_universes=true`; this keeps the Phase 1 scan focused on in-play underlyings.

### 1.5 Tests

Create `tests/test_breitstein_scanner.py`.

Follow the existing test patterns from `tests/test_small_cap_scanner.py`:

1. `FakeBreitsteinService` for tool-level tests
2. `FakeScannerService` returning canned `ScanRunOutput` for service-level tests
3. `FakeEvidenceService` for enrichment tests
4. Grade tests: verify A/B/C/REJECT thresholds
5. Risk gate tests: UNUSABLE confidence → REJECT, no catalyst + no abnormal → max B
6. Both-directions test: verify gap-down candidates are included (unlike Sykes)
7. Cap tier test: verify mid/large/mega preferred, nano/micro downgraded

All tests must run offline with fake providers. Never hit the network.

### 1.6 Universe Addition

Add a mid/large-cap universe to `data/universes.yaml`:

```yaml
MID_LARGE_CAP:
  - AAPL
  - MSFT
  - GOOGL
  - AMZN
  - NVDA
  - META
  - TSLA
  - AVGO
  - AMD
  - NFLX
  # ... add other liquid mid/large-cap names
```

Keep `data/universes.yaml` as a mapping of universe name to a plain ticker list.
The current `UniverseService` does not support nested metadata fields.

---

## Phase 2: Intraday Bar Data + Full Scanner

Phase 2 requires a new data provider for intraday bars. The Alpaca provider
already exists and already fetches 1Day bars. Extend it to fetch 2-minute bars.

### 2.1 New Model: IntradayBar

Add to `app/models.py`:

```python
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
    direction: str  # "long" or "short"
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
```

Add Protocol to `app/models.py`:

```python
class BarProvider(Protocol):
    source_name: str
    def get_bars(
        self, ticker: str, timeframe: str, start: str, end: str
    ) -> IntradayBarSeries: ...
```

### 2.2 Extend AlpacaProvider

Add method to `providers/alpaca_provider.py`:

```python
def get_bars(
    self,
    ticker: str,
    timeframe: str = "2Min",
    start: str | None = None,
    end: str | None = None,
    limit: int = 100,
) -> IntradayBarSeries:
    """Fetch intraday bars from Alpaca.

    Default: last 100 2-minute bars (covers ~3.5 hours of trading).
    """
    if not self.is_configured:
        return IntradayBarSeries(
            ticker=ticker.upper(),
            timeframe=timeframe,
            bars=[],
            source=self.source_name,
            fetched_at=utc_now_iso(),
        )

    now = datetime.now(timezone.utc)
    if start is None:
        start_dt = now - timedelta(hours=4)
        start = start_dt.isoformat()
    if end is None:
        end = now.isoformat()

    payload = self._request(
        f"/stocks/{ticker.upper()}/bars",
        {
            "timeframe": timeframe,
            "start": start,
            "end": end,
            "limit": limit,
            "adjustment": "raw",
            "feed": "iex",
            "sort": "asc",
        },
    )

    raw_bars = payload.get("bars", []) if isinstance(payload, dict) else []
    bars = []
    for bar in raw_bars:
        if not isinstance(bar, dict):
            continue
        bars.append(IntradayBar(
            ticker=ticker.upper(),
            timestamp=_normalize_timestamp(bar.get("t")),
            open=_num(bar.get("o")) or 0.0,
            high=_num(bar.get("h")) or 0.0,
            low=_num(bar.get("l")) or 0.0,
            close=_num(bar.get("c")) or 0.0,
            volume=_num(bar.get("v")) or 0.0,
            timeframe=timeframe,
        ))

    return IntradayBarSeries(
        ticker=ticker.upper(),
        timeframe=timeframe,
        bars=bars,
        source=self.source_name,
        fetched_at=utc_now_iso(),
    )
```

### 2.3 New Service: IntradayAnalysisService

Create `services/intraday_analysis_service.py`.

This service takes a `BarProvider` and computes Breitstein-specific metrics:

```python
class IntradayAnalysisService:
    def __init__(self, bar_provider: BarProvider | None = None) -> None:
        self.bar_provider = bar_provider  # default to AlpacaProvider in factory method

    def compute_vwap(self, series: IntradayBarSeries) -> float | None:
        """VWAP = cumulative(typical_price * volume) / cumulative(volume)
        typical_price = (high + low + close) / 3
        """
        ...

    def compute_prior_bar_levels(
        self, series: IntradayBarSeries
    ) -> tuple[float | None, float | None]:
        """Return (prior_bar_high, prior_bar_low) from the most recent completed bar."""
        ...

    def check_volume_2x(
        self, series: IntradayBarSeries
    ) -> bool | None:
        """Check if the last bar's volume >= 2x the prior bar's volume."""
        ...

    def compute_consecutive_bars(
        self, series: IntradayBarSeries
    ) -> int | None:
        """Count consecutive bars moving in the same direction.
        Positive = consecutive up bars, Negative = consecutive down bars.
        """
        ...

    def compute_rate_of_change(
        self, series: IntradayBarSeries, bars_back: int = 5
    ) -> float | None:
        """Rate of change: (current_close - close_N_bars_ago) / close_N_bars_ago * 100"""
        ...

    def compute_bollinger_width(
        self, series: IntradayBarSeries, period: int = 20, num_std: float = 2.0
    ) -> float | None:
        """Bollinger Band width = (upper - lower) / middle * 100.
        Used for chop/compression detection.
        """
        ...

    def compute_20_period_ma(
        self, series: IntradayBarSeries, period: int = 20
    ) -> float | None:
        """Simple moving average of close prices. Used as equilibrium target."""
        ...

    def detect_entry_signal(
        self, series: IntradayBarSeries, vwap: float | None
    ) -> BreitsteinEntrySignal | None:
        """Core entry detection logic.

        For LONGS (after downtrend / capitulation):
        1. Consecutive down bars (at least 3)
        2. Last bar breaks above prior bar high
        3. Volume on last bar >= 2x prior bar volume
        4. VWAP filter: stock is below VWAP (capitulating) OR above VWAP (reclaiming)

        For SHORTS (after uptrend / euphoria):
        1. Consecutive up bars (at least 3)
        2. Last bar breaks below prior bar low
        3. Volume on last bar >= 2x prior bar volume
        4. VWAP filter: stock is above VWAP (euphoric) OR below VWAP (breaking)

        Returns None if no signal detected.
        """
        ...

    def detect_chop(
        self, series: IntradayBarSeries
    ) -> bool | None:
        """Detect chop / Bollinger Band compression.
        Width < threshold means consolidation / no-trade zone.
        """
        ...
```

### 2.4 Extend BreitsteinScannerService for Phase 2

Add an `intraday_analysis_service` parameter to the constructor. When present,
the `scan()` method performs a second pass on Phase 1 candidates:

1. For each A/B Watch candidate from Phase 1, fetch 2-min bars
2. Compute VWAP, prior bar levels, 2x volume, consecutive bars, rate of change
3. Run `detect_entry_signal()`
4. If signal found, add entry/stop/target to candidate
5. If chop detected, downgrade candidate

Add a `scan_intraday()` method that takes a list of tickers (from Phase 1
output) and returns `BreitsteinEntrySignal` objects.

### 2.5 New Agent Tool for Phase 2

Add to `agent_tools/definitions.py`:

```python
{
    "type": "function",
    "function": {
        "name": "scan_breitstein_intraday",
        "description": "Run Phase 2 intraday analysis on Breitstein candidates. Requires Alpaca API keys for 2-minute bar data. Returns entry signals with stops and targets.",
        "parameters": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tickers to analyze (typically from Phase 1 scan_breitstein output)",
                },
            },
            "required": ["tickers"],
        },
    },
},
```

### 2.6 Tests for Phase 2

Create `tests/test_intraday_analysis.py`:

1. `FakeBarProvider` returning canned `IntradayBarSeries` — never hit network
2. VWAP computation test with known values
3. Prior bar levels test
4. 2x volume rule test (pass and fail cases)
5. Consecutive bars test (3 up, 3 down, mixed)
6. Rate of change test
7. Bollinger width test
8. Entry signal detection test: verify long signal after 3+ down bars + prior bar high break + 2x volume
9. Entry signal detection test: verify short signal after 3+ up bars + prior bar low break + 2x volume
10. Chop detection test: verify Bollinger compression returns True
11. VWAP filter test: verify "never long below VWAP unless capitulating"
12. No signal test: verify None returned when conditions not met
13. Integration test: Phase 1 candidates → Phase 2 intraday analysis → signals

---

## Build Order

Execute in this order. Each step should compile and pass tests before moving on.

1. `tests/test_breitstein_scanner.py` — write failing model/preset tests first
2. `app/models.py` — add `BreitsteinCandidate`, `BreitsteinScanOutput`, `BreitsteinGrade`
3. `data/scanner_presets.yaml` — add `breitstein_mean_reversion_v0` preset
4. `tests/test_breitstein_scanner.py` — write failing service/tool tests
5. `services/breitstein_scanner_service.py` — implement service with grading
6. `agent_tools/definitions.py` — add `scan_breitstein` tool
7. `agent_tools/tools.py` — add `scan_breitstein()` function + serializers
8. `tests/test_universe_service.py` — write failing `MID_LARGE_CAP` assertion
9. `data/universes.yaml` — add `MID_LARGE_CAP` universe as a plain list
10. Run full test suite: `.venv/bin/python -m pytest -q`
11. Run lint: `.venv/bin/ruff check .`
12. Run verify: `scripts/verify.sh`

Phase 2 (separate PR after Phase 1 is merged):

11. `app/models.py` — add `IntradayBar`, `IntradayBarSeries`, `BreitsteinEntrySignal`, `BarProvider` Protocol
12. `providers/alpaca_provider.py` — add `get_bars()` method
13. `services/intraday_analysis_service.py` — implement all computation methods
14. `tests/test_intraday_analysis.py` — write tests FIRST (TDD)
15. Extend `BreitsteinScannerService` with intraday pass
16. `agent_tools/definitions.py` — add `scan_breitstein_intraday` tool
17. `agent_tools/tools.py` — add `scan_breitstein_intraday()` function
18. Full test suite + lint + verify

## Rules

- Never hit the network in tests. Use fake providers with constructor injection.
- Never invent a number. Every price, gap, RVOL, volume, score must come from
  the data layer.
- Do not output buy/sell calls, position sizes, or targets as advice.
- Treat all performance claims as self-reported. The Breitstein profile has
  flaggable verification gaps — the Desk output should note these.
- Add to TOOLS and _DISPATCH once in definitions.py. MCP server reflects automatically.
- One logical change per commit.
- Work on a branch: `feature/breitstein-scanner`.
