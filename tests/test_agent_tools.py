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


def test_scan_small_caps_tool_returns_candidates():
    from app.models import SmallCapCandidate, SmallCapEvidence, SmallCapScanOutput

    class FakeSmallCapService:
        def scan(self, **kwargs):
            return SmallCapScanOutput(
                preset=kwargs["preset_name"],
                run_ids=["run1"],
                candidate_count=1,
                candidates=[
                    SmallCapCandidate(
                        ticker="HOT",
                        name="Hot Stock Inc.",
                        market_cap=25_000_000,
                        gap_pct=12.0,
                        gap_dollar=0.72,
                        gap_basis="premarket",
                        volume=2_000_000,
                        rel_volume=5.0,
                        confidence="OK",
                        score=90,
                        grade="A_WATCH",
                        matched_signals=["small_cap_fit"],
                        missing_fields=["float"],
                        risk_notes=[],
                        sources=["fake"],
                        evidence=SmallCapEvidence(
                            ticker="HOT",
                            float_shares=8_000_000,
                            is_low_float=True,
                            float_rotation=2.0,
                            missing_fields=["catalyst"],
                            risk_notes=["filings are unknown"],
                        ),
                        timestamp="2026-06-28T12:00:00Z",
                    )
                ],
                notes=["note"],
            )

    out = tools.scan_small_caps(
        tickers="HOT",
        preset_name="sykes_small_cap_v0",
        service=FakeSmallCapService(),
    )

    assert out["candidate_count"] == 1
    assert out["candidates"][0]["ticker"] == "HOT"
    assert out["candidates"][0]["grade"] == "A_WATCH"
    assert out["candidates"][0]["gap_basis"] == "premarket"
    assert out["candidates"][0]["missing_fields"] == ["catalyst"]
    assert out["candidates"][0]["evidence"]["float_shares"] == 8_000_000
    assert out["candidates"][0]["evidence"]["is_low_float"] is True
    assert out["candidates"][0]["evidence"]["float_rotation"] == 2.0
    assert "catalyst" in out["candidates"][0]["evidence"]["missing_fields"]


def test_scan_small_caps_tool_accepts_market_selection():
    from app.models import SmallCapScanOutput

    class FakeSmallCapService:
        def scan(self, **kwargs):
            assert kwargs["market"] == "us-listed"
            assert kwargs["market_limit"] == 25
            return SmallCapScanOutput(
                preset=kwargs["preset_name"],
                run_ids=[],
                candidate_count=0,
                candidates=[],
                notes=["market universe us-listed"],
            )

    out = tools.scan_small_caps(
        market="us-listed",
        market_limit=25,
        preset_name="sykes_small_cap_v0",
        service=FakeSmallCapService(),
    )

    assert out["candidate_count"] == 0
    assert out["notes"] == ["market universe us-listed"]


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


def test_get_ticker_snapshot_uses_configured_providers(monkeypatch):
    # Regression: the snapshot tool must build its service the same way the scan
    # path does (with_configured_providers), so both agree on the number. A bare
    # SnapshotService() would be yfinance-only and drift from the scan's gap.
    fake = SnapshotService(yf_provider=FakePriceProvider({"NVDA": _quote("NVDA", 100.0, 104.0, 3.0e12)}))
    calls = {"n": 0}

    def factory(cls, db_path=None):
        calls["n"] += 1
        return fake

    monkeypatch.setattr(SnapshotService, "with_configured_providers", classmethod(factory))
    out = tools.get_ticker_snapshot(ticker="NVDA")  # no injected service -> default path
    assert calls["n"] == 1
    assert out["gap_pct"] == 4.0


def test_dispatch_unknown_tool():
    assert "error" in definitions.dispatch("nope", {})


def test_dispatch_logging_closes_connection(monkeypatch):
    from app import db as app_db

    class FakeConnection:
        def __init__(self):
            self.closed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def close(self):
            self.closed = True

    fake_conn = FakeConnection()
    logged: list[dict] = []

    def fake_log_agent_query(conn, **kwargs):
        assert conn is fake_conn
        logged.append(kwargs)

    monkeypatch.setattr(app_db, "get_connection", lambda db_path: fake_conn)
    monkeypatch.setattr(app_db, "log_agent_query", fake_log_agent_query)

    out = definitions.dispatch(
        "list_universes",
        {},
        user_query="what lists exist?",
        db_path="fake.sqlite",
    )

    assert "universes" in out
    assert fake_conn.closed is True
    assert logged[0]["tool_name"] == "list_universes"
    assert logged[0]["user_query"] == "what lists exist?"


def test_tool_definitions_are_well_formed():
    names = {t["name"] for t in definitions.TOOLS}
    assert names == {
        "scan_premarket",
        "scan_small_caps",
        "list_universes",
        "get_ticker_snapshot",
    }
    for tool in definitions.TOOLS:
        assert tool["description"]
        assert tool["input_schema"]["type"] == "object"
        assert "properties" in tool["input_schema"]

    small_cap_tool = next(tool for tool in definitions.TOOLS if tool["name"] == "scan_small_caps")
    assert "market" in small_cap_tool["input_schema"]["properties"]
    assert "market_limit" in small_cap_tool["input_schema"]["properties"]
