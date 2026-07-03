from __future__ import annotations

import json

from typer.testing import CliRunner


runner = CliRunner()


def _payload() -> dict:
    return {
        "agent_name": "market_validation",
        "status": "ready",
        "session_mode": "MARKET_OPEN",
        "session_time_et": "Jul 1 2:31 PM ET",
        "ticker_count": 1,
        "ready_count": 1,
        "blocked_count": 0,
        "snapshot_checks": [
            {
                "ticker": "IBM",
                "readiness": "ready",
                "gap_pct": 1.8,
                "gap_basis": "last_trade",
                "confidence": "OK",
                "data_status": "live",
                "sources": ["fake"],
                "as_of_et": "Jul 1 2:30 PM ET",
                "blockers": [],
            }
        ],
        "lance_cycle": {"status": "OK", "scan_summary": {"candidate_count": 1}},
        "notes": [],
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def test_validate_live_market_readiness_cli_json(monkeypatch):
    from cli import validate_live_market_readiness

    calls: list[dict] = []

    def fake_validate(**kwargs):
        calls.append(kwargs)
        return _payload()

    monkeypatch.setattr(validate_live_market_readiness, "validate_live_market_readiness", fake_validate)

    result = runner.invoke(
        validate_live_market_readiness.app,
        ["--tickers", "IBM,MRVL", "--max-candidates", "2", "--json"],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == _payload()
    assert calls == [{
        "tickers": "IBM,MRVL",
        "max_candidates": 2,
        "persist": False,
        "summary_limit": 5,
        "review_limit": 10,
        "max_workers": 1,
        "now": None,
    }]


def test_validate_live_market_readiness_cli_readable(monkeypatch):
    from cli import validate_live_market_readiness

    monkeypatch.setattr(
        validate_live_market_readiness,
        "validate_live_market_readiness",
        lambda **kwargs: _payload(),
    )

    result = runner.invoke(validate_live_market_readiness.app, ["--tickers", "IBM"])

    assert result.exit_code == 0
    output = result.stdout
    assert "Live Market Readiness" in output
    assert "Status: ready" in output
    assert "Session: MARKET_OPEN, Jul 1 2:31 PM ET" in output
    assert "IBM readiness=ready gap_pct=1.8% source=fake as_of=Jul 1 2:30 PM ET gap_basis=last_trade confidence=OK data_status=live" in output
    assert "Matches your filter - not buy/sell advice. Verify before acting." in output
