from __future__ import annotations

import json

from typer.testing import CliRunner


runner = CliRunner()


def _payload() -> dict:
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
            "one_liner": "1 active monitor, 1 swing watch, 1 blocked/data-caveat, 1 pending review.",
            "active_monitor": ["IBM"],
            "swing_watch": ["MU"],
            "blocked_data_quality": ["AAOI"],
            "pending_review_count": 1,
        },
        "tracker": {
            "one_liner": "1 new, 0 upgraded, 0 downgraded, 0 unchanged, 0 removed, 0 data caveats.",
            "groups": {"new": [{"ticker": "IBM"}]},
            "data_caveats": [],
        },
        "signal_quality": [
            {
                "ticker": "IBM",
                "posture": "active_monitor",
                "state": "triggered_reference",
                "rel_volume": 4.2,
                "confidence": "OK",
                "gap_basis": "premarket",
                "as_of_et": "Jul 3 9:45 AM ET",
                "quality_reason": "confidence=OK / gap_basis=premarket / as_of=Jul 3 9:45 AM ET",
            },
            {
                "ticker": "AAOI",
                "posture": "blocked_data_quality",
                "state": "blocked_data_quality",
                "rel_volume": None,
                "confidence": "STALE_DATA",
                "gap_basis": "last_trade",
                "as_of_et": "Jul 2 4:00 PM ET",
                "quality_reason": "confidence=STALE_DATA / gap_basis=last_trade / as_of=Jul 2 4:00 PM ET",
            },
        ],
        "data_doctor": {
            "doctor_read": {
                "one_liner": "1 ready, 1 blocked. Main blockers: stale_or_off_session=1."
            },
            "root_causes": {
                "ready": ["IBM"],
                "provider_failure": [],
                "missing_price": [],
                "stale_or_off_session": ["AAOI"],
                "halted": [],
                "confidence": ["AAOI"],
                "unknown": [],
            },
            "next_actions": ["Resolve stale/off-session data before treating rows as live."],
        },
        "tomorrow_prep": {
            "fresh_scan_required": True,
            "watchlist": ["IBM", "MU", "AAOI"],
        },
        "outcome_loop": {
            "pending_review_count": 1,
            "pending_review_tickers": ["IBM"],
            "journal_commands": [
                "journal_lance_full_cycle_outcome lane=intraday ticker=IBM playbook=mean_reversion_after_capitulation outcome=unknown"
            ],
            "review_command": ".venv/bin/python -m cli.lance_full_cycle_eod review --intraday-session-id 2026-07-03-lance-intraday --swing-session-id 2026-07-03-lance-swing",
            "journal_tool": "journal_lance_full_cycle_outcome",
            "journal_note": "Journal observed outcomes only after manual chart review.",
        },
        "workflow_commands": {
            "now": ".venv/bin/python -m cli.lance --tickers IBM,MU",
            "watch": ".venv/bin/python -m cli.lance_full_cycle --tickers IBM,MU --watch 30",
            "explain": ".venv/bin/python -m cli.lance_explain <TICKER> --payload data/live_sessions/latest_command_center.json",
            "tomorrow": ".venv/bin/python -m cli.lance_dashboard tomorrow --intraday-session-id 2026-07-03-lance-intraday --swing-session-id 2026-07-03-lance-swing",
        },
        "selection_audit": {
            "requested_tickers": ["IBM", "MU", "AAOI", "ARM"],
            "returned_tickers": ["IBM", "MU", "AAOI"],
            "omitted_tickers": [{"ticker": "ARM", "reason": "filtered out"}],
        },
        "data_used": {
            "summary": "2 candidate rows, 1 benchmark row.",
            "source_paths": [
                "full_cycle.market_context.benchmarks",
                "full_cycle.combined_watchlist",
            ],
            "benchmarks": [
                {
                    "ticker": "SPY",
                    "gap_pct": 0.42,
                    "gap_basis": "premarket",
                    "confidence": "OK",
                    "as_of": "2026-07-03T13:30:00Z",
                    "sources": ["alpaca"],
                }
            ],
            "candidate_rows": [
                {
                    "ticker": "IBM",
                    "intraday_state": "triggered_reference",
                    "swing_state": None,
                    "intraday_playbook": "mean_reversion_after_capitulation",
                    "swing_playbook": None,
                    "latest_price": 189.25,
                    "gap_pct": 1.25,
                    "gap_basis": "premarket",
                    "confidence": "OK",
                    "data_status": "live",
                    "rel_volume": 4.2,
                    "volume": 1250000,
                    "as_of": None,
                    "as_of_et": "Jul 3 9:45 AM ET",
                    "sources": ["alpaca", "yfinance"],
                    "data_caveat": None,
                },
                {
                    "ticker": "AAOI",
                    "intraday_state": "blocked_data_quality",
                    "swing_state": None,
                    "intraday_playbook": None,
                    "swing_playbook": None,
                    "latest_price": None,
                    "gap_pct": None,
                    "gap_basis": "last_trade",
                    "confidence": "STALE_DATA",
                    "data_status": "stale",
                    "rel_volume": None,
                    "volume": None,
                    "as_of": None,
                    "as_of_et": "Jul 2 4:00 PM ET",
                    "sources": [],
                    "data_caveat": "POST_MARKET: last_trade / STALE_DATA",
                },
            ],
        },
        "agent_handoff": {
            "summary": "1 active monitor, 1 swing watch, 1 blocked/data-caveat, 1 pending review.",
            "session_ids": {
                "intraday": "2026-07-03-lance-intraday",
                "swing": "2026-07-03-lance-swing",
            },
            "active_monitor": ["IBM"],
            "swing_watch": ["MU"],
            "blocked_data_quality": ["AAOI"],
            "data_doctor": "1 ready, 1 blocked. Main blockers: stale_or_off_session=1.",
            "data_used": {
                "summary": "2 candidate rows, 1 benchmark row.",
                "candidate_rows": [],
                "benchmarks": [],
                "source_paths": [],
            },
            "session_banner": (
                "MARKET_CLOSED, Jul 3 10:00 AM ET. US equity market closed: "
                "Independence Day observed."
            ),
            "selection_audit": {
                "requested_tickers": ["IBM", "MU", "AAOI", "ARM"],
                "returned_tickers": ["IBM", "MU", "AAOI"],
                "omitted_tickers": [{"ticker": "ARM", "reason": "filtered out"}],
            },
            "pending_review_tickers": ["IBM"],
            "next_commands": {
                "now": ".venv/bin/python -m cli.lance --tickers IBM,MU",
                "watch": ".venv/bin/python -m cli.lance_full_cycle --tickers IBM,MU --watch 30",
                "explain": ".venv/bin/python -m cli.lance_explain <TICKER> --payload data/live_sessions/latest_command_center.json",
            },
            "handoff_prompt": "Use this block to brief another agent.",
        },
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def test_lance_cli_prints_command_center(monkeypatch):
    from cli import lance

    def fake_run(**kwargs):
        assert kwargs["tickers"] == "IBM,MU"
        assert kwargs["target_session_date"] == "2026-07-06"
        assert kwargs["previous"] is None
        return _payload()

    monkeypatch.setattr(lance, "run_lance_command_center", fake_run)

    result = runner.invoke(
        lance.app,
        ["--tickers", "IBM,MU", "--target-session-date", "2026-07-06"],
    )

    assert result.exit_code == 0
    assert "Lance Command Center" in result.stdout
    assert "MARKET_CLOSED, Jul 3 10:00 AM ET" in result.stdout
    assert "Independence Day observed" in result.stdout
    assert "1 active monitor, 1 swing watch" in result.stdout
    assert "Active Monitor: IBM" in result.stdout
    assert "Swing Watch: MU" in result.stdout
    assert "Blocked/Data Caveat: AAOI" in result.stdout
    assert "Data Lance Used" in result.stdout
    assert "SPY: gap=0.42% basis=premarket confidence=OK" in result.stdout
    assert "IBM | intraday=triggered_reference | swing=unknown" in result.stdout
    assert "price=189.25 | gap=1.25% | rvol=4.20x" in result.stdout
    assert "sources=alpaca,yfinance" in result.stdout
    assert "AAOI | intraday=blocked_data_quality | swing=unknown" in result.stdout
    assert "status=stale" in result.stdout
    assert "Requested Ticker Coverage" in result.stdout
    assert "requested=IBM, MU, AAOI, ARM" in result.stdout
    assert "returned=IBM, MU, AAOI" in result.stdout
    assert "omitted ARM: filtered out" in result.stdout
    assert "Signal Quality" in result.stdout
    assert "IBM posture=active_monitor" in result.stdout
    assert "AAOI posture=blocked_data_quality" in result.stdout
    assert "Data Doctor" in result.stdout
    assert "1 ready, 1 blocked. Main blockers: stale_or_off_session=1." in result.stdout
    assert "stale_or_off_session: AAOI" in result.stdout
    assert "Outcome Loop" in result.stdout
    assert "pending_review_count=1" in result.stdout
    assert "journal_lance_full_cycle_outcome lane=intraday ticker=IBM" in result.stdout
    assert "Tomorrow Prep" in result.stdout
    assert "fresh_scan_required=True" in result.stdout
    assert "explain=.venv/bin/python -m cli.lance_explain <TICKER>" in result.stdout
    assert "Agent Handoff" in result.stdout
    assert "summary=1 active monitor, 1 swing watch" in result.stdout
    assert "blocked_data_quality=AAOI" in result.stdout
    assert "Matches your filter - not buy/sell advice" in result.stdout


def test_lance_cli_json_prints_raw_payload(monkeypatch):
    from cli import lance

    monkeypatch.setattr(lance, "run_lance_command_center", lambda **kwargs: _payload())

    result = runner.invoke(lance.app, ["--tickers", "IBM", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["mode"] == "command_center"


def test_lance_cli_watch_runs_command_center_with_previous_payload(monkeypatch):
    from cli import lance

    payloads = [_payload(), {**_payload(), "tracker": {"one_liner": "0 new, 1 upgraded."}}]
    calls: list[dict] = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return payloads.pop(0)

    monkeypatch.setattr(lance, "run_lance_command_center", fake_run)

    result = runner.invoke(
        lance.app,
        ["--tickers", "IBM", "--watch", "0", "--watch-iterations", "2"],
    )

    assert result.exit_code == 0
    assert "Lance Command Center Watch: every 0 seconds" in result.stdout
    assert "Watch Cycle 1" in result.stdout
    assert "Watch Cycle 2" in result.stdout
    assert calls[0]["previous"] is None
    assert calls[1]["previous"]["mode"] == "command_center"
