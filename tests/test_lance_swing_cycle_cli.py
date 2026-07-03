from __future__ import annotations

import json

from typer.testing import CliRunner


runner = CliRunner()


def _payload() -> dict:
    return {
        "agent_name": "lance_swing",
        "mode": "swing_cycle",
        "strategy": "Lance swing desk cycle",
        "session_id": "2026-07-02-lance-swing",
        "status": "OK",
        "selection": "AI_SEMIS_MEMORY,WATCHLIST:HOT_ACTIVE",
        "selection_count": 2,
        "summary": {
            "plan_count": 2,
            "active_watch_count": 1,
            "mean_reversion_watch_count": 1,
            "watching_count": 0,
            "invalidated_count": 0,
            "blocked_count": 0,
        },
        "top_watchlist": [
            {
                "ticker": "HOOD",
                "state": "active_watch",
                "lance_quality_grade": "ACTIVE_DAILY_WATCH",
                "playbook": "relative_strength_continuation",
                "score": 90,
                "data_quality": {
                    "gap_pct": 3.2,
                    "rel_volume": 1.1,
                    "confidence": "OK",
                    "gap_basis": "last_trade",
                    "as_of_et": "Jul 2 3:31 PM ET",
                    "sources": ["fake"],
                },
                "relative_strength": {"classification": "strong", "vs_QQQ": 12.3},
                "daily_context": {"trend": "uptrend", "structure": "uptrend_needs_base"},
                "waiting_for": ["daily close confirmation"],
                "invalidates_if": ["daily close loses support"],
            },
            {
                "ticker": "MU",
                "state": "mean_reversion_watch",
                "lance_quality_grade": "REVERSION_WATCH",
                "playbook": "swing_mean_reversion_reclaim",
                "score": 55,
                "data_quality": {
                    "gap_pct": -7.1,
                    "rel_volume": 1.2,
                    "confidence": "OK",
                    "gap_basis": "last_trade",
                    "as_of_et": "Jul 2 3:31 PM ET",
                    "sources": ["fake"],
                },
                "relative_strength": {"classification": "in_line", "vs_QQQ": -1.2},
                "daily_context": {"trend": "mixed", "structure": "mixed_range"},
                "waiting_for": ["prior-day low reclaim"],
                "invalidates_if": ["daily close remains below prior-day low"],
            },
        ],
        "groups": {"mean_reversion_watch": [{"ticker": "MU"}]},
        "notes": [],
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def test_lance_swing_cycle_cli_prints_readable_payload(monkeypatch):
    from cli import lance_swing_cycle

    def fake_run_lance_swing_cycle(**kwargs):
        assert kwargs["universe"] == "AI_SEMIS_MEMORY"
        assert kwargs["watchlist"] == "HOT_ACTIVE"
        assert kwargs["persist"] is True
        assert kwargs["summary_limit"] == 3
        return _payload()

    monkeypatch.setattr(lance_swing_cycle, "run_lance_swing_cycle", fake_run_lance_swing_cycle)

    result = runner.invoke(
        lance_swing_cycle.app,
        [
            "--universe",
            "AI_SEMIS_MEMORY",
            "--watchlist",
            "HOT_ACTIVE",
            "--persist",
            "--summary-limit",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert "Lance Swing Cycle" in result.stdout
    assert "selection=AI_SEMIS_MEMORY,WATCHLIST:HOT_ACTIVE" in result.stdout
    assert "HOOD state=active_watch" in result.stdout
    assert "MU state=mean_reversion_watch" in result.stdout
    assert "Matches your filter - not buy/sell advice" in result.stdout


def test_lance_swing_cycle_cli_json_returns_raw_payload(monkeypatch):
    from cli import lance_swing_cycle

    def fake_run_lance_swing_cycle(**kwargs):
        assert kwargs["tickers"] == "MU,HOOD"
        assert kwargs["all_universes"] is False
        return _payload()

    monkeypatch.setattr(lance_swing_cycle, "run_lance_swing_cycle", fake_run_lance_swing_cycle)

    result = runner.invoke(lance_swing_cycle.app, ["--tickers", "MU,HOOD", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["agent_name"] == "lance_swing"
    assert payload["top_watchlist"][1]["ticker"] == "MU"


def test_lance_swing_cycle_cli_defaults_to_all_universes(monkeypatch):
    from cli import lance_swing_cycle

    def fake_run_lance_swing_cycle(**kwargs):
        assert kwargs["tickers"] is None
        assert kwargs["universe"] is None
        assert kwargs["watchlist"] is None
        assert kwargs["all_universes"] is True
        return _payload()

    monkeypatch.setattr(lance_swing_cycle, "run_lance_swing_cycle", fake_run_lance_swing_cycle)

    result = runner.invoke(lance_swing_cycle.app, [])

    assert result.exit_code == 0
