from __future__ import annotations

from services.live_market_validation_service import LiveMarketValidationService


class FakeSnapshotTool:
    def __init__(self, rows: dict[str, dict]) -> None:
        self.rows = rows
        self.calls: list[str] = []

    def __call__(self, *, ticker: str) -> dict:
        self.calls.append(ticker)
        return self.rows[ticker]


class FakeLanceCycleTool:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def __call__(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        return self.payload


def _snapshot(
    ticker: str,
    *,
    confidence: str = "OK",
    data_status: str = "live",
    gap_basis: str | None = "last_trade",
    timestamp: str = "2026-07-01T18:30:00Z",
    provider_failures: dict | None = None,
) -> dict:
    return {
        "ticker": ticker,
        "previous_close": 100.0,
        "latest_price": 103.0,
        "premarket_price": None,
        "gap_pct": 3.0,
        "gap_dollar": 3.0,
        "gap_basis": gap_basis,
        "confidence": confidence,
        "data_status": data_status,
        "provider_failures": provider_failures or {},
        "sources": ["fake"],
        "timestamp": timestamp,
    }


def test_live_market_validation_reports_ready_market_open_rows():
    snapshots = FakeSnapshotTool({
        "IBM": _snapshot("IBM"),
        "MRVL": _snapshot("MRVL"),
    })
    lance_cycle = FakeLanceCycleTool({
        "status": "OK",
        "session_id": "session-1",
        "scan_summary": {"candidate_count": 2},
        "top_watchlist": [
            {
                "ticker": "IBM",
                "state": "setup_forming",
                "data_quality": {
                    "confidence": "OK",
                    "data_status": "live",
                    "gap_basis": "last_trade",
                },
            }
        ],
    })

    output = LiveMarketValidationService(
        snapshot_tool=snapshots,
        lance_cycle_tool=lance_cycle,
    ).run(tickers="IBM,MRVL", max_candidates=2, now="2026-07-01T18:31:00Z")

    assert output["status"] == "ready"
    assert output["session_mode"] == "MARKET_OPEN"
    assert output["ticker_count"] == 2
    assert output["ready_count"] == 2
    assert output["blocked_count"] == 0
    assert output["snapshot_checks"][0]["ticker"] == "IBM"
    assert output["snapshot_checks"][0]["readiness"] == "ready"
    assert output["lance_cycle"]["status"] == "OK"
    assert lance_cycle.calls == [{
        "tickers": ["IBM", "MRVL"],
        "max_candidates": 2,
        "persist": False,
        "summary_limit": 2,
        "review_limit": 10,
        "max_workers": 1,
    }]


def test_live_market_validation_blocks_provider_failures_and_stale_rows():
    snapshots = FakeSnapshotTool({
        "IBM": _snapshot("IBM", data_status="stale", confidence="STALE_DATA"),
        "MRVL": _snapshot(
            "MRVL",
            data_status="provider_failure",
            confidence="ERROR",
            gap_basis=None,
            provider_failures={"yfinance": "DNS failure"},
        ),
    })
    lance_cycle = FakeLanceCycleTool({"status": "OK", "top_watchlist": []})

    output = LiveMarketValidationService(
        snapshot_tool=snapshots,
        lance_cycle_tool=lance_cycle,
    ).run(tickers=["IBM", "MRVL"], now="2026-07-01T18:31:00Z")

    assert output["status"] == "blocked"
    assert output["ready_count"] == 0
    assert output["blocked_count"] == 2
    assert output["snapshot_checks"][0]["readiness"] == "blocked"
    assert "data_status=stale" in output["snapshot_checks"][0]["blockers"]
    assert "provider_failures present" in output["snapshot_checks"][1]["blockers"]


def test_live_market_validation_blocks_halted_snapshot():
    snapshots = FakeSnapshotTool({
        "ABCD": {
            **_snapshot("ABCD", gap_basis="premarket"),
            "premarket_price": 105.0,
            "halt_status": {
                "ticker": "ABCD",
                "status": "HALTED",
                "reason_code": "LUDP",
            },
        }
    })
    lance_cycle = FakeLanceCycleTool({"status": "OK", "top_watchlist": []})

    output = LiveMarketValidationService(
        snapshot_tool=snapshots,
        lance_cycle_tool=lance_cycle,
    ).run(tickers="ABCD", now="2026-07-01T18:31:00Z")

    assert output["status"] == "blocked"
    assert output["blocked_count"] == 1
    assert output["snapshot_checks"][0]["halt_status"]["status"] == "HALTED"
    assert "halt_status=HALTED" in output["snapshot_checks"][0]["blockers"]


def test_live_market_validation_watch_only_when_off_session_but_data_resolves():
    snapshots = FakeSnapshotTool({"IBM": _snapshot("IBM", timestamp="2026-07-01T20:00:00Z")})
    lance_cycle = FakeLanceCycleTool({"status": "OK", "top_watchlist": []})

    output = LiveMarketValidationService(
        snapshot_tool=snapshots,
        lance_cycle_tool=lance_cycle,
    ).run(tickers="IBM", now="2026-07-02T00:40:00Z")

    assert output["status"] == "watch_only"
    assert output["session_mode"] == "OFF_SESSION"
    assert output["ready_count"] == 1
    assert output["notes"] == ["Market is not open; this validates plumbing, not live readiness."]


def test_live_market_validation_uses_current_time_when_now_is_omitted():
    snapshots = FakeSnapshotTool({"IBM": _snapshot("IBM")})
    lance_cycle = FakeLanceCycleTool({"status": "OK", "top_watchlist": []})

    output = LiveMarketValidationService(
        snapshot_tool=snapshots,
        lance_cycle_tool=lance_cycle,
    ).run(tickers="IBM")

    assert output["session_time_et"] is not None
    assert output["session_time_et"] != "unknown"
