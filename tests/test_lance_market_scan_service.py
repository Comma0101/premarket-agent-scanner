from __future__ import annotations

from app.db import get_lance_watchlist_events, get_lance_watchlist_items, initialize_database
from app.models import ScannerResult, ScanRunOutput
from services.lance_market_scan_service import LanceMarketScanService


class FakeScannerService:
    def __init__(self, results: list[ScannerResult]) -> None:
        self.results = results
        self.calls: list[dict] = []

    def scan(self, **kwargs):
        self.calls.append(kwargs)
        return ScanRunOutput(
            run_id="scan-1",
            universe="test-selection",
            started_at="2026-07-01T14:00:00Z",
            completed_at="2026-07-01T14:01:00Z",
            status="OK",
            results=self.results,
            notes=["fake scan"],
        )


class FakePlanService:
    def __init__(self, plans: dict[str, dict]) -> None:
        self.plans = plans
        self.calls: list[str] = []

    def build_plan(self, ticker: str) -> dict:
        self.calls.append(ticker)
        return self.plans[ticker]


class FakeMarketUniverse:
    def __init__(self, symbols: list[str]) -> None:
        self.name = "us-listed"
        self.symbols = symbols
        self.source = "fake_market"
        self.notes = ["fake market universe note"]


class FakeMarketUniverseProvider:
    def __init__(self, symbols: list[str]) -> None:
        self.symbols = symbols
        self.calls: list[str] = []

    def list_symbols(self, market: str) -> FakeMarketUniverse:
        self.calls.append(market)
        return FakeMarketUniverse(self.symbols)


def _result(
    ticker: str,
    *,
    gap_pct: float,
    rel_volume: float,
    confidence: str = "OK",
) -> ScannerResult:
    return ScannerResult(
        ticker=ticker,
        name=f"{ticker} Inc.",
        universe="test",
        market_cap=25_000_000_000,
        previous_close=100,
        premarket_price=None,
        latest_price=100 + gap_pct,
        gap_pct=gap_pct,
        gap_dollar=gap_pct,
        gap_basis="last_trade",
        volume=1_000_000,
        rel_volume=rel_volume,
        confidence=confidence,
        notes=None,
        sources=["fake"],
        timestamp="2026-07-01T14:00:00Z",
    )


def _plan(
    ticker: str,
    *,
    state: str,
    gap_pct: float,
    rel_volume: float,
    confidence: str = "OK",
    prior_break: str = "WAITING",
    volume_2x: str = "WAITING",
    pressure: str = "WAITING",
    chop: str = "PASS",
) -> dict:
    return {
        "ticker": ticker,
        "trader": "lance_breitstein",
        "setup_name": "mean_reversion_after_capitulation",
        "state": state,
        "data_quality": {
            "confidence": confidence,
            "gap_basis": "last_trade",
            "as_of": "2026-07-01T14:00:00Z",
            "as_of_et": "Jul 1 10:00 AM ET",
            "session_mode": "MARKET_OPEN",
            "data_caveat": "MARKET_OPEN: last_trade regular-session quote.",
            "latest_price": 100 + gap_pct,
            "previous_close": 100,
            "gap_pct": gap_pct,
            "gap_dollar": gap_pct,
            "volume": 1_000_000,
            "rel_volume": rel_volume,
            "market_cap": 25_000_000_000,
            "sources": ["fake"],
        },
        "conditions": {
            "data_quality": {"status": "PASS"},
            "abnormal_move": {"status": "PASS" if abs(gap_pct) >= 3 else "FAIL"},
            "participation": {"status": "PASS" if rel_volume >= 3 else "FAIL"},
            "prior_bar_break": {"status": prior_break},
            "volume_2x": {"status": volume_2x},
            "consecutive_pressure": {"status": pressure},
            "chop_filter": {"status": chop},
        },
        "trigger_reference": (
            {"direction": "long", "price": 101.25, "source": "prior_2min_bar_high_break"}
            if prior_break == "PASS"
            else None
        ),
        "risk_reference": {"price": 98.75, "source": "prior_2min_bar_low"},
        "target_reference": {"price": 103.5, "source": "20_period_ma"},
        "missing_fields": [],
        "state_reason": f"{ticker} policy reason.",
        "front_side_status": "right_side_confirmed" if prior_break == "PASS" else "front_side_active",
        "lance_quality_grade": (
            "REJECT"
            if state == "blocked_data_quality"
            else ("A_WATCH" if prior_break == "PASS" else "B_WATCH")
        ),
        "waiting_for": [] if prior_break == "PASS" else ["prior 2-minute bar break"],
        "invalidates_if": ["prior 2-minute low/high reference fails"],
        "manual_review_questions": ["Did the setup work, fail, chop, or reverse?"],
        "next_step": "Monitor Lance plan.",
        "disclaimer": "Reference levels are not buy/sell advice.",
    }


def test_lance_market_scan_ranks_triggered_high_participation_candidates_first():
    scanner = FakeScannerService(
        [
            _result("SLOW", gap_pct=2.0, rel_volume=0.7),
            _result("FAST", gap_pct=7.0, rel_volume=4.5),
            _result("FORM", gap_pct=-5.0, rel_volume=3.2),
        ]
    )
    plans = {
        "SLOW": _plan("SLOW", state="not_in_play", gap_pct=2.0, rel_volume=0.7),
        "FAST": _plan(
            "FAST",
            state="triggered_reference",
            gap_pct=7.0,
            rel_volume=4.5,
            prior_break="PASS",
            volume_2x="PASS",
            pressure="PASS",
        ),
        "FORM": _plan(
            "FORM",
            state="setup_forming",
            gap_pct=-5.0,
            rel_volume=3.2,
            volume_2x="PASS",
            pressure="PASS",
        ),
    }

    output = LanceMarketScanService(
        scanner_service=scanner,
        plan_service=FakePlanService(plans),
    ).scan(tickers=["SLOW", "FAST", "FORM"], max_candidates=3)

    assert output["agent_name"] == "lance_intraday"
    assert output["scanned_count"] == 3
    assert output["candidate_count"] == 3
    assert [row["ticker"] for row in output["watchlist"]] == ["FAST", "FORM", "SLOW"]
    assert output["watchlist"][0]["state"] == "triggered_reference"
    assert output["watchlist"][0]["score"] > output["watchlist"][1]["score"]
    assert output["watchlist"][0]["playbook"] == "mean_reversion_after_capitulation"
    assert output["watchlist"][0]["lance_quality_grade"] == "A_WATCH"
    assert output["watchlist"][0]["front_side_status"] == "right_side_confirmed"
    assert output["watchlist"][1]["front_side_status"] == "front_side_active"
    assert output["watchlist"][1]["waiting_for"] == ["prior 2-minute bar break"]
    assert output["watchlist"][0]["invalidates_if"] == ["prior 2-minute low/high reference fails"]
    assert output["watchlist"][0]["state_reason"] == "FAST policy reason."
    assert output["watchlist"][0]["manual_review_questions"] == [
        "Did the setup work, fail, chop, or reverse?"
    ]
    assert "7.0%" in output["watchlist"][0]["why_watching"]
    assert "4.5x session-volume RVOL" in output["watchlist"][0]["why_watching"]
    assert scanner.calls[0]["tickers"] == ["SLOW", "FAST", "FORM"]
    assert scanner.calls[0]["filters"].include_low_confidence is False
    assert output["triage_context"] == {
        "include_caveated_context": False,
        "filter_confidence": "OK_ONLY",
        "caveat": None,
    }


def test_lance_market_scan_resolves_full_market_before_intraday_triage():
    scanner = FakeScannerService([
        _result("IBM", gap_pct=4.0, rel_volume=3.1),
        _result("DELL", gap_pct=-5.0, rel_volume=3.8),
    ])
    market_provider = FakeMarketUniverseProvider(["IBM", "DELL", "MRVL"])
    plans = {
        "IBM": _plan("IBM", state="setup_forming", gap_pct=4.0, rel_volume=3.1),
        "DELL": _plan("DELL", state="triggered_reference", gap_pct=-5.0, rel_volume=3.8),
    }

    output = LanceMarketScanService(
        scanner_service=scanner,
        plan_service=FakePlanService(plans),
        market_universe_provider=market_provider,
    ).scan(market="us-listed", market_limit=2, max_candidates=2)

    assert market_provider.calls == ["us-listed"]
    assert scanner.calls[0]["tickers"] == ["IBM", "DELL"]
    assert scanner.calls[0]["universe"] is None
    assert scanner.calls[0]["watchlist"] is None
    assert scanner.calls[0]["all_universes"] is False
    assert output["watchlist"][0]["ticker"] == "DELL"
    assert output["notes"][:3] == [
        "Market universe us-listed resolved 3 symbol(s) from fake_market.",
        "Limited market universe to 2 symbol(s) for testing.",
        "fake market universe note",
    ]


def test_lance_market_scan_does_not_treat_market_symbols_as_manual_fallbacks():
    scanner = FakeScannerService([_result("DELL", gap_pct=-5.0, rel_volume=3.8)])
    market_provider = FakeMarketUniverseProvider(["IBM", "DELL", "MRVL"])
    plan_service = FakePlanService({
        "IBM": _plan("IBM", state="not_in_play", gap_pct=0.5, rel_volume=0.7),
        "DELL": _plan("DELL", state="setup_forming", gap_pct=-5.0, rel_volume=3.8),
        "MRVL": _plan("MRVL", state="not_in_play", gap_pct=0.2, rel_volume=0.8),
    })

    output = LanceMarketScanService(
        scanner_service=scanner,
        plan_service=plan_service,
        market_universe_provider=market_provider,
    ).scan(market="us-listed", max_candidates=3)

    assert scanner.calls[0]["tickers"] == ["IBM", "DELL", "MRVL"]
    assert plan_service.calls == ["DELL"]
    assert output["candidate_count"] == 1
    assert [row["ticker"] for row in output["watchlist"]] == ["DELL"]


def test_lance_market_scan_session_id_uses_new_york_date_from_scan_start():
    scanner = FakeScannerService([_result("FAST", gap_pct=7.0, rel_volume=4.5)])
    scanner_started_at = "2026-07-04T00:07:00Z"  # Jul 3 8:07 PM ET.
    original_scan = scanner.scan

    def fake_scan(**kwargs):
        output = original_scan(**kwargs)
        output.started_at = scanner_started_at
        return output

    scanner.scan = fake_scan
    output = LanceMarketScanService(
        scanner_service=scanner,
        plan_service=FakePlanService({
            "FAST": _plan("FAST", state="triggered_reference", gap_pct=7.0, rel_volume=4.5)
        }),
    ).scan(tickers=["FAST"], max_candidates=1)

    assert output["session_id"] == "2026-07-03-lance-intraday"


def test_lance_market_scan_can_include_caveated_context_without_upgrading_quality():
    scanner = FakeScannerService([_result("STALE", gap_pct=6.0, rel_volume=4.0, confidence="STALE_DATA")])
    plans = {
        "STALE": _plan(
            "STALE",
            state="blocked_data_quality",
            gap_pct=6.0,
            rel_volume=4.0,
            confidence="STALE_DATA",
        )
    }

    output = LanceMarketScanService(
        scanner_service=scanner,
        plan_service=FakePlanService(plans),
    ).scan(tickers=["STALE"], max_candidates=1, include_caveated_context=True)

    assert scanner.calls[0]["filters"].include_low_confidence is True
    assert output["triage_context"] == {
        "include_caveated_context": True,
        "filter_confidence": "ALLOW_CAVEATED_CONTEXT",
        "caveat": (
            "Caveated context may include STALE_DATA, CONFLICT, or LOW_CONFIDENCE rows; "
            "Lance data gates still block them from A_WATCH/live execution context."
        ),
    }
    assert output["watchlist"][0]["ticker"] == "STALE"
    assert output["watchlist"][0]["state"] == "blocked_data_quality"
    assert output["watchlist"][0]["lance_quality_grade"] == "REJECT"
    assert output["watchlist"][0]["data_quality"]["confidence"] == "STALE_DATA"


def test_lance_market_scan_can_persist_session_watchlist(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    scanner = FakeScannerService([_result("FAST", gap_pct=7.0, rel_volume=4.5)])
    plans = {
        "FAST": _plan(
            "FAST",
            state="triggered_reference",
            gap_pct=7.0,
            rel_volume=4.5,
            prior_break="PASS",
            volume_2x="PASS",
        )
    }

    output = LanceMarketScanService(
        scanner_service=scanner,
        plan_service=FakePlanService(plans),
        db_path=db_path,
    ).scan(
        tickers=["FAST"],
        max_candidates=1,
        persist=True,
        session_id="2026-07-01-market-open",
    )

    rows = get_lance_watchlist_items(db_path, session_id="2026-07-01-market-open")
    events = get_lance_watchlist_events(db_path, session_id="2026-07-01-market-open")

    assert output["session_id"] == "2026-07-01-market-open"
    assert len(rows) == 1
    assert rows[0]["ticker"] == "FAST"
    assert rows[0]["state"] == "triggered_reference"
    assert rows[0]["score"] == output["watchlist"][0]["score"]
    assert rows[0]["playbook"] == "mean_reversion_after_capitulation"
    assert rows[0]["data_quality"]["confidence"] == "OK"
    assert rows[0]["plan"]["ticker"] == "FAST"
    assert len(events) == 1
    assert events[0]["event_type"] == "scan"
    assert events[0]["ticker"] == "FAST"
    assert events[0]["payload"]["why_watching"] == output["watchlist"][0]["why_watching"]


def test_lance_market_scan_builds_plans_for_explicit_tickers_even_when_scan_filter_returns_none():
    scanner = FakeScannerService([])
    plans = {
        "IBM": _plan("IBM", state="not_in_play", gap_pct=0.5, rel_volume=0.7),
        "MRVL": _plan("MRVL", state="not_in_play", gap_pct=-0.8, rel_volume=0.9),
    }

    output = LanceMarketScanService(
        scanner_service=scanner,
        plan_service=FakePlanService(plans),
    ).scan(tickers="IBM,MRVL", max_candidates=2)

    assert scanner.calls[0]["tickers"] == "IBM,MRVL"
    assert output["scanned_count"] == 0
    assert output["candidate_count"] == 2
    assert [row["ticker"] for row in output["watchlist"]] == ["MRVL", "IBM"]
    assert all(row["state"] == "not_in_play" for row in output["watchlist"])
    assert all(row["data_quality"]["confidence"] == "OK" for row in output["watchlist"])


def test_lance_market_scan_caps_expensive_plan_builds_to_max_candidates():
    tickers = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    scanner = FakeScannerService([
        _result(ticker, gap_pct=float(index + 3), rel_volume=1.5)
        for index, ticker in enumerate(tickers)
    ])
    plan_service = FakePlanService({
        ticker: _plan(ticker, state="not_in_play", gap_pct=float(index + 3), rel_volume=1.5)
        for index, ticker in enumerate(tickers)
    })

    output = LanceMarketScanService(
        scanner_service=scanner,
        plan_service=plan_service,
    ).scan(tickers=tickers, max_candidates=2)

    assert plan_service.calls == ["AAA", "BBB"]
    assert output["candidate_count"] == 2
    assert len(output["watchlist"]) == 2
