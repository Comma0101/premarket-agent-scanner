from __future__ import annotations

import json

from typer.testing import CliRunner


runner = CliRunner()


def _payload() -> dict:
    return {
        "agent_name": "lance_swing",
        "strategy": "Lance Breitstein daily/swing planning",
        "timeframe": "daily_swing",
        "ticker_count": 1,
        "plan_count": 1,
        "plans": [
            {
                "ticker": "IBM",
                "state": "active_watch",
                "lance_quality_grade": "ACTIVE_DAILY_WATCH",
                "playbook": "relative_strength_continuation",
                "score": 95.0,
                "state_reason": "Daily trend and relative strength are aligned.",
                "daily_context": {
                    "trend": "uptrend",
                    "structure": "constructive_near_highs",
                    "return_20d_pct": 12.5,
                    "prior_day_levels": {"high": 201.0, "low": 195.0, "close": 200.0},
                },
                "relative_strength": {
                    "classification": "strong",
                    "vs_QQQ": 6.0,
                    "vs_SPY": 7.0,
                },
                "data_quality": {
                    "confidence": "OK",
                    "gap_basis": "last_trade",
                    "as_of_et": "Jul 1 4:00 PM ET",
                    "data_status": "stale",
                },
                "waiting_for": ["daily close confirmation above prior-day high or recent range high"],
                "invalidates_if": ["daily close loses prior-day low reference 195.0"],
            }
        ],
        "groups": {
            "active_watch": [{"ticker": "IBM"}],
            "confirmation_needed": [],
            "watching": [],
            "not_in_play": [],
            "invalidated": [],
            "blocked": [],
        },
        "disclaimer": "Swing plans are not buy/sell advice. They are daily-chart watch references from the data layer; verify before acting.",
    }


def test_lance_swing_plan_cli_prints_readable_payload(monkeypatch):
    from cli import lance_swing_plan

    def fake_build_lance_swing_plan(**kwargs):
        assert kwargs["tickers"] == "IBM"
        assert kwargs["lookback_days"] == 40
        return _payload()

    monkeypatch.setattr(lance_swing_plan, "build_lance_swing_plan", fake_build_lance_swing_plan)

    result = runner.invoke(
        lance_swing_plan.app,
        ["--tickers", "IBM", "--lookback-days", "40"],
    )

    assert result.exit_code == 0
    assert "Lance Swing Plan" in result.stdout
    assert "Agent: lance_swing" in result.stdout
    assert "IBM state=active_watch grade=ACTIVE_DAILY_WATCH" in result.stdout
    assert "trend=uptrend" in result.stdout
    assert "rs=strong" in result.stdout
    assert "Swing plans are not buy/sell advice" in result.stdout


def test_lance_swing_plan_cli_json_returns_raw_payload(monkeypatch):
    from cli import lance_swing_plan

    def fake_build_lance_swing_plan(**kwargs):
        assert kwargs["tickers"] == "IBM,MRVL"
        return _payload()

    monkeypatch.setattr(lance_swing_plan, "build_lance_swing_plan", fake_build_lance_swing_plan)

    result = runner.invoke(lance_swing_plan.app, ["--tickers", "IBM,MRVL", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["agent_name"] == "lance_swing"
    assert payload["plans"][0]["ticker"] == "IBM"


def test_lance_swing_plan_cli_accepts_universe_and_watchlist(monkeypatch):
    from cli import lance_swing_plan

    def fake_build_lance_swing_plan(**kwargs):
        assert kwargs["tickers"] is None
        assert kwargs["universe"] == "AI_SEMIS_MEMORY"
        assert kwargs["watchlist"] == "HOT_ACTIVE"
        assert kwargs["all_universes"] is False
        return _payload()

    monkeypatch.setattr(lance_swing_plan, "build_lance_swing_plan", fake_build_lance_swing_plan)

    result = runner.invoke(
        lance_swing_plan.app,
        ["--universe", "AI_SEMIS_MEMORY", "--watchlist", "HOT_ACTIVE"],
    )

    assert result.exit_code == 0
    assert "Lance Swing Plan" in result.stdout


def test_lance_swing_plan_cli_defaults_to_all_universes(monkeypatch):
    from cli import lance_swing_plan

    def fake_build_lance_swing_plan(**kwargs):
        assert kwargs["tickers"] is None
        assert kwargs["universe"] is None
        assert kwargs["watchlist"] is None
        assert kwargs["all_universes"] is True
        return _payload()

    monkeypatch.setattr(lance_swing_plan, "build_lance_swing_plan", fake_build_lance_swing_plan)

    result = runner.invoke(lance_swing_plan.app, [])

    assert result.exit_code == 0
    assert "Lance Swing Plan" in result.stdout
