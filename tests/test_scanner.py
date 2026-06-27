"""End-to-end scanner logic tests using injected fake providers.

These never touch the network: a FakePriceProvider feeds deterministic data
into the real SnapshotService and ScannerService so we exercise gap math,
confidence labelling, filtering, and sorting exactly as production would.
"""

from __future__ import annotations

from app.models import (
    ProviderPriceData,
    ScanFilters,
    make_scan_filters,
    resolve_cap_tier,
    utc_now_iso,
)
from services.scanner_service import ScannerService, compute_gap_pct, compute_rel_volume
from services.snapshot_service import SnapshotService
from services.universe_service import UniverseService


class FakePriceProvider:
    source_name = "fake"

    def __init__(self, quotes: dict[str, ProviderPriceData]) -> None:
        self._quotes = quotes

    def get_snapshot(self, ticker: str) -> ProviderPriceData:
        normalized = ticker.upper()
        if normalized in self._quotes:
            return self._quotes[normalized]
        return ProviderPriceData(
            ticker=normalized, source=self.source_name, error="not_found"
        )


def _quote(ticker, prev, pre, cap, ts=None, vol=1_000_000, avg_vol=None) -> ProviderPriceData:
    ts = ts or utc_now_iso()  # fresh by default so rows are not flagged STALE
    return ProviderPriceData(
        ticker=ticker,
        source="fake",
        previous_close=prev,
        premarket_price=pre,
        latest_price=pre,
        volume=vol,
        timestamp=ts,
        raw={"marketCap": cap, "averageVolume": avg_vol},
    )


def _service(quotes: dict[str, ProviderPriceData]) -> ScannerService:
    snapshot_service = SnapshotService(yf_provider=FakePriceProvider(quotes))
    return ScannerService(
        universe_service=UniverseService(),
        snapshot_service=snapshot_service,
        persist=False,
    )


def test_compute_gap_pct():
    assert compute_gap_pct(100.0, 105.0) == 5.0
    assert compute_gap_pct(100.0, 95.0) == -5.0
    assert compute_gap_pct(None, 105.0) is None
    assert compute_gap_pct(0.0, 105.0) is None


def test_gap_up_filter_and_market_cap():
    quotes = {
        "NVDA": _quote("NVDA", prev=100.0, pre=108.0, cap=3.0e12),  # +8%, mega cap
        "AMD": _quote("AMD", prev=100.0, pre=101.0, cap=2.0e11),  # +1%
        "TINY": _quote("TINY", prev=10.0, pre=12.0, cap=5.0e8),  # +20% but small cap
    }
    service = _service(quotes)
    out = service.scan(
        tickers="NVDA,AMD,TINY",
        filters=ScanFilters(min_market_cap=1.0e10, min_gap_abs=5.0, direction="up"),
    )

    tickers = [r.ticker for r in out.results]
    assert tickers == ["NVDA"]  # AMD too small a gap, TINY too small a cap
    assert out.results[0].gap_pct == 8.0
    assert out.results[0].confidence == "OK"


def test_results_sorted_by_absolute_gap():
    quotes = {
        "A": _quote("A", prev=100.0, pre=103.0, cap=5.0e10),  # +3%
        "B": _quote("B", prev=100.0, pre=90.0, cap=5.0e10),  # -10%
        "C": _quote("C", prev=100.0, pre=106.0, cap=5.0e10),  # +6%
    }
    out = _service(quotes).scan(
        tickers="A,B,C", filters=ScanFilters(direction="both")
    )
    assert [r.ticker for r in out.results] == ["B", "C", "A"]


def test_missing_previous_close_is_excluded():
    quotes = {
        "GOOD": _quote("GOOD", prev=50.0, pre=55.0, cap=5.0e10),
        "BAD": ProviderPriceData(
            ticker="BAD", source="fake", premarket_price=10.0, raw={"marketCap": 5.0e10}
        ),
    }
    out = _service(quotes).scan(tickers="GOOD,BAD")
    assert [r.ticker for r in out.results] == ["GOOD"]


def test_missing_market_cap_label_when_cap_unknown():
    quotes = {"X": _quote("X", prev=100.0, pre=105.0, cap=None)}
    # No market-cap filter, so the row survives but is labelled.
    out = _service(quotes).scan(tickers="X", filters=ScanFilters(min_market_cap=0))
    assert len(out.results) == 1
    assert out.results[0].confidence == "MISSING_MARKET_CAP"


def test_only_confident_drops_flagged_rows():
    quotes = {"X": _quote("X", prev=100.0, pre=105.0, cap=None)}  # MISSING_MARKET_CAP
    out = _service(quotes).scan(
        tickers="X", filters=ScanFilters(include_low_confidence=False)
    )
    assert out.results == []


def test_compute_rel_volume():
    assert compute_rel_volume(3_000_000, 1_000_000) == 3.0
    assert compute_rel_volume(1_000_000, None) is None
    assert compute_rel_volume(None, 1_000_000) is None
    assert compute_rel_volume(1_000_000, 0) is None


def test_resolve_cap_tier_bounds():
    assert resolve_cap_tier("small") == (300e6, 2e9)
    assert resolve_cap_tier("MEGA") == (200e9, None)
    try:
        resolve_cap_tier("ginormous")
    except ValueError as exc:
        assert "Unknown cap tier" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_cap_tier_filters_small_cap_gappers():
    quotes = {
        # Small-cap gapper: $800M cap, +12%, high RVOL
        "SMOL": _quote("SMOL", prev=10.0, pre=11.2, cap=8.0e8, vol=5_000_000, avg_vol=1_000_000),
        # Large cap that also gapped — must be excluded by the small tier
        "NVDA": _quote("NVDA", prev=100.0, pre=112.0, cap=3.0e12, vol=9_000_000, avg_vol=3_000_000),
    }
    filters = make_scan_filters(cap_tier="small", min_gap_abs=5.0, direction="up")
    out = _service(quotes).scan(tickers="SMOL,NVDA", filters=filters)
    assert [r.ticker for r in out.results] == ["SMOL"]
    assert out.results[0].rel_volume == 5.0


def test_min_rel_volume_filter():
    quotes = {
        "HOT": _quote("HOT", prev=10.0, pre=11.0, cap=5.0e8, vol=6_000_000, avg_vol=1_000_000),  # 6x
        "COLD": _quote("COLD", prev=10.0, pre=11.0, cap=5.0e8, vol=1_200_000, avg_vol=1_000_000),  # 1.2x
    }
    filters = make_scan_filters(min_gap_abs=5.0, min_rel_volume=3.0)
    out = _service(quotes).scan(tickers="HOT,COLD", filters=filters)
    assert [r.ticker for r in out.results] == ["HOT"]


def test_min_volume_filter_excludes_thin_names():
    quotes = {
        "LIQ": _quote("LIQ", prev=10.0, pre=11.0, cap=5.0e8, vol=4_000_000),
        "THIN": _quote("THIN", prev=10.0, pre=11.0, cap=5.0e8, vol=50_000),
    }
    filters = make_scan_filters(min_gap_abs=5.0, min_volume=1_000_000)
    out = _service(quotes).scan(tickers="LIQ,THIN", filters=filters)
    assert [r.ticker for r in out.results] == ["LIQ"]
