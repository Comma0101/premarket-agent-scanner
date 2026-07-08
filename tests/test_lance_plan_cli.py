from __future__ import annotations

import json

from typer.testing import CliRunner


runner = CliRunner()


def _payload() -> dict:
    return {
        "agent_name": "lance_unified",
        "strategy": "Lance daily/swing context plus intraday timing",
        "timeframe": "daily_plus_intraday",
        "ticker_count": 1,
        "plan_count": 1,
        "plans": [
            {
                "ticker": "IBM",
                "action_mode": "watch",
                "alignment": "aligned",
                "primary_timeframe": "daily_then_intraday",
                "rank_score": 94.0,
                "thesis": "Daily idea is valid; intraday timing is still forming.",
                "swing": {
                    "state": "active_watch",
                    "lance_quality_grade": "ACTIVE_DAILY_WATCH",
                    "playbook": "relative_strength_continuation",
                    "data_quality": {"confidence": "OK", "gap_basis": "last_trade"},
                },
                "intraday": {
                    "state": "waiting_for_turn",
                    "lance_quality_grade": "B_WATCH",
                    "playbook": "mean_reversion_after_capitulation",
                    "data_quality": {"confidence": "OK", "gap_basis": "last_trade"},
                },
                "outcome_memory": {
                    "status": "OK",
                    "outcome_count": 3,
                    "matching_action_mode": {
                        "action_mode": "watch",
                        "total": 2,
                        "worked_rate": 0.5,
                    },
                    "matching_alignment": {
                        "alignment": "aligned",
                        "total": 2,
                        "worked_rate": 0.5,
                    },
                    "note": "Journaled outcomes only; not P&L, prediction, or trade advice.",
                },
                "waiting_for": [
                    "daily close confirmation above prior-day high",
                    "prior 2-minute bar high break",
                ],
                "invalidates_if": [
                    "daily close loses prior-day low",
                    "prior 2-minute low/high reference fails",
                ],
                "conflict_flags": [],
            }
        ],
        "groups": {
            "active_watch": [],
            "watch": [{"ticker": "IBM"}],
            "carry": [],
            "wait": [],
            "review": [],
            "ignore": [],
            "blocked": [],
        },
        "disclaimer": "Unified Lance plans are not buy/sell advice. They combine daily/swing context with intraday timing references from the data layer; verify before acting.",
    }


def test_lance_plan_cli_prints_readable_unified_payload(monkeypatch):
    from cli import lance_plan

    def fake_build_lance_unified_plan(**kwargs):
        assert kwargs["tickers"] == "IBM"
        assert kwargs["lookback_days"] == 50
        return _payload()

    monkeypatch.setattr(lance_plan, "build_lance_unified_plan", fake_build_lance_unified_plan)

    result = runner.invoke(lance_plan.app, ["--tickers", "IBM", "--lookback-days", "50"])

    assert result.exit_code == 0
    assert "Lance Unified Plan" in result.stdout
    assert "Agent: lance_unified" in result.stdout
    assert "IBM action=watch alignment=aligned" in result.stdout
    assert "swing=active_watch" in result.stdout
    assert "intraday=waiting_for_turn" in result.stdout
    assert "memory: status=OK outcome_count=3 action_mode_total=2 action_mode_worked_rate=0.50 alignment_total=2 alignment_worked_rate=0.50" in result.stdout
    assert "Unified Lance plans are not buy/sell advice" in result.stdout


def test_lance_plan_cli_json_returns_raw_payload(monkeypatch):
    from cli import lance_plan

    def fake_build_lance_unified_plan(**kwargs):
        assert kwargs["tickers"] == "IBM,MRVL"
        return _payload()

    monkeypatch.setattr(lance_plan, "build_lance_unified_plan", fake_build_lance_unified_plan)

    result = runner.invoke(lance_plan.app, ["--tickers", "IBM,MRVL", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["agent_name"] == "lance_unified"
    assert payload["plans"][0]["action_mode"] == "watch"
