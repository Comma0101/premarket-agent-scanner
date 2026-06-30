"""Agent tool-layer tests: JSON tools and the dispatcher.

All offline. Tools run against injected fake providers.
"""

from __future__ import annotations

from types import SimpleNamespace

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
    from app.models import CatalystEvent, SmallCapCandidate, SmallCapEvidence, SmallCapScanOutput

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
                        missing_fields=["short_interest"],
                        risk_notes=[],
                        sources=["fake"],
                        evidence=SmallCapEvidence(
                            ticker="HOT",
                            float_shares=8_000_000,
                            is_low_float=True,
                            float_rotation=2.0,
                            catalysts=[
                                CatalystEvent(
                                    ticker="HOT",
                                    headline="Announces FDA clearance",
                                    published_at="2026-06-28T12:00:00Z",
                                    source="PR",
                                    catalyst_quality="hard",
                                    recency_minutes=30.0,
                                )
                            ],
                            missing_fields=["short_interest"],
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
    assert out["session_banner"].startswith("PRE_MARKET, Jun 28 8:00 AM ET.")
    assert out["candidates"][0]["ticker"] == "HOT"
    assert out["candidates"][0]["grade"] == "A_WATCH"
    assert out["candidates"][0]["gap_basis"] == "premarket"
    assert out["candidates"][0]["as_of_et"] == "Jun 28 8:00 AM ET"
    assert out["candidates"][0]["as_of_utc"] == "2026-06-28T12:00:00Z"
    assert out["candidates"][0]["session_mode"] == "PRE_MARKET"
    assert out["candidates"][0]["data_caveat"] is None
    assert out["candidates"][0]["missing_fields"] == ["short_interest"]
    assert out["candidates"][0]["evidence"]["float_shares"] == 8_000_000
    assert out["candidates"][0]["evidence"]["catalysts"][0]["catalyst_quality"] == "hard"
    assert out["candidates"][0]["evidence"]["catalysts"][0]["recency_minutes"] == 30.0
    assert out["candidates"][0]["evidence"]["is_low_float"] is True
    assert out["candidates"][0]["evidence"]["float_rotation"] == 2.0
    assert "short_interest" in out["candidates"][0]["evidence"]["missing_fields"]
    assert "rejected" not in out
    assert "rejected_count" not in out


def test_scan_small_caps_tool_can_include_rejected_rows():
    from app.models import SmallCapCandidate, SmallCapScanOutput

    class FakeSmallCapService:
        def scan(self, **kwargs):
            assert kwargs["include_rejected"] is True
            return SmallCapScanOutput(
                preset=kwargs["preset_name"],
                run_ids=["run1"],
                candidate_count=0,
                candidates=[],
                notes=[],
                rejected_count=1,
                rejected=[
                    SmallCapCandidate(
                        ticker="BAD",
                        name=None,
                        market_cap=25_000_000,
                        gap_pct=12.0,
                        gap_dollar=0.72,
                        gap_basis="last_trade",
                        volume=2_000_000,
                        rel_volume=5.0,
                        confidence="STALE_DATA",
                        score=0,
                        grade="REJECT",
                        matched_signals=["unusable_confidence"],
                        risk_notes=["Rejected because confidence is STALE_DATA."],
                        sources=["fake"],
                        timestamp="2026-06-29T23:30:00Z",
                    )
                ],
                zero_result_reason="all_failed_data_quality",
                relax_suggestions=["Run during PRE_MARKET for clean gap data."],
            )

    out = tools.scan_small_caps(
        tickers="BAD",
        preset_name="sykes_small_cap_v0",
        include_rejected=True,
        service=FakeSmallCapService(),
    )

    assert out["candidate_count"] == 0
    assert out["rejected_count"] == 1
    assert out["rejected"][0]["ticker"] == "BAD"
    assert out["rejected"][0]["as_of_et"] == "Jun 29 7:30 PM ET"
    assert out["rejected"][0]["session_mode"] == "POST_MARKET"
    assert out["rejected"][0]["data_caveat"].startswith(
        "POST_MARKET: last_trade / STALE_DATA"
    )
    assert out["zero_result_reason"] == "all_failed_data_quality"
    assert out["relax_suggestions"] == ["Run during PRE_MARKET for clean gap data."]


def test_scan_small_caps_tool_accepts_market_selection():
    from app.models import SmallCapScanOutput

    class FakeSmallCapService:
        def scan(self, **kwargs):
            assert kwargs["market"] == "us-listed"
            assert kwargs["market_limit"] == 25
            assert kwargs["max_workers"] == 6
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
        max_workers=6,
        preset_name="sykes_small_cap_v0",
        service=FakeSmallCapService(),
    )

    assert out["candidate_count"] == 0
    assert out["notes"] == ["market universe us-listed"]


def test_scan_small_caps_tool_can_opt_into_live_catalyst_refresh(monkeypatch):
    from app.models import SmallCapScanOutput
    from providers import news_provider as news_module
    from services import small_cap_evidence_service as evidence_module
    from services import small_cap_scanner_service as scanner_module

    calls = {"rss": 0, "evidence": 0, "scanner": 0}

    class FakeRSSNewsProvider:
        def __init__(self):
            calls["rss"] += 1

    class FakeEvidenceService:
        def __init__(self, news_provider):
            calls["evidence"] += 1
            assert isinstance(news_provider, FakeRSSNewsProvider)

    class FakeScannerService:
        def __init__(self, evidence_service):
            calls["scanner"] += 1
            assert isinstance(evidence_service, FakeEvidenceService)

        def scan(self, **kwargs):
            return SmallCapScanOutput(
                preset=kwargs["preset_name"],
                run_ids=[],
                candidate_count=0,
                candidates=[],
                notes=["scan note"],
            )

    monkeypatch.setattr(news_module, "RSSNewsProvider", FakeRSSNewsProvider)
    monkeypatch.setattr(evidence_module, "SmallCapEvidenceService", FakeEvidenceService)
    monkeypatch.setattr(scanner_module, "SmallCapScannerService", FakeScannerService)

    out = tools.scan_small_caps(tickers="HOT", refresh_catalysts=True)

    assert calls == {"rss": 1, "evidence": 1, "scanner": 1}
    assert out["candidate_count"] == 0
    assert out["notes"][0].startswith("Live catalyst RSS refresh enabled")


def test_scan_small_caps_tool_surfaces_market_selection_errors():
    class RaisingSmallCapService:
        def scan(self, **kwargs):
            raise ValueError("market universe unavailable")

    out = tools.scan_small_caps(
        market="us-listed",
        preset_name="sykes_small_cap_v0",
        service=RaisingSmallCapService(),
    )

    assert out == {"error": "market universe unavailable"}


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
    assert out["data_status"] == "live"
    assert out["provider_failures"] == {}


def test_get_ticker_snapshot_surfaces_provider_failures_and_data_status():
    """Reproduces the desk live-data failure: yfinance DNS-fails, no Alpaca.

    The tool must surface a structured failure so the desk can triage without
    parsing free-text notes. No price is invented; all fields stay None.
    """

    class ErroringYF:
        source_name = "yfinance"

        def get_snapshot(self, ticker):
            return ProviderPriceData(
                ticker=ticker.upper(),
                source="yfinance",
                error="ConnectionError: DNS failure for guce.yahoo.com",
                notes=["get_info failed: cannot resolve guce.yahoo.com"],
            )

    svc = SnapshotService(yf_provider=ErroringYF(), alpaca_provider=None)
    out = tools.get_ticker_snapshot(ticker="MRVL", snapshot_service=svc)

    assert out["confidence"] == "ERROR"
    assert out["data_status"] == "provider_failure"
    assert out["provider_failures"] == {
        "yfinance": "ConnectionError: DNS failure for guce.yahoo.com",
    }
    # Prime directive: never invent prices.
    assert out["previous_close"] is None
    assert out["premarket_price"] is None
    assert out["latest_price"] is None
    assert out["gap_pct"] is None
    assert out["gap_basis"] is None
    # Existing fields preserved so callers can still inspect notes.
    assert any("yfinance:" in note for note in out["notes"])


def test_explain_breitstein_ticker_tool_returns_moment_view():
    class FakeBreitsteinService:
        def scan(self, **kwargs):
            assert kwargs["tickers"] == "MRVL"
            return SimpleNamespace(
                preset=kwargs["preset_name"],
                run_ids=["run-1"],
                phase="1",
                candidate_count=0,
                candidates=[],
                notes=["Phase 1 underlying watchlist only."],
            )

    quotes = {
        "MRVL": ProviderPriceData(
            ticker="MRVL",
            source="yfinance",
            previous_close=266.77,
            latest_price=277.75,
            volume=31_025_441,
            timestamp="2026-06-29T20:00:00+00:00",
            raw={"marketCap": 243_184_893_952, "averageVolume": 43_000_000},
        )
    }
    snap_service = SnapshotService(yf_provider=FakePriceProvider(quotes))

    out = tools.explain_breitstein_ticker(
        ticker="MRVL",
        snapshot_service=snap_service,
        service=FakeBreitsteinService(),
    )

    assert out["ticker"] == "MRVL"
    assert out["verdict"] == "No Phase 1 setup"
    assert out["moment_state"] == "not_ready_data_quality"
    assert out["data_card"]["gap_basis"] == "last_trade"
    assert out["data_card"]["confidence"] == "STALE_DATA"
    assert any(item["label"] == "Participation" for item in out["setup_stack"])


def test_scan_breitstein_intraday_tool_with_injected_service():
    from app.models import IntradayBarSeries

    class FakeIntradayService:
        def fetch_bars(self, ticker, timeframe="2Min", start="", end="", limit=100):
            return IntradayBarSeries(
                ticker=ticker,
                timeframe=timeframe,
                bars=[],
                source="fake",
                fetched_at=utc_now_iso(),
            )

        def compute_vwap(self, series):
            return None

        def detect_entry_signal(self, series, vwap):
            return None

    out = tools.scan_breitstein_intraday(
        tickers=["MRVL"], service=FakeIntradayService()
    )

    assert out["ticker_count"] == 1
    assert out["signal_count"] == 0
    assert out["signals"] == []
    assert out["notes"]


def test_scan_breitstein_intraday_tool_returns_signal():
    from app.models import BreitsteinEntrySignal

    class FakeIntradayServiceWithSignal:
        def fetch_bars(self, ticker, timeframe="2Min", start="", end="", limit=100):
            return SimpleNamespace(ticker=ticker, timeframe=timeframe, bars=[])

        def compute_vwap(self, series):
            return 108.0

        def detect_entry_signal(self, series, vwap):
            return BreitsteinEntrySignal(
                ticker=series.ticker,
                direction="long",
                entry_price=109.0,
                stop_price=106.0,
                target_price=None,
                prior_bar_high=108.0,
                prior_bar_low=106.0,
                vwap=vwap,
                vwap_filter_passed=True,
                volume_2x_confirmed=True,
                consecutive_bars=-3,
                rate_of_change=-1.0,
                bollinger_width=2.5,
                timestamp="2026-06-29T14:08:00Z",
                confidence="OK",
            )

    out = tools.scan_breitstein_intraday(
        tickers=["MRVL"], service=FakeIntradayServiceWithSignal()
    )

    assert out["signal_count"] == 1
    assert out["signals"][0]["ticker"] == "MRVL"
    assert out["signals"][0]["direction"] == "long"
    assert out["signals"][0]["entry_price"] == 109.0
    assert out["signals"][0]["stop_price"] == 106.0


def test_scan_breitstein_intraday_tool_requires_tickers():
    out = tools.scan_breitstein_intraday(tickers=[])
    assert "error" in out


def test_scan_temiz_first_red_day_tool_returns_reference_signal():
    from app.models import FirstRedDaySignal

    class FakeTemizService:
        def detect_first_red_day(self, ticker):
            return FirstRedDaySignal(
                ticker=ticker,
                consecutive_green_days=3,
                breakdown_reference_price=13.0,
                risk_reference_price=14.0,
                prior_day_close=13.0,
                hod_before_breakdown=14.0,
                breakdown_bar_low=12.5,
                vwap=13.4,
                vwap_filter_passed=True,
                timestamp="2026-06-29T14:08:00Z",
                source="fake-bars",
                fetched_at="2026-06-29T14:10:00Z",
                confidence="OK",
                notes=["reference only"],
            )

    out = tools.scan_temiz_first_red_day(
        tickers=["HOT"], service=FakeTemizService()
    )

    assert out["ticker_count"] == 1
    assert out["signal_count"] == 1
    assert out["error_count"] == 0
    assert out["signals"][0]["ticker"] == "HOT"
    assert out["signals"][0]["breakdown_reference_price"] == 13.0
    assert out["signals"][0]["risk_reference_price"] == 14.0
    assert out["signals"][0]["source"] == "fake-bars"
    assert out["notes"]


def test_scan_temiz_first_red_day_tool_surfaces_ticker_errors():
    class RaisingTemizService:
        def detect_first_red_day(self, ticker):
            raise RuntimeError("bars unavailable")

    out = tools.scan_temiz_first_red_day(
        tickers=["HOT"], service=RaisingTemizService()
    )

    assert out["signal_count"] == 0
    assert out["error_count"] == 1
    assert out["errors"][0]["ticker"] == "HOT"
    assert out["errors"][0]["confidence"] == "ERROR"
    assert out["errors"][0]["missing_fields"] == ["bar_data"]
    assert "bars unavailable" in out["errors"][0]["error"]


def test_scan_temiz_first_red_day_tool_requires_tickers():
    out = tools.scan_temiz_first_red_day(tickers=[])
    assert "error" in out


def test_scan_grittani_morning_panic_tool_returns_reference_signal():
    from app.models import GrittaniPanicSignal

    class FakeGrittaniService:
        def detect_morning_panic(self, ticker, rvol=None):
            assert rvol == 6.5
            return GrittaniPanicSignal(
                ticker=ticker,
                multi_day_run_pct=200.0,
                intraday_drop_pct=40.0,
                panic_high=20.0,
                panic_low=12.0,
                bounce_reference_price=13.0,
                risk_reference_price=12.0,
                prior_day_close=15.0,
                vwap=14.2,
                rvol=rvol,
                timestamp="2026-06-29T13:38:00Z",
                source="fake-bars",
                fetched_at="2026-06-29T14:10:00Z",
                confidence="OK",
                notes=["reference only"],
            )

    out = tools.scan_grittani_morning_panic(
        tickers=["HOT"],
        rvol_by_ticker={"HOT": 6.5},
        service=FakeGrittaniService(),
    )

    assert out["ticker_count"] == 1
    assert out["signal_count"] == 1
    assert out["error_count"] == 0
    assert out["signals"][0]["ticker"] == "HOT"
    assert out["signals"][0]["bounce_reference_price"] == 13.0
    assert out["signals"][0]["risk_reference_price"] == 12.0
    assert out["signals"][0]["rvol"] == 6.5
    assert out["signals"][0]["source"] == "fake-bars"
    assert out["notes"]


def test_scan_grittani_morning_panic_tool_surfaces_ticker_errors():
    class RaisingGrittaniService:
        def detect_morning_panic(self, ticker, rvol=None):
            raise RuntimeError("bars unavailable")

    out = tools.scan_grittani_morning_panic(
        tickers=["HOT"],
        rvol_by_ticker={"HOT": 6.5},
        service=RaisingGrittaniService(),
    )

    assert out["signal_count"] == 0
    assert out["error_count"] == 1
    assert out["errors"][0]["ticker"] == "HOT"
    assert out["errors"][0]["confidence"] == "ERROR"
    assert out["errors"][0]["missing_fields"] == ["bar_data"]
    assert "bars unavailable" in out["errors"][0]["error"]


def test_scan_grittani_morning_panic_tool_requires_tickers():
    out = tools.scan_grittani_morning_panic(tickers=[])
    assert "error" in out


def test_get_trader_context_tool_with_injected_service():
    class FakeTraderContextService:
        def build_context(self, **kwargs):
            assert kwargs["ticker"] == "HOT"
            assert kwargs["trader_profile"] == "timothy_sykes"
            assert kwargs["include_intraday"] is True
            assert kwargs["include_daily"] is True
            assert kwargs["refresh_catalysts"] is False
            return {
                "ticker": "HOT",
                "trader_profile": "timothy_sykes",
                "snapshot": {"confidence": "OK"},
                "missing_fields": [],
            }

    out = tools.get_trader_context(
        ticker="HOT",
        trader_profile="timothy_sykes",
        include_intraday=True,
        include_daily=True,
        service=FakeTraderContextService(),
    )

    assert out["ticker"] == "HOT"
    assert out["snapshot"]["confidence"] == "OK"


def test_explain_ticker_as_trader_tool_formats_context_packet():
    class FakeTraderContextService:
        def build_context(self, **kwargs):
            assert kwargs["ticker"] == "HOT"
            assert kwargs["trader_profile"] == "timothy_sykes"
            assert kwargs["include_intraday"] is True
            assert kwargs["include_daily"] is False
            assert kwargs["refresh_catalysts"] is False
            return {
                "ticker": "HOT",
                "trader_profile": "timothy_sykes",
                "snapshot": {
                    "ticker": "HOT",
                    "previous_close": 10.0,
                    "premarket_price": 11.2,
                    "latest_price": 11.2,
                    "gap_pct": 12.0,
                    "gap_dollar": 1.2,
                    "gap_basis": "premarket",
                    "market_cap": 75_000_000.0,
                    "volume": 2_000_000.0,
                    "rel_volume": 4.5,
                    "confidence": "OK",
                    "sources": ["fake"],
                    "timestamp": "2026-06-29T13:30:00Z",
                },
                "evidence": {
                    "float_shares": 5_000_000.0,
                    "is_low_float": True,
                    "catalysts": [{"headline": "HOT wins supply deal"}],
                    "filings": [],
                    "missing_fields": ["short_interest"],
                },
                "technicals": {"intraday": None, "daily": None},
                "missing_fields": ["short_interest", "intraday_bars"],
                "sources": ["fake"],
                "notes": [],
            }

    out = tools.explain_ticker_as_trader(
        ticker="HOT",
        trader_profile="timothy_sykes",
        include_intraday=True,
        service=FakeTraderContextService(),
    )

    assert out["ticker"] == "HOT"
    assert out["trader"] == "timothy_sykes"
    assert out["verdict"] == "Context ready"
    assert out["data_card"]["gap_basis"] == "premarket"
    assert out["disclaimer"].startswith("Matches your filter")


def test_explain_ticker_as_trader_tool_requires_ticker():
    out = tools.explain_ticker_as_trader(ticker="")
    assert "error" in out


def test_run_desk_tool_returns_aggregated_views():
    class FakeDeskRunService:
        def run(self, **kwargs):
            assert kwargs["tickers"] == ["MRVL", "HOOD"]
            assert kwargs["universe"] is None
            assert kwargs["watchlist"] is None
            assert kwargs["market"] is None
            assert kwargs["all_universes"] is False
            assert kwargs["trader_profiles"] == ["lance_breitstein"]
            assert kwargs["include_intraday"] is True
            assert kwargs["include_daily"] is False
            assert kwargs["refresh_catalysts"] is False
            return {
                "ticker_count": 2,
                "trader_profiles": ["lance_breitstein"],
                "tickers": [
                    {
                        "ticker": "MRVL",
                        "data_quality": {
                            "gap_basis": "last_trade",
                            "confidence": "STALE_DATA",
                            "as_of": "2026-06-29T20:00:00Z",
                            "sources": ["fake"],
                        },
                        "views": {"lance_breitstein": {"ticker": "MRVL"}},
                        "errors": [],
                    }
                ],
                "disclaimer": "Matches your filter — not buy/sell advice. Verify before acting.",
            }

    out = tools.run_desk(
        tickers="MRVL, HOOD",
        trader_profiles=["lance_breitstein"],
        include_intraday=True,
        service=FakeDeskRunService(),
    )

    assert out["ticker_count"] == 2
    assert out["trader_profiles"] == ["lance_breitstein"]
    assert out["tickers"][0]["ticker"] == "MRVL"


def test_run_desk_tool_accepts_watchlist_selection():
    class FakeDeskRunService:
        def run(self, **kwargs):
            assert kwargs["tickers"] is None
            assert kwargs["watchlist"] == "ACTIVE"
            return {
                "ticker_count": 1,
                "selection": {"source": "universe_service", "label": "WATCHLIST:ACTIVE"},
                "tickers": [],
                "trader_profiles": ["timothy_sykes"],
                "disclaimer": "Matches your filter — not buy/sell advice. Verify before acting.",
            }

    out = tools.run_desk(watchlist="ACTIVE", service=FakeDeskRunService())

    assert out["selection"]["label"] == "WATCHLIST:ACTIVE"


def test_run_desk_tool_requires_selection():
    out = tools.run_desk()
    assert "error" in out


def test_run_morning_brief_tool_returns_packet():
    class FakeMorningBriefService:
        def run(self, **kwargs):
            assert kwargs["profile"] == "tim_grittani"
            assert kwargs["market"] == "us-listed"
            assert kwargs["market_limit"] == 25
            assert kwargs["save_journal"] is False
            return {
                "agent_name": "premarket_desk",
                "strategy": "tim_grittani",
                "status": "OK",
                "brief_summary": "1 primary.",
                "watchlist": {"primary_watch": [], "monitoring": []},
            }

    out = tools.run_morning_brief(
        profile="tim_grittani",
        market="us-listed",
        market_limit=25,
        save_journal=False,
        service=FakeMorningBriefService(),
    )

    assert out["agent_name"] == "premarket_desk"
    assert out["strategy"] == "tim_grittani"
    assert out["brief_summary"] == "1 primary."


def test_run_morning_brief_tool_requires_selection():
    out = tools.run_morning_brief()
    assert "error" in out


def test_deep_dive_ticker_tool_returns_packet():
    class FakeDeepDiveService:
        def run(self, **kwargs):
            assert kwargs["ticker"] == "HOT"
            assert kwargs["trader_profile"] == "alex_temiz"
            assert kwargs["include_intraday"] is True
            assert kwargs["include_daily"] is True
            assert kwargs["refresh_catalysts"] is False
            return {
                "ticker": "HOT",
                "status": "OK",
                "snapshot": {"confidence": "OK"},
                "scanner_results": {"temiz_first_red_day": {"triggered": False}},
                "disclaimer": "Matches your filter — not buy/sell advice. Verify before acting.",
            }

    out = tools.deep_dive_ticker(
        ticker="HOT",
        trader_profile="alex_temiz",
        include_intraday=True,
        include_daily=True,
        service=FakeDeepDiveService(),
    )

    assert out["ticker"] == "HOT"
    assert out["status"] == "OK"
    assert out["snapshot"]["confidence"] == "OK"


def test_deep_dive_ticker_tool_requires_ticker():
    out = tools.deep_dive_ticker(ticker="")
    assert "error" in out


def test_get_trader_context_tool_requires_ticker():
    out = tools.get_trader_context(ticker="")
    assert "error" in out


def test_get_trader_context_tool_wires_bar_provider_for_technicals(monkeypatch):
    from providers import alpaca_provider as alpaca_module
    from services import trader_context_service as context_module

    calls = {"alpaca": 0, "context": 0}

    class FakeAlpacaProvider:
        def __init__(self):
            calls["alpaca"] += 1

    class FakeTraderContextService:
        def __init__(self, bar_provider=None):
            calls["context"] += 1
            assert isinstance(bar_provider, FakeAlpacaProvider)

        def build_context(self, **kwargs):
            return {
                "ticker": kwargs["ticker"],
                "technicals": {"intraday": None, "daily": None},
                "missing_fields": ["intraday_bars", "daily_bars"],
            }

    monkeypatch.setattr(alpaca_module, "AlpacaProvider", FakeAlpacaProvider)
    monkeypatch.setattr(context_module, "TraderContextService", FakeTraderContextService)

    out = tools.get_trader_context(
        ticker="HOT",
        include_intraday=True,
        include_daily=True,
    )

    assert calls == {"alpaca": 1, "context": 1}
    assert out["ticker"] == "HOT"


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
        "scan_breitstein",
        "explain_breitstein_ticker",
        "scan_breitstein_intraday",
        "scan_temiz_first_red_day",
        "scan_grittani_morning_panic",
        "get_trader_context",
        "explain_ticker_as_trader",
        "run_desk",
        "run_morning_brief",
        "deep_dive_ticker",
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
    assert "max_workers" in small_cap_tool["input_schema"]["properties"]
    assert "refresh_catalysts" in small_cap_tool["input_schema"]["properties"]

    breitstein_tool = next(tool for tool in definitions.TOOLS if tool["name"] == "scan_breitstein")
    assert "watchlist" in breitstein_tool["input_schema"]["properties"]
    assert "market" in breitstein_tool["input_schema"]["properties"]
    assert "market_limit" in breitstein_tool["input_schema"]["properties"]
    assert "max_workers" in breitstein_tool["input_schema"]["properties"]

    explain_tool = next(tool for tool in definitions.TOOLS if tool["name"] == "explain_breitstein_ticker")
    assert explain_tool["input_schema"]["required"] == ["ticker"]

    intraday_tool = next(tool for tool in definitions.TOOLS if tool["name"] == "scan_breitstein_intraday")
    assert intraday_tool["input_schema"]["required"] == ["tickers"]

    temiz_tool = next(tool for tool in definitions.TOOLS if tool["name"] == "scan_temiz_first_red_day")
    assert temiz_tool["input_schema"]["required"] == ["tickers"]

    grittani_tool = next(tool for tool in definitions.TOOLS if tool["name"] == "scan_grittani_morning_panic")
    assert grittani_tool["input_schema"]["required"] == ["tickers"]
    assert "rvol_by_ticker" in grittani_tool["input_schema"]["properties"]

    context_tool = next(tool for tool in definitions.TOOLS if tool["name"] == "get_trader_context")
    assert context_tool["input_schema"]["required"] == ["ticker"]

    explain_context_tool = next(tool for tool in definitions.TOOLS if tool["name"] == "explain_ticker_as_trader")
    assert explain_context_tool["input_schema"]["required"] == ["ticker"]

    run_desk_tool = next(tool for tool in definitions.TOOLS if tool["name"] == "run_desk")
    assert run_desk_tool["input_schema"]["required"] == []
    assert "trader_profiles" in run_desk_tool["input_schema"]["properties"]
    assert "watchlist" in run_desk_tool["input_schema"]["properties"]
    assert "market" in run_desk_tool["input_schema"]["properties"]

    morning_tool = next(tool for tool in definitions.TOOLS if tool["name"] == "run_morning_brief")
    assert morning_tool["input_schema"]["required"] == []
    assert "profile" in morning_tool["input_schema"]["properties"]
    assert "save_journal" in morning_tool["input_schema"]["properties"]

    deep_dive_tool = next(tool for tool in definitions.TOOLS if tool["name"] == "deep_dive_ticker")
    assert deep_dive_tool["input_schema"]["required"] == ["ticker"]
    assert "trader_profile" in deep_dive_tool["input_schema"]["properties"]
