from __future__ import annotations

import json

from typer.testing import CliRunner


runner = CliRunner()


def _payload() -> dict:
    return {
        "agent_name": "lance_full_cycle",
        "mode": "full_cycle",
        "status": "OK",
        "session_ids": {
            "intraday": "2026-07-02-lance-intraday",
            "swing": "2026-07-02-lance-swing",
        },
        "session_workflow": {
            "persisted": True,
            "full_universe": True,
            "include_caveated_context": True,
            "intraday_session_id": "2026-07-02-lance-intraday",
            "swing_session_id": "2026-07-02-lance-swing",
            "review_tool": "review_lance_full_cycle",
            "journal_tool": "journal_lance_full_cycle_outcome",
            "triage_mode": "full_universe_intraday_first",
            "swing_scope": "intraday_triage",
            "swing_scope_count": 2,
            "triage_note": "Swing scope came from the intraday triage shortlist.",
            "review_command": ".venv/bin/python -m cli.lance_full_cycle_eod review --intraday-session-id 2026-07-02-lance-intraday --swing-session-id 2026-07-02-lance-swing",
            "journal_note": "Journal observed outcomes only after manual chart review; use unknown when not reviewed.",
        },
        "summary": {
            "intraday_candidate_count": 2,
            "intraday_update_count": 2,
            "intraday_pending_review_count": 1,
            "swing_plan_count": 3,
            "swing_active_watch_count": 1,
            "swing_mean_reversion_watch_count": 1,
            "swing_carryover_count": 1,
            "combined_ticker_count": 2,
        },
        "desk_read": {
            "one_liner": (
                "1 intraday focus, 0 swing watch, 1 blocked/data-caveat, "
                "1 swing carryover."
            ),
            "intraday_focus": [{"ticker": "IBM", "intraday_state": "triggered_reference"}],
            "swing_watch": [],
            "blocked_data_quality": [{"ticker": "MU", "swing_state": "mean_reversion_watch"}],
            "swing_carryover": [
                {
                    "ticker": "MU",
                    "bucket": "swing_mean_reversion_carryover",
                    "playbook": "swing_mean_reversion_reclaim",
                }
            ],
            "workflow_notes": [
                "Use intraday focus rows for live desk monitoring only when data quality stays OK.",
                "Swing watches still require their waiting_for conditions before upgrading.",
                "Carryover rows require a fresh scan before next-session decisions.",
            ],
        },
        "combined_watchlist": [
            {
                "ticker": "IBM",
                "lanes": ["intraday", "swing"],
                "intraday_state": "triggered_reference",
                "swing_state": "active_watch",
                "data_quality": {
                    "confidence": "OK",
                    "gap_basis": "last_trade",
                    "as_of_et": "Jul 2 3:45 PM ET",
                },
            },
            {
                "ticker": "MU",
                "lanes": ["swing"],
                "swing_state": "mean_reversion_watch",
                "data_quality": {
                    "confidence": "STALE_DATA",
                    "gap_basis": "last_trade",
                    "as_of_et": "Jul 2 4:00 PM ET",
                },
            },
        ],
        "top_intraday_watchlist": [{"ticker": "IBM", "state": "triggered_reference"}],
        "top_swing_watchlist": [{"ticker": "MU", "state": "mean_reversion_watch"}],
        "swing_carryover_summary": {
            "status": "OK",
            "carryover_count": 1,
            "fresh_scan_required": True,
        },
        "swing_carryover_groups": {
            "swing_mean_reversion_carryover": [{"ticker": "MU"}],
            "swing_continuation_carryover": [],
            "strength_carryover": [],
            "weakness_carryover": [],
            "context_only": [],
        },
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def test_lance_full_cycle_cli_prints_readable_payload(monkeypatch):
    from cli import lance_full_cycle

    def fake_run_lance_full_cycle(**kwargs):
        assert kwargs["universe"] == "AI_SEMIS_MEMORY"
        assert kwargs["watchlist"] == "HOT_ACTIVE"
        assert kwargs["persist"] is True
        assert kwargs["swing_session_id"] == "2026-07-02-lance-swing"
        assert kwargs["summary_limit"] == 3
        return _payload()

    monkeypatch.setattr(lance_full_cycle, "run_lance_full_cycle", fake_run_lance_full_cycle)

    result = runner.invoke(
        lance_full_cycle.app,
        [
            "--universe",
            "AI_SEMIS_MEMORY",
            "--watchlist",
            "HOT_ACTIVE",
            "--persist",
            "--swing-session-id",
            "2026-07-02-lance-swing",
            "--summary-limit",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert "Lance Full Cycle" in result.stdout
    assert "intraday=2026-07-02-lance-intraday" in result.stdout
    assert "swing=2026-07-02-lance-swing" in result.stdout
    assert "Desk Read" in result.stdout
    assert "Session Workflow" in result.stdout
    assert "review_lance_full_cycle" in result.stdout
    assert "include_caveated_context=True" in result.stdout
    assert "triage_mode=full_universe_intraday_first" in result.stdout
    assert "swing_scope=intraday_triage" in result.stdout
    assert "swing_scope_count=2" in result.stdout
    assert "triage_note=Swing scope came from the intraday triage shortlist." in result.stdout
    assert "1 intraday focus, 0 swing watch, 1 blocked/data-caveat" in result.stdout
    assert "intraday_focus: IBM" in result.stdout
    assert "blocked_data_quality: MU" in result.stdout
    assert "IBM lanes=intraday,swing" in result.stdout
    assert "MU lanes=swing" in result.stdout
    assert "Swing Carryover" in result.stdout
    assert "swing_mean_reversion_carryover: MU" in result.stdout
    assert "Matches your filter - not buy/sell advice" in result.stdout


def test_lance_full_cycle_cli_json_returns_raw_payload(monkeypatch):
    from cli import lance_full_cycle

    def fake_run_lance_full_cycle(**kwargs):
        assert kwargs["tickers"] == "IBM,MU"
        assert kwargs["all_universes"] is False
        return _payload()

    monkeypatch.setattr(lance_full_cycle, "run_lance_full_cycle", fake_run_lance_full_cycle)

    result = runner.invoke(lance_full_cycle.app, ["--tickers", "IBM,MU", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["agent_name"] == "lance_full_cycle"
    assert payload["combined_watchlist"][0]["ticker"] == "IBM"


def test_lance_full_cycle_cli_defaults_to_all_universes(monkeypatch):
    from cli import lance_full_cycle

    def fake_run_lance_full_cycle(**kwargs):
        assert kwargs["tickers"] is None
        assert kwargs["universe"] is None
        assert kwargs["watchlist"] is None
        assert kwargs["all_universes"] is True
        assert kwargs["max_workers"] == 6
        assert kwargs["include_caveated_context"] is True
        return _payload()

    monkeypatch.setattr(lance_full_cycle, "run_lance_full_cycle", fake_run_lance_full_cycle)

    result = runner.invoke(lance_full_cycle.app, [])

    assert result.exit_code == 0


def test_lance_full_cycle_cli_full_universe_alias(monkeypatch):
    from cli import lance_full_cycle

    def fake_run_lance_full_cycle(**kwargs):
        assert kwargs["all_universes"] is True
        assert kwargs["include_caveated_context"] is True
        return _payload()

    monkeypatch.setattr(lance_full_cycle, "run_lance_full_cycle", fake_run_lance_full_cycle)

    result = runner.invoke(lance_full_cycle.app, ["--full-universe"])

    assert result.exit_code == 0


def test_lance_full_cycle_cli_watch_prints_tracker_changes(monkeypatch):
    from cli import lance_full_cycle

    payloads = [
        {
            **_payload(),
            "session_ids": {"intraday": "cycle-1-intraday", "swing": "cycle-1-swing"},
            "combined_watchlist": [
                {
                    "ticker": "IBM",
                    "lanes": ["intraday"],
                    "intraday_state": "watching",
                    "intraday_score": 45,
                    "data_quality": {
                        "confidence": "OK",
                        "gap_basis": "premarket",
                        "as_of_et": "Jul 2 10:00 AM ET",
                    },
                }
            ],
        },
        {
            **_payload(),
            "session_ids": {"intraday": "cycle-2-intraday", "swing": "cycle-2-swing"},
            "combined_watchlist": [
                {
                    "ticker": "IBM",
                    "lanes": ["intraday"],
                    "intraday_state": "triggered_reference",
                    "intraday_score": 75,
                    "data_quality": {
                        "confidence": "OK",
                        "gap_basis": "premarket",
                        "as_of_et": "Jul 2 10:04 AM ET",
                    },
                },
                {
                    "ticker": "MU",
                    "lanes": ["swing"],
                    "swing_state": "blocked_data_quality",
                    "swing_score": 20,
                    "data_quality": {
                        "confidence": "STALE_DATA",
                        "gap_basis": "last_trade",
                        "as_of_et": "Jul 2 4:00 PM ET",
                    },
                },
            ],
        },
    ]

    def fake_run_lance_full_cycle(**kwargs):
        assert kwargs["summary_limit"] == 2
        return payloads.pop(0)

    monkeypatch.setattr(lance_full_cycle, "run_lance_full_cycle", fake_run_lance_full_cycle)

    result = runner.invoke(
        lance_full_cycle.app,
        ["--tickers", "IBM,MU", "--watch", "0", "--watch-iterations", "2", "--summary-limit", "2"],
    )

    assert result.exit_code == 0
    assert "Full-Cycle Watch Mode: every 0 seconds" in result.stdout
    assert "Watch Cycle 1" in result.stdout
    assert "Watch Cycle 2" in result.stdout
    assert "Lance Session Tracker" in result.stdout
    assert "1 new, 1 upgraded, 0 downgraded" in result.stdout
    assert "upgraded:" in result.stdout
    assert "IBM previous_state=watching current_state=triggered_reference" in result.stdout
    assert "new:" in result.stdout
    assert "MU state=blocked_data_quality" in result.stdout
    assert "Data Caveats" in result.stdout
    assert "MU: confidence=STALE_DATA / gap_basis=last_trade as of Jul 2 4:00 PM ET." in result.stdout
