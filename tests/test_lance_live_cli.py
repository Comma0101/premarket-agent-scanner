from __future__ import annotations

from typer.testing import CliRunner


runner = CliRunner()


def _payload(summary: str = "1 active monitor, 0 swing watches, 1 blocked/data-caveat, 0 pending reviews.") -> dict:
    return {
        "agent_name": "lance_full_cycle",
        "mode": "command_center",
        "status": "OK",
        "session_ids": {
            "intraday": "2026-07-03-lance-intraday",
            "swing": "2026-07-03-lance-swing",
        },
        "session_banner": (
            "MARKET_CLOSED, Jul 3 10:00 AM ET. US equity market closed: "
            "Independence Day observed."
        ),
        "session_context": {
            "session_mode": "MARKET_CLOSED",
            "as_of_et": "Jul 3 10:00 AM ET",
            "trading_date": "2026-07-03",
            "is_market_open": False,
            "is_market_holiday": True,
            "market_closed_reason": "Independence Day observed",
        },
        "single_run_read": {
            "one_liner": summary,
            "active_monitor": ["IBM"],
            "swing_watch": [],
            "blocked_data_quality": ["MU"],
            "pending_review_count": 0,
        },
        "tracker": {
            "one_liner": "1 new, 0 upgraded, 0 downgraded, 0 unchanged, 0 removed, 1 data caveat.",
        },
        "data_doctor": {
            "doctor_read": {
                "one_liner": "1 ready, 1 blocked. Main blockers: provider_failure=1."
            },
            "root_causes": {
                "ready": ["IBM"],
                "provider_failure": ["MU"],
                "missing_price": ["MU"],
                "stale_or_off_session": [],
                "halted": [],
                "confidence": ["MU"],
                "unknown": [],
            },
            "next_actions": ["Check provider connectivity/credentials before trusting Lance output."],
        },
        "outcome_loop": {
            "pending_review_count": 0,
            "pending_review_tickers": [],
            "journal_commands": [],
            "review_command": ".venv/bin/python -m cli.lance_full_cycle_eod review --intraday-session-id 2026-07-03-lance-intraday --swing-session-id 2026-07-03-lance-swing",
            "journal_tool": "journal_lance_full_cycle_outcome",
        },
        "workflow_commands": {
            "now": ".venv/bin/python -m cli.lance --tickers IBM,MU",
            "watch": ".venv/bin/python -m cli.lance_full_cycle --tickers IBM,MU --watch 30",
            "tomorrow": ".venv/bin/python -m cli.lance_dashboard tomorrow --intraday-session-id 2026-07-03-lance-intraday --swing-session-id 2026-07-03-lance-swing",
        },
        "selection_audit": {
            "requested_tickers": ["IBM", "MU", "ARM"],
            "returned_tickers": ["IBM", "MU"],
            "omitted_tickers": [{"ticker": "ARM", "reason": "filtered out"}],
        },
        "full_cycle": {
            "market_context": {
                "benchmarks": {
                    "SPY": {
                        "gap_pct": 0.42,
                        "gap_basis": "premarket",
                        "confidence": "OK",
                        "as_of": "2026-07-03T13:30:00Z",
                        "sources": ["alpaca"],
                    }
                }
            },
            "combined_watchlist": [
                {
                    "ticker": "IBM",
                    "intraday_state": "active_monitor",
                    "swing_state": "watch",
                    "intraday_playbook": "mean_reversion",
                    "swing_playbook": "daily_context_watch",
                    "intraday_score": 72.5,
                    "swing_score": 61.0,
                    "data_quality": {
                        "latest_price": 189.25,
                        "gap_pct": 1.25,
                        "gap_basis": "premarket",
                        "confidence": "OK",
                        "data_status": "live",
                        "rel_volume": 2.1,
                        "volume": 1250000,
                        "as_of_et": "Jul 3 9:30 AM ET",
                        "sources": ["alpaca", "yfinance"],
                        "data_caveat": None,
                    },
                },
                {
                    "ticker": "MU",
                    "intraday_state": "blocked",
                    "swing_state": "blocked_data_quality",
                    "intraday_score": -110.0,
                    "swing_score": -100.0,
                    "data_quality": {
                        "latest_price": None,
                        "gap_pct": None,
                        "gap_basis": None,
                        "confidence": "ERROR",
                        "data_status": "provider_failure",
                        "rel_volume": None,
                        "volume": None,
                        "as_of_et": "Jul 3 9:31 AM ET",
                        "sources": [],
                        "data_caveat": "provider failure",
                    },
                },
            ],
        },
        "agent_handoff": {
            "summary": summary,
            "session_ids": {
                "intraday": "2026-07-03-lance-intraday",
                "swing": "2026-07-03-lance-swing",
            },
            "active_monitor": ["IBM"],
            "swing_watch": [],
            "blocked_data_quality": ["MU"],
            "data_doctor": "1 ready, 1 blocked. Main blockers: provider_failure=1.",
            "session_banner": (
                "MARKET_CLOSED, Jul 3 10:00 AM ET. US equity market closed: "
                "Independence Day observed."
            ),
            "selection_audit": {
                "requested_tickers": ["IBM", "MU", "ARM"],
                "returned_tickers": ["IBM", "MU"],
                "omitted_tickers": [{"ticker": "ARM", "reason": "filtered out"}],
            },
            "pending_review_tickers": [],
            "next_commands": {
                "now": ".venv/bin/python -m cli.lance --tickers IBM,MU",
                "watch": ".venv/bin/python -m cli.lance_full_cycle --tickers IBM,MU --watch 30",
            },
            "handoff_prompt": "Preserve data-quality caveats.",
        },
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def test_lance_live_prints_operator_console_and_writes_handoff(monkeypatch, tmp_path):
    from cli import lance_live

    calls: list[dict] = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return _payload()

    monkeypatch.setattr(lance_live, "run_lance_command_center", fake_run)

    result = runner.invoke(
        lance_live.app,
        [
            "--tickers",
            "IBM,MU",
            "--target-session-date",
            "2026-07-06",
            "--handoff-dir",
            str(tmp_path),
            "--no-persist",
        ],
    )

    assert result.exit_code == 0
    assert calls[0]["tickers"] == "IBM,MU"
    assert calls[0]["persist"] is False
    assert calls[0]["previous"] is None
    assert "Lance Live Operator" in result.stdout
    assert "Session" in result.stdout
    assert "MARKET_CLOSED, Jul 3 10:00 AM ET" in result.stdout
    assert "Independence Day observed" in result.stdout
    assert "Active Monitor: IBM" in result.stdout
    assert "Data Lance Used" in result.stdout
    assert "SPY: gap=0.42% basis=premarket confidence=OK" in result.stdout
    assert "IBM | intraday=active_monitor | swing=watch" in result.stdout
    assert "price=189.25 | gap=1.25% | rvol=2.10x" in result.stdout
    assert "sources=alpaca,yfinance" in result.stdout
    assert "MU | intraday=blocked | swing=blocked_data_quality" in result.stdout
    assert "status=provider_failure" in result.stdout
    assert "Requested Ticker Coverage" in result.stdout
    assert "requested=IBM, MU, ARM" in result.stdout
    assert "returned=IBM, MU" in result.stdout
    assert "omitted ARM: filtered out" in result.stdout
    assert "Blocked / Data Doctor" in result.stdout
    assert "provider_failure: MU" in result.stdout
    assert "Next Actions" in result.stdout
    assert "now=.venv/bin/python -m cli.lance --tickers IBM,MU" in result.stdout
    assert "watch=.venv/bin/python -m cli.lance_full_cycle --tickers IBM,MU --watch 30" in result.stdout
    assert "Agent Handoff" in result.stdout
    assert "Handoff written:" in result.stdout
    assert "JSON written:" in result.stdout

    handoff = tmp_path / "latest_agent_handoff.md"
    assert handoff.exists()
    content = handoff.read_text(encoding="utf-8")
    assert "# Lance Agent Handoff" in content
    assert "summary: 1 active monitor" in content
    assert "blocked_data_quality: MU" in content
    assert "## Data Lance Used" in content
    assert "IBM | intraday=active_monitor | swing=watch" in content
    assert "sources=alpaca,yfinance" in content
    assert "## Requested Ticker Coverage" in content
    assert "omitted ARM: filtered out" in content
    assert "## Data Doctor" in content
    assert "provider_failure: MU" in content
    assert "now: .venv/bin/python -m cli.lance --tickers IBM,MU" in content
    assert "## Agent Task Prompt" in content
    assert "latest_command_center.json" in content
    assert "Matches your filter - not buy/sell advice. Verify before acting." in content

    payload_json = tmp_path / "latest_command_center.json"
    assert payload_json.exists()
    parsed = payload_json.read_text(encoding="utf-8")
    assert '"mode": "command_center"' in parsed
    assert '"provider_failure"' in parsed


def test_lance_live_watch_carries_previous_payload(monkeypatch, tmp_path):
    from cli import lance_live

    payloads = [
        _payload("1 active monitor, 0 swing watches, 0 blocked/data-caveat names, 0 pending reviews."),
        _payload("0 active monitors, 0 swing watches, 1 blocked/data-caveat, 0 pending reviews."),
    ]
    calls: list[dict] = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return payloads.pop(0)

    monkeypatch.setattr(lance_live, "run_lance_command_center", fake_run)

    result = runner.invoke(
        lance_live.app,
        [
            "--tickers",
            "IBM",
            "--watch",
            "0",
            "--watch-iterations",
            "2",
            "--handoff-dir",
            str(tmp_path),
            "--no-persist",
        ],
    )

    assert result.exit_code == 0
    assert "Lance Live Watch: every 0 seconds" in result.stdout
    assert "Cycle 1" in result.stdout
    assert "Cycle 2" in result.stdout
    assert calls[0]["previous"] is None
    assert calls[1]["previous"]["mode"] == "command_center"
    assert (tmp_path / "latest_agent_handoff.md").exists()
    assert (tmp_path / "latest_command_center.json").exists()
