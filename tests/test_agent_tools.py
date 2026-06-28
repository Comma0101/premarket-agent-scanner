"""Agent tool-layer tests: JSON tools and the dispatcher.

All offline. Tools run against injected fake providers.
"""

from __future__ import annotations

from agent_tools import definitions, tools
from app.models import ProviderPriceData, utc_now_iso
from services.scanner_service import ScannerService
from services.snapshot_service import SnapshotService
from services.universe_service import UniverseService


class FakePriceProvider:
    source_name = "fake"

    def __init__(self, quotes):
        self._quotes = quotes

    def get_snapshot(self, ticker):
        t = ticker.upper()
        if t in self._quotes:
            return self._quotes[t]
        return ProviderPriceData(ticker=t, source=self.source_name, error="not_found")


def _quote(ticker, prev, pre, cap):
    return ProviderPriceData(
        ticker=ticker,
        source="yfinance",
        previous_close=prev,
        premarket_price=pre,
        latest_price=pre,
        volume=2_000_000,
        timestamp=utc_now_iso(),
        raw={"marketCap": cap},
    )


def _scanner(quotes):
    return ScannerService(
        UniverseService(),
        SnapshotService(yf_provider=FakePriceProvider(quotes)),
        persist=False,
    )


def test_scan_premarket_tool_returns_json_dict():
    quotes = {
        "NVDA": _quote("NVDA", 100.0, 107.0, 3.0e12),  # +7%
        "AMD": _quote("AMD", 100.0, 100.5, 2.5e11),  # +0.5%
    }
    out = tools.scan_premarket(
        tickers="NVDA,AMD", min_gap_abs=5.0, direction="up", service=_scanner(quotes)
    )
    assert out["result_count"] == 1
    assert out["results"][0]["ticker"] == "NVDA"
    assert out["results"][0]["gap_pct"] == 7.0
    assert out["results"][0]["gap_dollar"] == 7.0
    assert out["status"] == "OK"


def test_scan_premarket_tool_validates_selection_and_direction():
    assert "error" in tools.scan_premarket()
    assert "error" in tools.scan_premarket(tickers="NVDA", direction="sideways")


def test_list_universes_tool_shape():
    out = tools.list_universes(service=UniverseService())
    assert "MAG7" in out["universes"]
    assert out["universes"]["MAG7"]["count"] == len(out["universes"]["MAG7"]["tickers"])


def test_get_ticker_snapshot_tool():
    quotes = {"NVDA": _quote("NVDA", 100.0, 104.0, 3.0e12)}
    snap_service = SnapshotService(yf_provider=FakePriceProvider(quotes))
    out = tools.get_ticker_snapshot(ticker="NVDA", snapshot_service=snap_service)
    assert out["ticker"] == "NVDA"
    assert out["gap_pct"] == 4.0
    assert out["confidence"] == "OK"


def test_dispatch_unknown_tool():
    assert "error" in definitions.dispatch("nope", {})


def test_tool_definitions_are_well_formed():
    names = {t["name"] for t in definitions.TOOLS}
    assert names == {"scan_premarket", "list_universes", "get_ticker_snapshot"}
    for tool in definitions.TOOLS:
        assert tool["description"]
        assert tool["input_schema"]["type"] == "object"
        assert "properties" in tool["input_schema"]
