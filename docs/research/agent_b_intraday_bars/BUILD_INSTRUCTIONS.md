# Agent B — Intraday Bars Build Instructions

Build the intraday bar data layer that powers Breitstein Phase 2 entry signals.
Branch: `feature/intraday-bars`. Rebase onto `main` before opening a PR.

---

## Pre-flight

1. Verify you're on a clean branch off `main`:
   ```bash
   git checkout main && git pull
   git checkout -b feature/intraday-bars
   ```
2. Verify the venv works:
   ```bash
   .venv/bin/python -m pytest -q
   .venv/bin/ruff check .
   ```
   All tests must pass before you start.

---

## Step 1: Add IntradayBar models to `app/models.py`

Add these dataclasses **after** the existing `ScanRunOutput` class (around line 292)
and **before** the `PriceProvider` Protocol (line 294):

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
```

Add the `BarProvider` Protocol **after** the existing `ProfileProvider` Protocol
(around line 305):

```python
class BarProvider(Protocol):
    source_name: str

    def get_bars(
        self, ticker: str, timeframe: str, start: str, end: str, limit: int = 100
    ) -> IntradayBarSeries: ...
```

**Why this placement:** All data models live in `app/models.py`. Protocols are at
the bottom. The `IntradayBar` / `IntradayBarSeries` / `BreitsteinEntrySignal`
dataclasses go with the other dataclasses. The `BarProvider` Protocol goes with
the other Protocols. Agent A will add `BreitsteinCandidate` and
`BreitsteinScanOutput` in the same area — coordinate via separate branches so
there's no conflict. Agent A adds "Breitstein" models; you add "Intraday/Bar"
models. They don't overlap.

**Verify:** `.venv/bin/python -c "from app.models import IntradayBar, IntradayBarSeries, BreitsteinEntrySignal, BarProvider; print('OK')"`

---

## Step 2: Add `get_bars()` to `providers/alpaca_provider.py`

Add this method to the `AlpacaProvider` class, after `get_previous_close()` and
before `_request()`:

```python
def get_bars(
    self,
    ticker: str,
    timeframe: str = "2Min",
    start: str | None = None,
    end: str | None = None,
    limit: int = 100,
) -> IntradayBarSeries:
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

**Key points:**
- Follows the exact same pattern as `get_previous_close()`: uses `_request()`,
  parses response, uses `_num()` and `_normalize_timestamp()` helpers already in
  the file.
- Returns `IntradayBarSeries` (empty bars list) when unconfigured, matching how
  `get_snapshot()` returns `ProviderPriceData` with `error="missing_credentials"`.
- Default timeframe is `"2Min"`, default limit is 100 bars (covers ~3.5 hours of
  trading), default start is 4 hours ago — all from the build plan.
- Uses `"feed": "iex"` and `"adjustment": "raw"` matching `get_previous_close()`.
- The Alpaca API endpoint `/stocks/{ticker}/bars` is the same one used by
  `get_previous_close()` — just with a different `timeframe` parameter.

**Verify:** `.venv/bin/python -c "from providers.alpaca_provider import AlpacaProvider; print(hasattr(AlpacaProvider, 'get_bars'))"`

---

## Step 3: Write tests for `get_bars()` — TDD

Create `tests/test_alpaca_bars.py`.

### 3.1 FakeBarProvider

Follow the `FakePriceProvider` pattern from `tests/test_scanner.py`:

```python
class FakeBarProvider:
    source_name = "fake"

    def __init__(self, series_map: dict[str, IntradayBarSeries]) -> None:
        self._map = series_map

    def get_bars(
        self, ticker: str, timeframe: str, start: str, end: str, limit: int = 100
    ) -> IntradayBarSeries:
        key = ticker.upper()
        if key in self._map:
            return self._map[key]
        return IntradayBarSeries(
            ticker=key,
            timeframe=timeframe,
            bars=[],
            source=self.source_name,
            fetched_at=utc_now_iso(),
        )
```

### 3.2 Test: AlpacaProvider.get_bars() with unconfigured keys

```python
def test_get_bars_returns_empty_when_unconfigured():
    provider = AlpacaProvider(api_key=None, secret_key=None)
    series = provider.get_bars("AAPL")
    assert series.ticker == "AAPL"
    assert series.bars == []
    assert series.source == "alpaca"
```

This test does NOT hit the network — it tests the early-return path when
`is_configured` is False. This is the same pattern as the existing
`test_sec_provider.py`.

### 3.3 Test: AlpacaProvider.get_bars() parses Alpaca response

Inject a fake `_request` method so the test never hits the network:

```python
def test_get_bars_parses_alpaca_response(monkeypatch):
    provider = AlpacaProvider(api_key="key", secret_key="secret")

    fake_payload = {
        "bars": [
            {
                "t": "2026-06-29T14:00:00Z",
                "o": 100.0,
                "h": 101.0,
                "l": 99.5,
                "c": 100.5,
                "v": 5000,
            },
            {
                "t": "2026-06-29T14:02:00Z",
                "o": 100.5,
                "h": 102.0,
                "l": 100.0,
                "c": 101.5,
                "v": 8000,
            },
        ]
    }

    monkeypatch.setattr(provider, "_request", lambda endpoint, params: fake_payload)

    series = provider.get_bars("AAPL", timeframe="2Min")
    assert series.ticker == "AAPL"
    assert series.timeframe == "2Min"
    assert len(series.bars) == 2
    assert series.bars[0].open == 100.0
    assert series.bars[0].high == 101.0
    assert series.bars[0].low == 99.5
    assert series.bars[0].close == 100.5
    assert series.bars[0].volume == 5000
    assert series.bars[1].close == 101.5
    assert series.bars[1].volume == 8000
```

### 3.4 Test: get_bars handles empty bars gracefully

```python
def test_get_bars_handles_empty_payload(monkeypatch):
    provider = AlpacaProvider(api_key="key", secret_key="secret")
    monkeypatch.setattr(provider, "_request", lambda endpoint, params: {"bars": []})
    series = provider.get_bars("AAPL")
    assert series.bars == []
```

### 3.5 Test: get_bars handles malformed bars

```python
def test_get_bars_skips_malformed_bars(monkeypatch):
    provider = AlpacaProvider(api_key="key", secret_key="secret")
    monkeypatch.setattr(
        provider,
        "_request",
        lambda endpoint, params: {
            "bars": [
                "not_a_dict",
                {"t": "2026-06-29T14:00:00Z", "o": 100, "h": 101, "l": 99, "c": 100, "v": 5000},
            ]
        },
    )
    series = provider.get_bars("AAPL")
    assert len(series.bars) == 1
```

**Run:** `.venv/bin/python -m pytest tests/test_alpaca_bars.py -q`

---

## Step 4: Create `services/intraday_analysis_service.py`

This is the core computation service. It takes a `BarProvider` and computes
Breitstein-specific metrics from bar data.

```python
from __future__ import annotations

from app.models import BarProvider, BreitsteinEntrySignal, IntradayBarSeries, utc_now_iso


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
        count = 1
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

        consecutive = self.compute_consecutive_bars(series)
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
```

**Key design decisions:**

1. `fetch_bars()` lazy-inits `AlpacaProvider` if no provider is injected — same
   pattern as `SmallCapScannerService` with `ScannerService`.

2. `compute_consecutive_bars()` returns negative for down-streaks, positive for
   up-streaks. This is critical for the entry signal: `consecutive < 0` means
   the stock has been falling (long setup), `consecutive > 0` means rising
   (short setup).

3. `detect_entry_signal()` implements the Breitstein rules:
   - **Long** (after capitulation/downtrend): 3+ consecutive down bars, last bar
     breaks above prior bar high, 2x volume on the last bar. VWAP filter: if
     below VWAP the stock is capitulating (OK), if above VWAP it's reclaiming
     (also OK) — so the filter always passes unless VWAP is unknown.
   - **Short** (after euphoria/uptrend): 3+ consecutive up bars, last bar breaks
     below prior bar low, 2x volume on the last bar. VWAP filter mirrors long.
   - Returns `None` if no signal detected.

4. `detect_chop()` uses Bollinger Band width. Width < threshold means
   consolidation / no-trade zone. The threshold is parameterized (default 1.0%)
   — it's not a Breitstein-specified number, it's a reasonable default that can
   be tuned.

**Verify:** `.venv/bin/python -c "from services.intraday_analysis_service import IntradayAnalysisService; print('OK')"`

---

## Step 5: Write comprehensive tests for IntradayAnalysisService — TDD

Create `tests/test_intraday_analysis.py`. This is the most important file in
Agent B's work. Every computation method must be tested with known inputs and
expected outputs.

### 5.1 Helper: build bar series from a list of OHLCV tuples

```python
def _make_bar(ticker, timestamp, o, h, l, c, v, timeframe="2Min"):
    return IntradayBar(
        ticker=ticker,
        timestamp=timestamp,
        open=o,
        high=h,
        low=l,
        close=c,
        volume=v,
        timeframe=timeframe,
    )


def _make_series(ticker, ohlcv_list, timeframe="2Min", source="test"):
    bars = [
        _make_bar(ticker, f"2026-06-29T14:{i:02d}:00Z", o, h, l, c, v, timeframe)
        for i, (o, h, l, c, v) in enumerate(ohlcv_list)
    ]
    return IntradayBarSeries(
        ticker=ticker,
        timeframe=timeframe,
        bars=bars,
        source=source,
        fetched_at=utc_now_iso(),
    )
```

### 5.2 VWAP computation tests

```python
def test_compute_vwap_known_values():
    # 2 bars: bar1 TP=100, vol=1000; bar2 TP=110, vol=2000
    # VWAP = (100*1000 + 110*2000) / (1000+2000) = 320000/3000 = 106.67
    series = _make_series("TEST", [
        (99, 102, 98, 100, 100, 1000),
        (109, 112, 108, 110, 110, 2000),
    ])
    svc = IntradayAnalysisService()
    vwap = svc.compute_vwap(series)
    assert vwap is not None
    assert abs(vwap - 106.667) < 0.01


def test_compute_vwap_empty_series():
    series = IntradayBarSeries(ticker="X", timeframe="2Min", bars=[], source="test", fetched_at=utc_now_iso())
    svc = IntradayAnalysisService()
    assert svc.compute_vwap(series) is None


def test_compute_vwap_zero_volume():
    series = _make_series("TEST", [
        (100, 101, 99, 100, 100, 0),
        (100, 101, 99, 100, 100, 0),
    ])
    svc = IntradayAnalysisService()
    assert svc.compute_vwap(series) is None
```

### 5.3 Prior bar levels tests

```python
def test_compute_prior_bar_levels():
    series = _make_series("TEST", [
        (100, 105, 95, 100, 100, 1000),
        (101, 108, 96, 102, 2000),  # prior bar: high=108, low=96
        (103, 110, 97, 104, 3000),  # last bar
    ])
    svc = IntradayAnalysisService()
    high, low = svc.compute_prior_bar_levels(series)
    assert high == 108
    assert low == 96


def test_compute_prior_bar_levels_insufficient_bars():
    series = _make_series("TEST", [(100, 101, 99, 100, 100, 1000)])
    svc = IntradayAnalysisService()
    high, low = svc.compute_prior_bar_levels(series)
    assert high is None
    assert low is None
```

### 5.4 2x volume rule tests

```python
def test_check_volume_2x_true():
    series = _make_series("TEST", [
        (100, 101, 99, 100, 100, 1000),
        (101, 102, 100, 101, 2500),  # last bar vol 2500 >= 2*1000
    ])
    svc = IntradayAnalysisService()
    assert svc.check_volume_2x(series) is True


def test_check_volume_2x_false():
    series = _make_series("TEST", [
        (100, 101, 99, 100, 100, 1000),
        (101, 102, 100, 101, 1500),  # 1500 < 2*1000
    ])
    svc = IntradayAnalysisService()
    assert svc.check_volume_2x(series) is False


def test_check_volume_2x_insufficient_bars():
    series = _make_series("TEST", [(100, 101, 99, 100, 100, 1000)])
    svc = IntradayAnalysisService()
    assert svc.check_volume_2x(series) is None
```

### 5.5 Consecutive bars tests

```python
def test_consecutive_down_bars():
    # 5 bars, each closing lower than the one before
    series = _make_series("TEST", [
        (105, 106, 104, 105, 1000),
        (104, 105, 103, 104, 1000),
        (103, 104, 102, 103, 1000),
        (102, 103, 101, 102, 1000),
        (101, 102, 100, 101, 2000),  # 4 consecutive down
    ])
    svc = IntradayAnalysisService()
    result = svc.compute_consecutive_bars(series)
    assert result == -4  # negative = down streak


def test_consecutive_up_bars():
    series = _make_series("TEST", [
        (100, 101, 99, 100, 1000),
        (100, 102, 100, 101, 1000),
        (101, 103, 101, 102, 1000),
        (102, 104, 102, 103, 1000),
        (103, 105, 103, 104, 2000),  # 4 consecutive up
    ])
    svc = IntradayAnalysisService()
    result = svc.compute_consecutive_bars(series)
    assert result == 4  # positive = up streak


def test_consecutive_bars_mixed():
    series = _make_series("TEST", [
        (100, 101, 99, 100, 1000),
        (100, 102, 100, 101, 1000),
        (101, 102, 100, 100, 1000),  # down
        (100, 101, 99, 99, 2000),    # down again = 2 consecutive down
    ])
    svc = IntradayAnalysisService()
    result = svc.compute_consecutive_bars(series)
    assert result == -2
```

### 5.6 Rate of change tests

```python
def test_compute_rate_of_change():
    # 6 bars; last close=110, 5-bars-ago close=100 → +10%
    series = _make_series("TEST", [
        (100, 101, 99, 100, 1000),  # 5 bars ago
        (101, 102, 100, 101, 1000),
        (102, 103, 101, 102, 1000),
        (103, 104, 102, 103, 1000),
        (104, 105, 103, 104, 1000),
        (110, 111, 109, 110, 2000),  # last bar
    ])
    svc = IntradayAnalysisService()
    roc = svc.compute_rate_of_change(series, bars_back=5)
    assert roc is not None
    assert abs(roc - 10.0) < 0.01


def test_compute_rate_of_change_insufficient_bars():
    series = _make_series("TEST", [
        (100, 101, 99, 100, 1000),
        (101, 102, 100, 101, 1000),
    ])
    svc = IntradayAnalysisService()
    assert svc.compute_rate_of_change(series, bars_back=5) is None
```

### 5.7 Bollinger width tests

```python
def test_compute_bollinger_width():
    # 20 bars with known std; just verify it returns a positive number
    bars = [(100 + i * 0.1, 100.5 + i * 0.1, 99.5 + i * 0.1, 100 + i * 0.1, 1000) for i in range(20)]
    series = _make_series("TEST", bars)
    svc = IntradayAnalysisService()
    width = svc.compute_bollinger_width(series)
    assert width is not None
    assert width > 0


def test_compute_bollinger_width_insufficient_bars():
    bars = [(100, 101, 99, 100, 1000) for _ in range(10)]
    series = _make_series("TEST", bars)
    svc = IntradayAnalysisService()
    assert svc.compute_bollinger_width(series, period=20) is None
```

### 5.8 20-period MA tests

```python
def test_compute_20_period_ma():
    bars = [(100 + i, 101 + i, 99 + i, 100 + i, 1000) for i in range(25)]
    series = _make_series("TEST", bars)
    svc = IntradayAnalysisService()
    ma = svc.compute_20_period_ma(series)
    expected = sum(100 + i for i in range(5, 25)) / 20  # last 20 closes
    assert ma is not None
    assert abs(ma - expected) < 0.01


def test_compute_20_period_ma_insufficient_bars():
    bars = [(100, 101, 99, 100, 1000) for _ in range(15)]
    series = _make_series("TEST", bars)
    svc = IntradayAnalysisService()
    assert svc.compute_20_period_ma(series) is None
```

### 5.9 Entry signal detection tests (THE MOST IMPORTANT TESTS)

```python
def test_detect_long_entry_signal():
    # 3+ consecutive down bars, then a bar that breaks above prior bar high with 2x volume
    series = _make_series("TEST", [
        (110, 111, 109, 110, 1000),  # up
        (109, 110, 108, 109, 1000),  # down
        (108, 109, 107, 108, 1000),  # down
        (107, 108, 106, 107, 1000),  # down (3 consecutive down)
        (108, 110, 107, 109, 2000),  # breaks above prior high (108), vol 2x
    ])
    svc = IntradayAnalysisService()
    signal = svc.detect_entry_signal(series, vwap=108.0)
    assert signal is not None
    assert signal.direction == "long"
    assert signal.entry_price == 109
    assert signal.stop_price == 106  # prior bar low
    assert signal.prior_bar_high == 108
    assert signal.prior_bar_low == 106
    assert signal.volume_2x_confirmed is True
    assert signal.consecutive_bars == -3  # was 3 down before the breakout bar


def test_detect_short_entry_signal():
    # 3+ consecutive up bars, then a bar that breaks below prior bar low with 2x volume
    series = _make_series("TEST", [
        (100, 101, 99, 100, 1000),
        (100, 102, 100, 101, 1000),  # up
        (101, 103, 101, 102, 1000),  # up
        (102, 104, 102, 103, 1000),  # up (3 consecutive up)
        (102, 103, 100, 101, 2000),  # breaks below prior low (102), vol 2x
    ])
    svc = IntradayAnalysisService()
    signal = svc.detect_entry_signal(series, vwap=102.0)
    assert signal is not None
    assert signal.direction == "short"
    assert signal.entry_price == 101
    assert signal.stop_price == 104  # prior bar high
    assert signal.volume_2x_confirmed is True


def test_no_signal_insufficient_consecutive_bars():
    # Only 2 consecutive down bars
    series = _make_series("TEST", [
        (110, 111, 109, 110, 1000),
        (109, 110, 108, 109, 1000),  # down
        (108, 109, 107, 108, 1000),  # down (only 2)
        (109, 110, 107, 109, 2000),
    ])
    svc = IntradayAnalysisService()
    signal = svc.detect_entry_signal(series, vwap=108.0)
    assert signal is None


def test_no_signal_no_volume_2x():
    # 3 consecutive down bars but no 2x volume on last bar
    series = _make_series("TEST", [
        (110, 111, 109, 110, 1000),
        (109, 110, 108, 109, 1000),  # down
        (108, 109, 107, 108, 1000),  # down
        (107, 108, 106, 107, 1000),  # down (3 consecutive)
        (108, 110, 107, 109, 1200),  # vol only 1.2x, not 2x
    ])
    svc = IntradayAnalysisService()
    signal = svc.detect_entry_signal(series, vwap=108.0)
    assert signal is None


def test_no_signal_no_prior_bar_break():
    # 3 consecutive down + 2x volume, but close does NOT break prior bar high
    series = _make_series("TEST", [
        (110, 111, 109, 110, 1000),
        (109, 110, 108, 109, 1000),  # down
        (108, 109, 107, 108, 1000),  # down
        (107, 108, 106, 107, 1000),  # down (prior high = 108)
        (107, 107.5, 106, 107, 2000),  # close 107 <= prior high 108 — no break
    ])
    svc = IntradayAnalysisService()
    signal = svc.detect_entry_signal(series, vwap=108.0)
    assert signal is None


def test_signal_with_missing_vwap():
    series = _make_series("TEST", [
        (110, 111, 109, 110, 1000),
        (109, 110, 108, 109, 1000),
        (108, 109, 107, 108, 1000),
        (107, 108, 106, 107, 1000),
        (108, 110, 107, 109, 2000),
    ])
    svc = IntradayAnalysisService()
    signal = svc.detect_entry_signal(series, vwap=None)
    assert signal is not None
    assert "vwap" in signal.missing_fields
    assert signal.confidence == "LOW_CONFIDENCE"
```

### 5.10 Chop detection tests

```python
def test_detect_chop_compression():
    # 20 bars with tiny range — should be chop
    bars = [(100, 100.1, 99.9, 100, 1000) for _ in range(20)]
    series = _make_series("TEST", bars)
    svc = IntradayAnalysisService()
    assert svc.detect_chop(series) is True


def test_detect_chop_expanding():
    # 20 bars with expanding range — should not be chop
    bars = [(100 + i * 2, 100 + i * 2 + 1, 100 + i * 2 - 1, 100 + i * 2, 1000) for i in range(20)]
    series = _make_series("TEST", bars)
    svc = IntradayAnalysisService()
    assert svc.detect_chop(series) is False


def test_detect_chop_insufficient_bars():
    series = _make_series("TEST", [(100, 101, 99, 100, 1000) for _ in range(10)])
    svc = IntradayAnalysisService()
    assert svc.detect_chop(series) is None
```

### 5.11 Integration: fetch_bars + analysis

```python
def test_fetch_bars_and_analyze():
    fake_series = _make_series("AAPL", [
        (110, 111, 109, 110, 1000),
        (109, 110, 108, 109, 1000),
        (108, 109, 107, 108, 1000),
        (107, 108, 106, 107, 1000),
        (108, 110, 107, 109, 2000),
    ])
    provider = FakeBarProvider({"AAPL": fake_series})
    svc = IntradayAnalysisService(bar_provider=provider)
    series = svc.fetch_bars("AAPL")
    assert len(series.bars) == 5
    signal = svc.detect_entry_signal(series, vwap=108.0)
    assert signal is not None
    assert signal.direction == "long"
```

**Run all:** `.venv/bin/python -m pytest tests/test_intraday_analysis.py -q`

---

## Step 6: Add `scan_breitstein_intraday` tool to `agent_tools/definitions.py`

Add this entry to the `TOOLS` list (after the existing 4 tools):

```python
{
    "name": "scan_breitstein_intraday",
    "description": (
        "Run Phase 2 intraday analysis on Breitstein candidates. Requires "
        "Alpaca API keys for 2-minute bar data. Fetches bars, computes VWAP, "
        "prior bar levels, 2x volume confirmation, and detects entry signals "
        "with stops and targets. Call this after scan_breitstein identifies "
        "Phase 1 candidates. Every number comes from the bar data layer — "
        "never invent prices, stops, or targets."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tickers to analyze (typically from Phase 1 scan_breitstein output).",
            },
        },
        "required": ["tickers"],
    },
},
```

Add to `_DISPATCH`:

```python
"scan_breitstein_intraday": tools.scan_breitstein_intraday,
```

**IMPORTANT:** Add it ONCE. The MCP server reflects TOOLS automatically — never
hand-duplicate a schema in `mcp_server/`.

---

## Step 7: Add `scan_breitstein_intraday()` to `agent_tools/tools.py`

Add the serializer and tool function. Follow the exact pattern of `scan_small_caps()`:

```python
def _intraday_bar_to_dict(bar: IntradayBar) -> dict[str, Any]:
    return {
        "ticker": bar.ticker,
        "timestamp": bar.timestamp,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "timeframe": bar.timeframe,
    }


def _breitstein_entry_signal_to_dict(signal: BreitsteinEntrySignal) -> dict[str, Any]:
    return {
        "ticker": signal.ticker,
        "direction": signal.direction,
        "entry_price": signal.entry_price,
        "stop_price": signal.stop_price,
        "target_price": signal.target_price,
        "prior_bar_high": signal.prior_bar_high,
        "prior_bar_low": signal.prior_bar_low,
        "vwap": signal.vwap,
        "vwap_filter_passed": signal.vwap_filter_passed,
        "volume_2x_confirmed": signal.volume_2x_confirmed,
        "consecutive_bars": signal.consecutive_bars,
        "rate_of_change": signal.rate_of_change,
        "bollinger_width": signal.bollinger_width,
        "timestamp": signal.timestamp,
        "confidence": signal.confidence,
        "missing_fields": list(signal.missing_fields),
    }


def scan_breitstein_intraday(
    *,
    tickers: list[str],
    service: Any | None = None,
) -> dict[str, Any]:
    if not tickers:
        return {"error": "tickers is required and must be non-empty."}

    if service is None:
        from services.intraday_analysis_service import IntradayAnalysisService

        service = IntradayAnalysisService()

    signals = []
    for ticker in tickers:
        try:
            series = service.fetch_bars(ticker)
            vwap = service.compute_vwap(series)
            signal = service.detect_entry_signal(series, vwap)
            if signal is not None:
                signals.append(signal)
        except Exception as exc:
            signals.append(BreitsteinEntrySignal(
                ticker=ticker,
                direction="unknown",
                entry_price=None,
                stop_price=None,
                target_price=None,
                prior_bar_high=None,
                prior_bar_low=None,
                vwap=None,
                vwap_filter_passed=None,
                volume_2x_confirmed=None,
                consecutive_bars=None,
                rate_of_change=None,
                bollinger_width=None,
                timestamp=utc_now_iso(),
                confidence="ERROR",
                missing_fields=["bar_data"],
            ))

    return {
        "ticker_count": len(tickers),
        "signal_count": len(signals),
        "signals": [_breitstein_entry_signal_to_dict(s) for s in signals],
    }
```

Add the necessary imports at the top of `tools.py`:

```python
from app.models import (
    BreitsteinEntrySignal,
    IntradayBar,
    ...
)
```

**Verify:** `.venv/bin/python -c "from agent_tools.tools import scan_breitstein_intraday; print('OK')"`

---

## Step 8: Add tool-level tests to `tests/test_agent_tools.py`

Append these tests:

```python
def test_scan_breitstein_intraday_tool_with_injected_service():
    from app.models import BreitsteinEntrySignal

    class FakeIntradayService:
        def fetch_bars(self, ticker, timeframe="2Min", start="", end="", limit=100):
            return IntradayBarSeries(
                ticker=ticker, timeframe="2Min", bars=[], source="fake", fetched_at=utc_now_iso()
            )

        def compute_vwap(self, series):
            return None

        def detect_entry_signal(self, series, vwap):
            return None

    out = tools.scan_breitstein_intraday(
        tickers=["AAPL"], service=FakeIntradayService()
    )
    assert out["ticker_count"] == 1
    assert out["signal_count"] == 0
    assert out["signals"] == []


def test_scan_breitstein_intraday_tool_returns_signal():
    from app.models import BreitsteinEntrySignal

    class FakeIntradayServiceWithSignal:
        def fetch_bars(self, ticker, timeframe="2Min", start="", end="", limit=100):
            return _make_series(ticker, [
                (110, 111, 109, 110, 1000),
                (109, 110, 108, 109, 1000),
                (108, 109, 107, 108, 1000),
                (107, 108, 106, 107, 1000),
                (108, 110, 107, 109, 2000),
            ])

        def compute_vwap(self, series):
            return 108.0

        def detect_entry_signal(self, series, vwap):
            return BreitsteinEntrySignal(
                ticker="AAPL",
                direction="long",
                entry_price=109,
                stop_price=106,
                target_price=None,
                prior_bar_high=108,
                prior_bar_low=106,
                vwap=108.0,
                vwap_filter_passed=True,
                volume_2x_confirmed=True,
                consecutive_bars=-3,
                rate_of_change=-1.0,
                bollinger_width=2.5,
                timestamp="2026-06-29T14:08:00Z",
                confidence="OK",
            )

    out = tools.scan_breitstein_intraday(
        tickers=["AAPL"], service=FakeIntradayServiceWithSignal()
    )
    assert out["signal_count"] == 1
    assert out["signals"][0]["ticker"] == "AAPL"
    assert out["signals"][0]["direction"] == "long"
    assert out["signals"][0]["entry_price"] == 109
    assert out["signals"][0]["stop_price"] == 106


def test_scan_breitstein_intraday_tool_requires_tickers():
    out = tools.scan_breitstein_intraday(tickers=[])
    assert "error" in out
```

Also update `test_tool_definitions_are_well_formed` to include the new tool:

```python
names = {t["name"] for t in definitions.TOOLS}
assert names == {
    "scan_premarket",
    "scan_small_caps",
    "list_universes",
    "get_ticker_snapshot",
    "scan_breitstein_intraday",
}
```

**Run:** `.venv/bin/python -m pytest tests/test_agent_tools.py -q`

---

## Step 9: Update `test_tool_definitions_are_well_formed`

This test in `test_agent_tools.py` validates the tool names set. You need to add
`"scan_breitstein_intraday"` to the expected set. See Step 8 above.

**NOTE:** If Agent A has already merged `scan_breitstein` by the time you rebase,
the expected set will also include `"scan_breitstein"`. Coordinate.

---

## Step 10: Final verification

Run the complete verification pipeline:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
scripts/verify.sh
```

All must pass before committing.

---

## File ownership (avoid merge conflicts)

| File | Owner | Notes |
|------|-------|-------|
| `app/models.py` | **Agent B** (IntradayBar, IntradayBarSeries, BreitsteinEntrySignal, BarProvider) | Agent A adds BreitsteinCandidate, BreitsteinScanOutput in a different section. Coordinate: B's models go near ScanRunOutput, A's go near SmallCapCandidate. |
| `providers/alpaca_provider.py` | **Agent B** | get_bars() is a new method; Agent A doesn't touch this file. |
| `services/intraday_analysis_service.py` | **Agent B** | New file, no conflict. |
| `tests/test_intraday_analysis.py` | **Agent B** | New file, no conflict. |
| `tests/test_alpaca_bars.py` | **Agent B** | New file, no conflict. |
| `agent_tools/definitions.py` | **Shared** | Agent A adds `scan_breitstein`, Agent B adds `scan_breitstein_intraday`. Append to different positions. |
| `agent_tools/tools.py` | **Shared** | Agent A adds `scan_breitstein()`, Agent B adds `scan_breitstein_intraday()` + serializers. Append at end. |
| `tests/test_agent_tools.py` | **Shared** | Both agents add tests and update `test_tool_definitions_are_well_formed`. Coordinate. |

**Merge order:** Agent A merges first → Agent B rebases onto A's branch → resolve any conflicts in shared files → merge B.

---

## Commit structure

One logical change per commit:

1. `app/models.py`: "Add IntradayBar, IntradayBarSeries, BreitsteinEntrySignal, BarProvider models"
2. `providers/alpaca_provider.py` + `tests/test_alpaca_bars.py`: "Add AlpacaProvider.get_bars() with tests"
3. `services/intraday_analysis_service.py` + `tests/test_intraday_analysis.py`: "Add IntradayAnalysisService with VWAP, entry signals, chop detection"
4. `agent_tools/definitions.py` + `agent_tools/tools.py` + `tests/test_agent_tools.py`: "Add scan_breitstein_intraday agent tool"

---

## Rules

- **Never hit the network in tests.** Use `FakeBarProvider` with constructor
  injection. Follow the `FakePriceProvider` pattern from `tests/test_scanner.py`.
- **Never invent a number.** Every VWAP, stop, target, entry, volume must come
  from bar data computation, not from the agent layer.
- **Do not output buy/sell calls.** Entry signals are data observations, not
  recommendations. Every signal output should carry: "Matches filter — not
  buy/sell advice."
- **One tool, one dispatch entry.** `scan_breitstein_intraday` goes in TOOLS and
  _DISPATCH exactly once. MCP server reflects automatically.
- **Protocols, not ABCs.** `BarProvider` is a duck-typing Protocol, same as
  `PriceProvider` and `ProfileProvider`.
- **All models are dataclasses.** No Pydantic. Follow the existing pattern in
  `app/models.py`.
