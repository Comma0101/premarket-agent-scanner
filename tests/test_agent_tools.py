"""Agent tool-layer tests: JSON tools and the dispatcher.

All offline. Tools run against injected fake providers.
"""

from __future__ import annotations

from agent_tools import definitions, tools
from app.models import HaltStatus, ProviderPriceData, utc_now_iso
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
        raw={"marketCap": cap, "averageVolume": 1_000_000},
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


def test_get_ticker_snapshot_tool_surfaces_halt_status():
    class FakeSnapshotService:
        def build_snapshot(self, ticker):
            from app.models import CombinedSnapshot

            return CombinedSnapshot(
                ticker=ticker,
                timestamp=utc_now_iso(),
                previous_close=100.0,
                premarket_price=105.0,
                latest_price=105.0,
                open_price=None,
                high=None,
                low=None,
                volume=1_000_000,
                source_primary="fake",
                source_secondary=None,
                confidence="OK",
                sources=["fake"],
                halt_status=HaltStatus(
                    ticker=ticker,
                    status="HALTED",
                    reason_code="LUDP",
                    halt_time="07/01/2026 09:35:12",
                    source="nasdaq_trader_halts",
                ),
            )

    out = tools.get_ticker_snapshot(
        ticker="ABCD",
        snapshot_service=FakeSnapshotService(),
    )

    assert out["halt_status"] == {
        "ticker": "ABCD",
        "status": "HALTED",
        "reason_code": "LUDP",
        "reason": None,
        "halt_time": "07/01/2026 09:35:12",
        "resume_time": None,
        "source": "nasdaq_trader_halts",
        "raw": {},
        "notes": [],
        "error": None,
    }


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
    assert out["candidates"][0]["ticker"] == "HOT"
    assert out["candidates"][0]["grade"] == "A_WATCH"
    assert out["candidates"][0]["gap_basis"] == "premarket"
    assert out["candidates"][0]["missing_fields"] == ["short_interest"]
    assert out["candidates"][0]["evidence"]["float_shares"] == 8_000_000
    assert out["candidates"][0]["evidence"]["catalysts"][0]["catalyst_quality"] == "hard"
    assert out["candidates"][0]["evidence"]["catalysts"][0]["recency_minutes"] == 30.0
    assert out["candidates"][0]["evidence"]["is_low_float"] is True
    assert out["candidates"][0]["evidence"]["float_rotation"] == 2.0
    assert "short_interest" in out["candidates"][0]["evidence"]["missing_fields"]


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


def test_scan_small_caps_tool_accepts_live_intraday():
    from app.models import SmallCapScanOutput

    class FakeSmallCapService:
        def scan(self, **kwargs):
            assert kwargs["live_intraday"] is True
            return SmallCapScanOutput(
                preset=kwargs["preset_name"],
                run_ids=[],
                candidate_count=0,
                candidates=[],
                notes=["live intraday"],
            )

    out = tools.scan_small_caps(
        tickers="HOT",
        live_intraday=True,
        service=FakeSmallCapService(),
    )

    assert out["notes"] == ["live intraday"]


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
    assert out["rel_volume"] == 2.0
    assert out["rel_volume_basis"] == "session_volume_vs_average_daily_volume"
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


def test_get_ticker_snapshot_surfaces_data_status_and_provider_failures():
    yf = ProviderPriceData(
        ticker="NVDA",
        source="yfinance",
        notes=["Failed to fetch yfinance quote: DNS failure"],
        error="DNS failure",
    )
    alpaca = ProviderPriceData(
        ticker="NVDA",
        source="alpaca",
        notes=["Alpaca latest trade unavailable: DNS failure"],
        error="no_usable_alpaca_snapshot",
    )
    snap_service = SnapshotService(
        yf_provider=FakePriceProvider({"NVDA": yf}),
        alpaca_provider=FakePriceProvider({"NVDA": alpaca}),
    )

    out = tools.get_ticker_snapshot(ticker="NVDA", snapshot_service=snap_service)

    assert out["confidence"] == "ERROR"
    assert out["data_status"] == "provider_failure"
    assert out["provider_failures"] == {
        "yfinance": "DNS failure",
        "alpaca": "no_usable_alpaca_snapshot",
    }
    assert out["sources"] == []


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


def test_scan_breitstein_intraday_tool_with_injected_service():
    from app.models import IntradayBarSeries

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
    from tests.test_intraday_analysis import _make_series

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


def test_build_lance_intraday_plan_tool_with_injected_service():
    class FakeLancePlanService:
        def build_plan(self, ticker):
            return {
                "ticker": ticker,
                "trader": "lance_breitstein",
                "state": "watching",
                "data_quality": {"confidence": "OK"},
            }

    out = tools.build_lance_intraday_plan(
        ticker="IBM",
        service=FakeLancePlanService(),
    )

    assert out["ticker"] == "IBM"
    assert out["trader"] == "lance_breitstein"
    assert out["state"] == "watching"


def test_build_lance_intraday_plan_tool_requires_ticker():
    out = tools.build_lance_intraday_plan(ticker="")
    assert "error" in out


def test_build_lance_swing_plan_tool_with_injected_service():
    class FakeLanceSwingPlanService:
        def build(self, **kwargs):
            assert kwargs["tickers"] == ["IBM", "MRVL"]
            assert kwargs["lookback_days"] == 40
            return {
                "agent_name": "lance_swing",
                "strategy": "Lance Breitstein daily/swing planning",
                "plans": [{"ticker": "IBM", "state": "active_watch"}],
            }

    out = tools.build_lance_swing_plan(
        tickers=["IBM", "MRVL"],
        lookback_days=40,
        service=FakeLanceSwingPlanService(),
    )

    assert out["agent_name"] == "lance_swing"
    assert out["plans"][0]["ticker"] == "IBM"
    assert out["plans"][0]["state"] == "active_watch"


def test_build_lance_swing_plan_tool_requires_tickers():
    out = tools.build_lance_swing_plan(tickers=[])
    assert "error" in out


def test_build_lance_swing_plan_tool_resolves_universe_and_watchlist():
    from services.universe_service import UniverseSelection

    class FakeUniverseService:
        def resolve_selection(self, **kwargs):
            assert kwargs == {
                "tickers": None,
                "universe": "AI_SEMIS_MEMORY",
                "watchlist": "HOT_ACTIVE",
                "all_universes": False,
            }
            return UniverseSelection(
                tickers=["MU", "HOOD"],
                memberships={"MU": ["AI_SEMIS_MEMORY"], "HOOD": ["WATCHLIST:HOT_ACTIVE"]},
                label="AI_SEMIS_MEMORY,WATCHLIST:HOT_ACTIVE",
            )

    class FakeLanceSwingPlanService:
        def build(self, **kwargs):
            assert kwargs["tickers"] == ["MU", "HOOD"]
            assert kwargs["lookback_days"] == 60
            return {
                "agent_name": "lance_swing",
                "plans": [{"ticker": "MU", "state": "mean_reversion_watch"}],
            }

    out = tools.build_lance_swing_plan(
        tickers=None,
        universe="AI_SEMIS_MEMORY",
        watchlist="HOT_ACTIVE",
        service=FakeLanceSwingPlanService(),
        universe_service=FakeUniverseService(),
    )

    assert out["selection"] == "AI_SEMIS_MEMORY,WATCHLIST:HOT_ACTIVE"
    assert out["selection_count"] == 2
    assert out["plans"][0]["state"] == "mean_reversion_watch"


def test_run_lance_swing_cycle_tool_with_injected_service():
    class FakeLanceSwingCycleService:
        def run(self, **kwargs):
            assert kwargs == {
                "tickers": None,
                "universe": "AI_SEMIS_MEMORY",
                "watchlist": "HOT_ACTIVE",
                "all_universes": False,
                "lookback_days": 60,
                "persist": True,
                "session_id": "session-1",
                "summary_limit": 5,
            }
            return {
                "agent_name": "lance_swing",
                "mode": "swing_cycle",
                "session_id": "session-1",
                "top_watchlist": [{"ticker": "MU", "state": "mean_reversion_watch"}],
            }

    out = tools.run_lance_swing_cycle(
        universe="AI_SEMIS_MEMORY",
        watchlist="HOT_ACTIVE",
        persist=True,
        session_id="session-1",
        summary_limit=5,
        service=FakeLanceSwingCycleService(),
    )

    assert out["agent_name"] == "lance_swing"
    assert out["mode"] == "swing_cycle"
    assert out["top_watchlist"][0]["ticker"] == "MU"


def test_run_lance_full_cycle_tool_with_injected_service():
    class FakeLanceFullCycleService:
        def run(self, **kwargs):
            assert kwargs == {
                "tickers": None,
                "universe": "AI_SEMIS_MEMORY",
                "watchlist": "HOT_ACTIVE",
                "all_universes": False,
                "market": None,
                "market_limit": None,
                "min_gap_abs": 2.5,
                "max_candidates": 7,
                "persist": True,
                "session_id": "2026-07-02-lance-intraday",
                "swing_session_id": "2026-07-02-lance-swing",
                "max_workers": 3,
                "include_caveated_context": None,
                "lookback_days": 80,
                "update_limit": 9,
                "review_limit": 11,
                "target_session_date": "2026-07-03",
                "summary_limit": 4,
            }
            return {
                "agent_name": "lance_full_cycle",
                "mode": "full_cycle",
                "status": "OK",
                "combined_watchlist": [{"ticker": "IBM", "lanes": ["intraday", "swing"]}],
            }

    out = tools.run_lance_full_cycle(
        universe="AI_SEMIS_MEMORY",
        watchlist="HOT_ACTIVE",
        min_gap_abs=2.5,
        max_candidates=7,
        persist=True,
        session_id="2026-07-02-lance-intraday",
        swing_session_id="2026-07-02-lance-swing",
        max_workers=3,
        lookback_days=80,
        update_limit=9,
        review_limit=11,
        target_session_date="2026-07-03",
        summary_limit=4,
        service=FakeLanceFullCycleService(),
    )

    assert out["agent_name"] == "lance_full_cycle"
    assert out["mode"] == "full_cycle"
    assert out["combined_watchlist"][0]["ticker"] == "IBM"


def test_run_sykes_live_tool_with_injected_service():
    class FakeSykesLiveService:
        def run(self, **kwargs):
            assert kwargs["market"] == "us-listed"
            assert kwargs["market_limit"] == 100
            assert kwargs["live_intraday"] is True
            return {"agent_name": "timothy_sykes", "mode": "live_and_swing"}

    out = tools.run_sykes_live(
        market="us-listed",
        market_limit=100,
        service=FakeSykesLiveService(),
    )

    assert out["agent_name"] == "timothy_sykes"
    assert out["mode"] == "live_and_swing"


def test_run_trading_desk_tool_with_injected_service():
    class FakeTradingDeskService:
        def run(self, **kwargs):
            assert kwargs["market"] == "us-listed"
            assert kwargs["market_limit"] == 100
            assert kwargs["max_workers"] == 5
            return {"agent_name": "trading_desk", "mode": "one_run"}

    out = tools.run_trading_desk(
        market="us-listed",
        market_limit=100,
        max_workers=5,
        service=FakeTradingDeskService(),
    )

    assert out["agent_name"] == "trading_desk"
    assert out["mode"] == "one_run"


def test_run_lance_full_cycle_tool_accepts_market_selector():
    class FakeLanceFullCycleService:
        def run(self, **kwargs):
            assert kwargs["market"] == "us-listed"
            assert kwargs["market_limit"] == 600
            assert kwargs["all_universes"] is False
            return {"mode": "full_cycle", "market": kwargs["market"]}

    out = tools.run_lance_full_cycle(
        market="us-listed",
        market_limit=600,
        service=FakeLanceFullCycleService(),
    )

    assert out["mode"] == "full_cycle"
    assert out["market"] == "us-listed"


def test_run_lance_full_cycle_tool_defaults_to_bounded_parallel_workers():
    class FakeLanceFullCycleService:
        def run(self, **kwargs):
            return {"max_workers": kwargs["max_workers"]}

    out = tools.run_lance_full_cycle(service=FakeLanceFullCycleService())

    assert out["max_workers"] == 6


def test_review_lance_full_cycle_tool_with_injected_service():
    class FakeFullCycleReviewService:
        def review(self, **kwargs):
            assert kwargs == {
                "intraday_session_id": "2026-07-02-lance-intraday",
                "swing_session_id": "2026-07-02-lance-swing",
                "limit": 25,
            }
            return {
                "agent_name": "lance_full_cycle",
                "mode": "full_cycle_review",
                "journal_queue": [{"lane": "intraday", "ticker": "IBM"}],
            }

    out = tools.review_lance_full_cycle(
        intraday_session_id="2026-07-02-lance-intraday",
        swing_session_id="2026-07-02-lance-swing",
        limit=25,
        service=FakeFullCycleReviewService(),
    )

    assert out["mode"] == "full_cycle_review"
    assert out["journal_queue"][0]["ticker"] == "IBM"


def test_journal_lance_full_cycle_outcome_tool_with_injected_service():
    class FakeFullCycleReviewService:
        def record_outcome(self, **kwargs):
            assert kwargs == {
                "lane": "swing",
                "session_id": "2026-07-02-lance-swing",
                "ticker": "MU",
                "playbook": "swing_mean_reversion_reclaim",
                "outcome": "chop",
                "notes": "Manual review.",
                "plan": {"ticker": "MU"},
            }
            return {
                "agent_name": "lance_full_cycle",
                "mode": "full_cycle_journal",
                "lane": "swing",
                "journal": {"recorded": {"ticker": "MU", "outcome": "chop"}},
            }

    out = tools.journal_lance_full_cycle_outcome(
        lane="swing",
        session_id="2026-07-02-lance-swing",
        ticker="MU",
        playbook="swing_mean_reversion_reclaim",
        outcome="chop",
        notes="Manual review.",
        plan={"ticker": "MU"},
        service=FakeFullCycleReviewService(),
    )

    assert out["mode"] == "full_cycle_journal"
    assert out["journal"]["recorded"]["outcome"] == "chop"


def test_get_lance_session_dashboard_tool_with_injected_service():
    class FakeDashboardService:
        def dashboard(self, **kwargs):
            assert kwargs == {
                "intraday_session_id": "2026-07-02-lance-intraday",
                "swing_session_id": "2026-07-02-lance-swing",
                "target_session_date": "2026-07-03",
                "limit": 25,
                "memory_limit": 50,
            }
            return {
                "agent_name": "lance_full_cycle",
                "mode": "session_dashboard",
                "status": "OK",
                "buckets": {"needs_manual_review": [{"ticker": "IBM"}]},
            }

    out = tools.get_lance_session_dashboard(
        intraday_session_id="2026-07-02-lance-intraday",
        swing_session_id="2026-07-02-lance-swing",
        target_session_date="2026-07-03",
        limit=25,
        memory_limit=50,
        service=FakeDashboardService(),
    )

    assert out["mode"] == "session_dashboard"
    assert out["buckets"]["needs_manual_review"][0]["ticker"] == "IBM"


def test_build_lance_tomorrow_prep_tool_with_injected_service():
    class FakeDashboardService:
        def tomorrow_prep(self, **kwargs):
            assert kwargs == {
                "intraday_session_id": "2026-07-02-lance-intraday",
                "swing_session_id": "2026-07-02-lance-swing",
                "target_session_date": "2026-07-03",
                "limit": 25,
                "memory_limit": 50,
            }
            return {
                "agent_name": "lance_full_cycle",
                "mode": "tomorrow_prep",
                "watchlist": [{"ticker": "MU"}],
            }

    out = tools.build_lance_tomorrow_prep(
        intraday_session_id="2026-07-02-lance-intraday",
        swing_session_id="2026-07-02-lance-swing",
        target_session_date="2026-07-03",
        limit=25,
        memory_limit=50,
        service=FakeDashboardService(),
    )

    assert out["mode"] == "tomorrow_prep"
    assert out["watchlist"][0]["ticker"] == "MU"


def test_build_lance_unified_plan_tool_with_injected_service():
    class FakeLanceUnifiedPlanService:
        def build(self, **kwargs):
            assert kwargs["tickers"] == ["IBM", "MRVL"]
            assert kwargs["lookback_days"] == 50
            return {
                "agent_name": "lance_unified",
                "plans": [{"ticker": "IBM", "action_mode": "watch"}],
            }

    out = tools.build_lance_unified_plan(
        tickers=["IBM", "MRVL"],
        lookback_days=50,
        service=FakeLanceUnifiedPlanService(),
    )

    assert out["agent_name"] == "lance_unified"
    assert out["plans"][0]["ticker"] == "IBM"
    assert out["plans"][0]["action_mode"] == "watch"


def test_build_lance_unified_plan_tool_requires_tickers():
    out = tools.build_lance_unified_plan(tickers=[])
    assert "error" in out


def test_run_lance_market_scan_tool_with_injected_service():
    class FakeLanceMarketScanService:
        def scan(self, **kwargs):
            assert kwargs["tickers"] == ["IBM", "MRVL"]
            assert kwargs["max_candidates"] == 2
            assert kwargs["persist"] is True
            return {
                "agent_name": "lance_intraday",
                "session_id": "session-1",
                "candidate_count": 1,
                "watchlist": [{"ticker": "IBM", "state": "setup_forming", "score": 90}],
            }

    out = tools.run_lance_market_scan(
        tickers=["IBM", "MRVL"],
        max_candidates=2,
        persist=True,
        service=FakeLanceMarketScanService(),
    )

    assert out["agent_name"] == "lance_intraday"
    assert out["session_id"] == "session-1"
    assert out["watchlist"][0]["ticker"] == "IBM"


def test_run_lance_market_scan_tool_accepts_market_selector():
    class FakeLanceMarketScanService:
        def scan(self, **kwargs):
            assert kwargs["market"] == "us-listed"
            assert kwargs["market_limit"] == 750
            assert kwargs["all_universes"] is False
            return {"agent_name": "lance_intraday", "selection": "us-listed"}

    out = tools.run_lance_market_scan(
        market="us-listed",
        market_limit=750,
        service=FakeLanceMarketScanService(),
    )

    assert out["agent_name"] == "lance_intraday"
    assert out["selection"] == "us-listed"


def test_update_lance_watchlist_tool_with_injected_service():
    class FakeLanceDeskUpdateService:
        def update(self, **kwargs):
            assert kwargs["session_id"] == "session-1"
            assert kwargs["limit"] == 3
            assert kwargs["persist"] is True
            return {
                "agent_name": "lance_intraday",
                "session_id": "session-1",
                "updated_count": 1,
                "updates": [{"ticker": "IBM", "current_state": "triggered_reference"}],
            }

    out = tools.update_lance_watchlist(
        session_id="session-1",
        limit=3,
        persist=True,
        service=FakeLanceDeskUpdateService(),
    )

    assert out["agent_name"] == "lance_intraday"
    assert out["updated_count"] == 1
    assert out["updates"][0]["ticker"] == "IBM"


def test_run_advanced_lance_scan_tool_with_injected_service():
    class FakeAdvancedLanceService:
        def scan(self, **kwargs):
            assert kwargs["universe"] == "AI_SEMIS_MEMORY"
            assert kwargs["max_candidates"] == 5
            return {
                "agent_name": "lance_intraday",
                "mode": "advanced",
                "watchlist": [{"ticker": "NVDA"}],
            }

    out = tools.run_advanced_lance_scan(
        universe="AI_SEMIS_MEMORY",
        max_candidates=5,
        service=FakeAdvancedLanceService(),
    )

    assert out["mode"] == "advanced"
    assert out["watchlist"][0]["ticker"] == "NVDA"


def test_run_advanced_lance_scan_tool_accepts_market_selector():
    class FakeAdvancedLanceService:
        def scan(self, **kwargs):
            assert kwargs["market"] == "us-listed"
            assert kwargs["market_limit"] == 500
            assert kwargs["all_universes"] is False
            return {"mode": "advanced", "selection": "us-listed"}

    out = tools.run_advanced_lance_scan(
        market="us-listed",
        market_limit=500,
        service=FakeAdvancedLanceService(),
    )

    assert out["mode"] == "advanced"
    assert out["selection"] == "us-listed"


def test_journal_lance_outcome_tool_with_injected_service():
    class FakeJournalService:
        def record(self, **kwargs):
            assert kwargs["ticker"] == "NVDA"
            assert kwargs["outcome"] == "worked"
            return {"status": "OK", "recorded": {"ticker": "NVDA", "outcome": "worked"}}

    out = tools.journal_lance_outcome(
        session_id="session-1",
        ticker="NVDA",
        playbook="earnings_continuation",
        outcome="worked",
        service=FakeJournalService(),
    )

    assert out["status"] == "OK"
    assert out["recorded"]["outcome"] == "worked"


def test_get_lance_session_timeline_tool_with_injected_service():
    class FakeTimelineService:
        def timeline(self, **kwargs):
            assert kwargs["session_id"] == "session-1"
            assert kwargs["ticker"] == "NVDA"
            assert kwargs["limit"] == 10
            return {
                "agent_name": "lance_intraday",
                "session_id": "session-1",
                "event_count": 2,
                "tickers": [{"ticker": "NVDA", "latest_state": "setup_forming"}],
            }

    out = tools.get_lance_session_timeline(
        session_id="session-1",
        ticker="NVDA",
        limit=10,
        service=FakeTimelineService(),
    )

    assert out["event_count"] == 2
    assert out["tickers"][0]["latest_state"] == "setup_forming"


def test_review_lance_session_tool_with_injected_service():
    class FakeReviewService:
        def review(self, **kwargs):
            assert kwargs["session_id"] == "session-1"
            assert kwargs["limit"] == 20
            return {
                "agent_name": "lance_intraday",
                "session_id": "session-1",
                "pending_count": 1,
                "pending_reviews": [{"ticker": "OPEN", "suggested_outcome": "unknown"}],
            }

    out = tools.review_lance_session(
        session_id="session-1",
        limit=20,
        service=FakeReviewService(),
    )

    assert out["pending_count"] == 1
    assert out["pending_reviews"][0]["ticker"] == "OPEN"


def test_build_lance_carryover_plan_tool_with_injected_service():
    class FakeCarryoverService:
        def build(self, **kwargs):
            assert kwargs["session_id"] == "session-1"
            assert kwargs["target_session_date"] == "2026-07-02"
            assert kwargs["limit"] == 20
            return {
                "agent_name": "lance_intraday",
                "source_session_id": "session-1",
                "target_session_date": "2026-07-02",
                "carryover_count": 1,
                "groups": {"strength_carryover": [{"ticker": "OPEN"}]},
            }

    out = tools.build_lance_carryover_plan(
        session_id="session-1",
        target_session_date="2026-07-02",
        limit=20,
        service=FakeCarryoverService(),
    )

    assert out["carryover_count"] == 1
    assert out["groups"]["strength_carryover"][0]["ticker"] == "OPEN"


def test_run_lance_desk_cycle_tool_with_injected_service():
    class FakeDeskCycleService:
        def run(self, **kwargs):
            assert kwargs["tickers"] == ["IBM", "MRVL"]
            assert kwargs["max_candidates"] == 2
            assert kwargs["target_session_date"] == "2026-07-02"
            return {
                "agent_name": "lance_intraday",
                "mode": "desk_cycle",
                "session_id": "session-1",
                "status": "OK",
                "scan_summary": {"candidate_count": 2},
            }

    out = tools.run_lance_desk_cycle(
        tickers=["IBM", "MRVL"],
        max_candidates=2,
        target_session_date="2026-07-02",
        service=FakeDeskCycleService(),
    )

    assert out["mode"] == "desk_cycle"
    assert out["session_id"] == "session-1"
    assert out["scan_summary"]["candidate_count"] == 2


def test_run_lance_desk_cycle_tool_accepts_market_selector():
    class FakeDeskCycleService:
        def run(self, **kwargs):
            assert kwargs["market"] == "us-listed"
            assert kwargs["market_limit"] == 500
            assert kwargs["all_universes"] is False
            return {"mode": "desk_cycle", "selection": "us-listed"}

    out = tools.run_lance_desk_cycle(
        market="us-listed",
        market_limit=500,
        service=FakeDeskCycleService(),
    )

    assert out["mode"] == "desk_cycle"
    assert out["selection"] == "us-listed"


def test_validate_live_market_readiness_tool_with_injected_service():
    class FakeValidationService:
        def run(self, **kwargs):
            assert kwargs["tickers"] == ["IBM", "MRVL"]
            assert kwargs["max_candidates"] == 2
            assert kwargs["now"] == "2026-07-01T18:31:00Z"
            return {
                "agent_name": "market_validation",
                "status": "ready",
                "ticker_count": 2,
            }

    out = tools.validate_live_market_readiness(
        tickers=["IBM", "MRVL"],
        max_candidates=2,
        now="2026-07-01T18:31:00Z",
        service=FakeValidationService(),
    )

    assert out["status"] == "ready"
    assert out["ticker_count"] == 2


def test_summarize_lance_memory_tool_with_injected_service():
    class FakeMemoryService:
        def summarize(self, **kwargs):
            assert kwargs["session_id"] == "session-1"
            assert kwargs["ticker"] == "MRVL"
            assert kwargs["limit"] == 25
            return {
                "agent_name": "lance_intraday",
                "strategy": "Lance market memory report",
                "status": "OK",
                "outcome_count": 2,
            }

    out = tools.summarize_lance_memory(
        session_id="session-1",
        ticker="MRVL",
        limit=25,
        service=FakeMemoryService(),
    )

    assert out["status"] == "OK"
    assert out["outcome_count"] == 2


def test_run_lance_replay_tool_with_injected_service():
    class FakeReplayService:
        def replay(self, **kwargs):
            assert kwargs["source_db_path"] == "data/market_data.sqlite"
            assert kwargs["scratch_db_path"] == "/tmp/lance_replay.sqlite"
            assert kwargs["scenario_name"] == "today_replay"
            assert kwargs["scenarios_path"] == "data/lance_replay_scenarios.yaml"
            assert kwargs["session_id"] == "session-1"
            assert kwargs["target_session_date"] == "2026-07-02"
            assert kwargs["outcomes"] == [{"ticker": "OPEN", "outcome": "worked"}]
            assert kwargs["limit"] == 20
            assert kwargs["check_assertions"] is True
            return {
                "agent_name": "lance_intraday",
                "mode": "replay",
                "status": "OK",
                "memory": {"outcome_count": 1},
                "assertions": {"status": "PASS"},
            }

    out = tools.run_lance_replay(
        source_db_path="data/market_data.sqlite",
        scratch_db_path="/tmp/lance_replay.sqlite",
        scenario_name="today_replay",
        scenarios_path="data/lance_replay_scenarios.yaml",
        session_id="session-1",
        target_session_date="2026-07-02",
        outcomes=[{"ticker": "OPEN", "outcome": "worked"}],
        limit=20,
        check_assertions=True,
        service=FakeReplayService(),
    )

    assert out["mode"] == "replay"
    assert out["memory"]["outcome_count"] == 1
    assert out["assertions"]["status"] == "PASS"


def test_run_lance_replay_suite_tool_with_injected_service():
    class FakeSuiteService:
        def run(self, **kwargs):
            assert kwargs["source_db_path"] == "data/market_data.sqlite"
            assert kwargs["scenarios_path"] == "data/lance_replay_scenarios.yaml"
            assert kwargs["scratch_dir"] == "/tmp/lance_suite"
            return {
                "agent_name": "lance_intraday",
                "mode": "replay_suite",
                "status": "PASS",
                "scenario_count": 2,
                "passed_count": 2,
                "failed_count": 0,
            }

    out = tools.run_lance_replay_suite(
        source_db_path="data/market_data.sqlite",
        scenarios_path="data/lance_replay_scenarios.yaml",
        scratch_dir="/tmp/lance_suite",
        service=FakeSuiteService(),
    )

    assert out["mode"] == "replay_suite"
    assert out["status"] == "PASS"
    assert out["scenario_count"] == 2


def test_run_lance_system_check_tool_with_injected_service():
    class FakeSystemCheckService:
        def run(self, **kwargs):
            assert kwargs["source_db_path"] == "data/market_data.sqlite"
            assert kwargs["scenarios_path"] == "data/lance_replay_scenarios.yaml"
            assert kwargs["scratch_dir"] == "/tmp/lance_system_check"
            return {
                "agent_name": "lance_intraday",
                "mode": "system_check",
                "status": "PASS",
                "summary": {
                    "suite_status": "PASS",
                    "suite_scenarios": 2,
                    "suite_passed": 2,
                    "suite_failed": 0,
                    "source_outcomes_before": 0,
                    "source_outcomes_after": 0,
                },
            }

    out = tools.run_lance_system_check(
        source_db_path="data/market_data.sqlite",
        scenarios_path="data/lance_replay_scenarios.yaml",
        scratch_dir="/tmp/lance_system_check",
        service=FakeSystemCheckService(),
    )

    assert out["mode"] == "system_check"
    assert out["status"] == "PASS"
    assert out["summary"]["suite_scenarios"] == 2


def test_track_lance_session_changes_tool_with_injected_service():
    class FakeTrackerService:
        def diff(self, **kwargs):
            assert kwargs["previous"]["session_ids"]["intraday"] == "prev-intraday"
            assert kwargs["current"]["session_ids"]["intraday"] == "current-intraday"
            return {
                "agent_name": "lance_full_cycle",
                "mode": "session_tracker",
                "status": "OK",
                "summary": {"new_count": 1},
                "groups": {"new": [{"ticker": "IBM"}]},
                "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
            }

    out = tools.track_lance_session_changes(
        previous={"session_ids": {"intraday": "prev-intraday"}},
        current={"session_ids": {"intraday": "current-intraday"}},
        service=FakeTrackerService(),
    )

    assert out["mode"] == "session_tracker"
    assert out["summary"]["new_count"] == 1
    assert out["groups"]["new"][0]["ticker"] == "IBM"


def test_run_lance_command_center_tool_with_injected_service():
    class FakeCommandCenterService:
        def run(self, **kwargs):
            assert kwargs["tickers"] == "IBM,MU"
            assert kwargs["previous"] == {"combined_watchlist": []}
            assert kwargs["persist"] is True
            assert kwargs["target_session_date"] == "2026-07-06"
            return {
                "agent_name": "lance_full_cycle",
                "mode": "command_center",
                "status": "OK",
                "single_run_read": {"one_liner": "1 active monitor."},
                "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
            }

    out = tools.run_lance_command_center(
        tickers="IBM,MU",
        previous={"combined_watchlist": []},
        persist=True,
        target_session_date="2026-07-06",
        service=FakeCommandCenterService(),
    )

    assert out["mode"] == "command_center"
    assert out["single_run_read"]["one_liner"] == "1 active monitor."


def test_run_lance_command_center_tool_accepts_market_selector():
    class FakeCommandCenterService:
        def run(self, **kwargs):
            assert kwargs["market"] == "us-listed"
            assert kwargs["market_limit"] == 500
            assert kwargs["all_universes"] is False
            return {
                "mode": "command_center",
                "workflow_commands": {"now": ".venv/bin/python -m cli.lance --market us-listed"},
            }

    out = tools.run_lance_command_center(
        market="us-listed",
        market_limit=500,
        service=FakeCommandCenterService(),
    )

    assert out["mode"] == "command_center"
    assert "--market us-listed" in out["workflow_commands"]["now"]


def test_explain_lance_ticker_tool_with_injected_service():
    class FakeTickerExplainService:
        def explain(self, **kwargs):
            assert kwargs["ticker"] == "IBM"
            assert kwargs["payload"] == {"mode": "command_center"}
            assert kwargs["payload_path"] == "data/live_sessions/latest_command_center.json"
            return {
                "agent_name": "lance_full_cycle",
                "mode": "ticker_explain",
                "ticker": "IBM",
                "status": "FOUND",
                "summary": "IBM is in Lance output.",
                "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
            }

    out = tools.explain_lance_ticker(
        ticker="IBM",
        payload={"mode": "command_center"},
        payload_path="data/live_sessions/latest_command_center.json",
        service=FakeTickerExplainService(),
    )

    assert out["mode"] == "ticker_explain"
    assert out["ticker"] == "IBM"
    assert out["status"] == "FOUND"


def test_run_lance_data_doctor_tool_with_injected_service():
    class FakeDataDoctorService:
        def diagnose(self, **kwargs):
            assert kwargs["tickers"] == "IBM,MU"
            assert kwargs["max_candidates"] == 2
            assert kwargs["now"] == "2026-07-03T14:00:00Z"
            return {
                "agent_name": "lance_data_doctor",
                "mode": "data_doctor",
                "status": "blocked",
                "doctor_read": {"one_liner": "1 ready, 1 blocked."},
                "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
            }

    out = tools.run_lance_data_doctor(
        tickers="IBM,MU",
        max_candidates=2,
        now="2026-07-03T14:00:00Z",
        service=FakeDataDoctorService(),
    )

    assert out["mode"] == "data_doctor"
    assert out["doctor_read"]["one_liner"] == "1 ready, 1 blocked."


def test_tool_definitions_are_well_formed():
    names = {t["name"] for t in definitions.TOOLS}
    assert names == {
        "scan_premarket",
        "scan_small_caps",
        "run_trading_desk",
        "run_sykes_live",
        "list_universes",
        "get_ticker_snapshot",
        "scan_breitstein_intraday",
        "build_lance_intraday_plan",
        "build_lance_swing_plan",
        "run_lance_swing_cycle",
        "run_lance_full_cycle",
        "track_lance_session_changes",
        "run_lance_command_center",
        "explain_lance_ticker",
        "run_lance_data_doctor",
        "review_lance_full_cycle",
        "journal_lance_full_cycle_outcome",
        "get_lance_session_dashboard",
        "build_lance_tomorrow_prep",
        "build_lance_unified_plan",
        "run_lance_market_scan",
        "update_lance_watchlist",
        "run_advanced_lance_scan",
        "journal_lance_outcome",
        "get_lance_session_timeline",
        "review_lance_session",
        "build_lance_carryover_plan",
        "run_lance_desk_cycle",
        "validate_live_market_readiness",
        "summarize_lance_memory",
        "run_lance_replay",
        "run_lance_replay_suite",
        "run_lance_system_check",
        "scan_temiz_first_red_day",
        "scan_grittani_morning_panic",
    }
    for tool in definitions.TOOLS:
        assert tool["description"]
        assert tool["input_schema"]["type"] == "object"
        assert "properties" in tool["input_schema"]

    small_cap_tool = next(tool for tool in definitions.TOOLS if tool["name"] == "scan_small_caps")
    assert "market" in small_cap_tool["input_schema"]["properties"]
    assert "market_limit" in small_cap_tool["input_schema"]["properties"]
    assert "max_workers" in small_cap_tool["input_schema"]["properties"]
    assert "include_rejected" in small_cap_tool["input_schema"]["properties"]

    replay_tool = next(tool for tool in definitions.TOOLS if tool["name"] == "run_lance_replay")
    replay_props = replay_tool["input_schema"]["properties"]
    assert "source_db_path" in replay_props
    assert "scratch_db_path" in replay_props
    assert "scenario_name" in replay_props
    assert "scenarios_path" in replay_props
    assert "check_assertions" in replay_props
    assert "outcomes" in replay_props

    replay_suite_tool = next(
        tool for tool in definitions.TOOLS if tool["name"] == "run_lance_replay_suite"
    )
    replay_suite_props = replay_suite_tool["input_schema"]["properties"]
    assert "source_db_path" in replay_suite_props
    assert "scenarios_path" in replay_suite_props
    assert "scratch_dir" in replay_suite_props

    system_check_tool = next(
        tool for tool in definitions.TOOLS if tool["name"] == "run_lance_system_check"
    )
    system_check_props = system_check_tool["input_schema"]["properties"]
    assert "source_db_path" in system_check_props
    assert "scenarios_path" in system_check_props
    assert "scratch_dir" in system_check_props


def test_scan_small_caps_tool_includes_session_banner_and_row_time_fields():
    from app.models import SmallCapCandidate, SmallCapScanOutput

    class FakeSmallCapService:
        def scan(self, **kwargs):
            assert kwargs["include_rejected"] is True
            return SmallCapScanOutput(
                preset="sykes_small_cap_v0",
                run_ids=["run-1"],
                candidate_count=2,
                candidates=[
                    SmallCapCandidate(
                        ticker="GOOD",
                        name="Good Inc.",
                        market_cap=25_000_000,
                        gap_pct=8.0,
                        gap_dollar=0.5,
                        gap_basis="premarket",
                        volume=2_000_000,
                        rel_volume=4.0,
                        confidence="OK",
                        score=88,
                        grade="A_WATCH",
                        timestamp="2026-06-29T13:00:00Z",  # 09:00 ET (PRE_MARKET)
                    ),
                    SmallCapCandidate(
                        ticker="STALE",
                        name="Stale Corp.",
                        market_cap=40_000_000,
                        gap_pct=4.0,
                        gap_dollar=0.3,
                        gap_basis="last_trade",
                        volume=1_500_000,
                        rel_volume=3.0,
                        confidence="STALE_DATA",
                        score=72,
                        grade="B_WATCH",
                        timestamp="2026-06-29T23:30:00Z",  # 19:30 ET (POST_MARKET)
                    ),
                ],
                notes=[],
                rejected=[
                    SmallCapCandidate(
                        ticker="REJ",
                        name="Reject Co.",
                        market_cap=80_000_000,
                        gap_pct=2.0,
                        gap_dollar=0.1,
                        gap_basis="premarket",
                        volume=300_000,
                        rel_volume=0.5,
                        confidence="CONFLICT",
                        score=0,
                        grade="REJECT",
                        timestamp="2026-06-29T12:00:00Z",
                        risk_notes=["Rejected because confidence is CONFLICT."],
                    ),
                ],
                rejected_count=1,
            )

    out = tools.scan_small_caps(
        tickers="GOOD,STALE,REJ",
        include_rejected=True,
        service=FakeSmallCapService(),
    )

    # Session banner derives from the most recent candidate timestamp.
    assert out["session_banner"].startswith("POST_MARKET, Jun 29 7:30 PM ET.")

    # Per-row time / session / caveat fields exist on every candidate.
    good = out["candidates"][0]
    assert good["timestamp"] == "2026-06-29T13:00:00Z"
    assert good["as_of_utc"] == "2026-06-29T13:00:00Z"
    assert good["as_of_et"] == "Jun 29 9:00 AM ET"
    assert good["session_mode"] == "PRE_MARKET"
    assert good["data_caveat"] is None  # clean premarket = no caveat

    stale = out["candidates"][1]
    assert stale["as_of_et"] == "Jun 29 7:30 PM ET"
    assert stale["session_mode"] == "POST_MARKET"
    assert stale["data_caveat"] is not None
    assert "POST_MARKET:" in stale["data_caveat"]
    assert "last_trade" in stale["data_caveat"]
    assert "STALE_DATA" in stale["data_caveat"]
    assert "Not a live premarket gap" in stale["data_caveat"]

    # Rejected rows + count are exposed only when opted in.
    assert out["rejected_count"] == 1
    assert len(out["rejected"]) == 1
    assert out["rejected"][0]["ticker"] == "REJ"
    assert out["rejected"][0]["grade"] == "REJECT"
    assert "Rejected because confidence is CONFLICT." in out["rejected"][0]["risk_notes"]
    assert out["rejected"][0]["session_mode"] == "PRE_MARKET"


def test_scan_small_caps_tool_hides_rejected_when_opt_out():
    from app.models import SmallCapCandidate, SmallCapScanOutput

    class FakeSmallCapService:
        def scan(self, **kwargs):
            assert kwargs.get("include_rejected") is False
            return SmallCapScanOutput(
                preset="sykes_small_cap_v0",
                run_ids=["run-1"],
                candidate_count=1,
                candidates=[
                    SmallCapCandidate(
                        ticker="GOOD",
                        name="Good Inc.",
                        market_cap=25_000_000,
                        gap_pct=8.0,
                        gap_dollar=0.5,
                        gap_basis="premarket",
                        volume=2_000_000,
                        rel_volume=4.0,
                        confidence="OK",
                        score=88,
                        grade="A_WATCH",
                        timestamp="2026-06-29T13:00:00Z",
                    ),
                ],
                notes=[],
                rejected=[
                    SmallCapCandidate(
                        ticker="REJ",
                        name="Reject Co.",
                        market_cap=80_000_000,
                        gap_pct=2.0,
                        gap_dollar=0.1,
                        gap_basis="premarket",
                        volume=300_000,
                        rel_volume=0.5,
                        confidence="CONFLICT",
                        score=0,
                        grade="REJECT",
                        timestamp="2026-06-29T13:00:00Z",
                    ),
                ],
                rejected_count=1,
            )

    out = tools.scan_small_caps(
        tickers="GOOD,REJ",
        service=FakeSmallCapService(),
    )

    assert "rejected" not in out
    assert "rejected_count" not in out
    assert out["session_banner"].startswith("PRE_MARKET, Jun 29 9:00 AM ET.")


def test_scan_small_caps_tool_emits_empty_state_when_no_candidates():
    from app.models import SmallCapScanOutput

    class FakeSmallCapService:
        def scan(self, **kwargs):
            return SmallCapScanOutput(
                preset="sykes_small_cap_v0",
                run_ids=[],
                candidate_count=0,
                candidates=[],
                notes=[],
                zero_result_reason="all_filtered",
                relax_suggestions=[
                    "Review rejected rows with include_rejected=True.",
                ],
            )

    out = tools.scan_small_caps(tickers="HOT", service=FakeSmallCapService())

    assert out["zero_result_reason"] == "all_filtered"
    assert any("include_rejected=True" in s for s in out["relax_suggestions"])
    # session_banner falls back to OFF_SESSION when no timestamps are present.
    assert out["session_banner"].startswith("OFF_SESSION")
