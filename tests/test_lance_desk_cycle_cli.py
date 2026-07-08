from __future__ import annotations

import json

from typer.testing import CliRunner


runner = CliRunner()


def _payload() -> dict:
    return {
        "agent_name": "lance_intraday",
        "mode": "desk_cycle",
        "strategy": "Advanced Lance desk cycle",
        "status": "OK",
        "session_id": "session-1",
        "scan_summary": {
            "status": "OK",
            "scanned_count": 3,
            "candidate_count": 2,
            "returned_watchlist_count": 2,
        },
        "updates_summary": {
            "status": "OK",
            "tracked_count": 2,
            "updated_count": 2,
            "state_changed_count": 1,
        },
        "review_summary": {"status": "OK", "pending_count": 1, "reviewed_count": 0},
        "carryover_summary": {
            "status": "OK",
            "carryover_count": 1,
            "fresh_scan_required": True,
        },
        "market_context": {
            "theme_rotation": [
                {"theme": "AI_SEMIS_MEMORY", "tickers": ["MRVL"], "evidence": "tool-provided"}
            ]
        },
        "top_watchlist": [
            {
                "ticker": "MRVL",
                "state": "setup_forming",
                "score": 82,
                "gap_pct": 4.2,
                "gap_dollar": 3.1,
                "source": "fake-provider",
                "as_of": "2026-07-01T13:31:00Z",
                "gap_basis": "premarket",
                "confidence": "OK",
                "evidence": ["panic move"],
            },
            {"ticker": "IBM", "state": "manual_review"},
        ],
        "top_updates": [
            {
                "ticker": "MRVL",
                "previous_state": "setup_forming",
                "current_state": "triggered_reference",
                "state_changed": True,
            }
        ],
        "pending_reviews": [{"ticker": "IBM", "suggested_outcome": "unknown"}],
        "carryover_groups": {"fresh_confirm": [{"ticker": "MRVL", "reason": "fresh scan required"}]},
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def _watch_payload(iteration: int) -> dict:
    payload = _payload()
    payload["session_id"] = "watch-session"
    payload["top_updates"] = [
        {
            "ticker": "MRVL",
            "previous_state": "setup_forming" if iteration == 1 else "triggered_reference",
            "current_state": "triggered_reference" if iteration == 1 else "not_in_play",
            "state_changed": True,
            "score_delta": 18 if iteration == 1 else -25,
            "gap_pct_delta": 2.1 if iteration == 1 else -1.4,
            "rel_volume_delta": 1.2 if iteration == 1 else -1.1,
            "change_flags": ["state_changed", "rvol_expanded"] if iteration == 1 else ["score_deteriorated", "rvol_faded"],
            "data_quality": {
                "as_of_et": f"Jul 1 11:3{iteration} AM ET",
                "gap_basis": "last_trade",
                "confidence": "OK",
                "data_status": "live",
                "sources": ["fake"],
            },
        }
    ]
    return payload


def test_json_output_returns_raw_run_lance_desk_cycle_payload(monkeypatch):
    from cli import lance_desk_cycle

    calls: list[dict] = []

    def fake_run_lance_desk_cycle(**kwargs):
        calls.append(kwargs)
        return _payload()

    monkeypatch.setattr(lance_desk_cycle, "run_lance_desk_cycle", fake_run_lance_desk_cycle)

    result = runner.invoke(
        lance_desk_cycle.app,
        ["--watchlist", "hot_active", "--json"],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == _payload()
    assert calls == [{
        "tickers": None,
        "universe": None,
        "watchlist": "hot_active",
        "all_universes": False,
        "market": None,
        "market_limit": None,
        "min_gap_abs": 3.0,
        "max_candidates": 20,
        "persist": False,
        "session_id": None,
        "max_workers": 1,
        "include_caveated_context": False,
        "update_limit": 50,
        "review_limit": 500,
        "target_session_date": None,
        "summary_limit": 5,
    }]


def test_no_selection_defaults_to_all_universes(monkeypatch):
    from cli import lance_desk_cycle

    calls: list[dict] = []

    def fake_run_lance_desk_cycle(**kwargs):
        calls.append(kwargs)
        return _payload()

    monkeypatch.setattr(lance_desk_cycle, "run_lance_desk_cycle", fake_run_lance_desk_cycle)

    result = runner.invoke(lance_desk_cycle.app, ["--max-candidates", "5"])

    assert result.exit_code == 0
    assert calls[0]["all_universes"] is True
    assert calls[0]["max_candidates"] == 5
    assert calls[0]["include_caveated_context"] is True


def test_market_selector_does_not_default_to_all_universes(monkeypatch):
    from cli import lance_desk_cycle

    calls: list[dict] = []

    def fake_run_lance_desk_cycle(**kwargs):
        calls.append(kwargs)
        return _payload()

    monkeypatch.setattr(lance_desk_cycle, "run_lance_desk_cycle", fake_run_lance_desk_cycle)

    result = runner.invoke(
        lance_desk_cycle.app,
        ["--market", "us-listed", "--market-limit", "500", "--json"],
    )

    assert result.exit_code == 0
    assert calls[0]["market"] == "us-listed"
    assert calls[0]["market_limit"] == 500
    assert calls[0]["all_universes"] is False
    assert calls[0]["include_caveated_context"] is True


def test_readable_output_groups_sections_and_preserves_market_provenance(monkeypatch):
    from cli import lance_desk_cycle

    def fake_run_lance_desk_cycle(**kwargs):
        return _payload()

    monkeypatch.setattr(lance_desk_cycle, "run_lance_desk_cycle", fake_run_lance_desk_cycle)

    result = runner.invoke(
        lance_desk_cycle.app,
        ["--tickers", "IBM,MRVL,HOOD", "--max-candidates", "5"],
    )

    assert result.exit_code == 0
    output = result.stdout
    assert "Session and Status" in output
    assert "Market Context / Theme Rotation" in output
    assert "Top Lance Watchlist Rows" in output
    assert "What Changed Since The Last Run" in output
    assert "Pending Manual Review Queue" in output
    assert "Carryover Prep" in output
    assert "Disclaimer" in output
    assert "MRVL" in output
    assert "gap_pct=4.2% source=fake-provider as_of=2026-07-01T13:31:00Z gap_basis=premarket confidence=OK" in output
    assert "IBM state=manual_review score=unknown source=unknown as_of=unknown gap_basis=unknown confidence=unknown" in output
    assert "Matches your filter - not buy/sell advice. Verify before acting." in output


def test_readable_output_uses_nested_data_quality_provenance(monkeypatch):
    from cli import lance_desk_cycle

    payload = _payload()
    payload["top_watchlist"] = [
        {
            "ticker": "HOOD",
            "state": "not_in_play",
            "score": 10,
            "data_quality": {
                "gap_pct": 1.2,
                "gap_dollar": 0.9,
                "volume": 1200000,
                "rel_volume": 0.8,
                "data_status": "provider_failure",
                "provider_failures": {"yfinance": "DNS failure"},
                "sources": ["alpaca", "yfinance"],
                "as_of_et": "Jul 1 11:31 AM ET",
                "gap_basis": "last_trade",
                "confidence": "OK",
            },
        }
    ]

    def fake_run_lance_desk_cycle(**kwargs):
        return payload

    monkeypatch.setattr(lance_desk_cycle, "run_lance_desk_cycle", fake_run_lance_desk_cycle)

    result = runner.invoke(lance_desk_cycle.app, ["--tickers", "HOOD"])

    assert result.exit_code == 0
    assert (
        "HOOD state=not_in_play score=10 gap_pct=1.2% "
        "source=alpaca, yfinance as_of=Jul 1 11:31 AM ET "
        "gap_basis=last_trade confidence=OK data_status=provider_failure "
        "gap_dollar=0.9 volume=1200000 rvol=0.8 "
        "provider_failures={\"yfinance\": \"DNS failure\"}"
    ) in result.stdout


def test_readable_output_prints_lance_policy_fields(monkeypatch):
    from cli import lance_desk_cycle

    payload = _payload()
    payload["top_watchlist"] = [
        {
            "ticker": "MRVL",
            "state": "waiting_for_turn",
            "score": 72,
            "lance_quality_grade": "B_WATCH",
            "front_side_status": "front_side_active",
            "state_reason": "Directional pressure exists, but Lance is still waiting for the turn.",
            "waiting_for": ["prior 2-minute bar high break"],
            "invalidates_if": ["prior 2-minute low/high reference fails"],
            "manual_review_questions": ["Did the setup work, fail, chop, or reverse?"],
            "data_quality": {
                "gap_pct": -5.1,
                "rel_volume": 3.4,
                "sources": ["fake"],
                "as_of_et": "Jul 1 11:31 AM ET",
                "gap_basis": "last_trade",
                "confidence": "OK",
            },
        }
    ]

    def fake_run_lance_desk_cycle(**kwargs):
        return payload

    monkeypatch.setattr(lance_desk_cycle, "run_lance_desk_cycle", fake_run_lance_desk_cycle)

    result = runner.invoke(lance_desk_cycle.app, ["--tickers", "MRVL"])

    assert result.exit_code == 0
    assert "MRVL state=waiting_for_turn score=72" in result.stdout
    assert "grade=B_WATCH front_side=front_side_active" in result.stdout
    assert "reason=Directional pressure exists, but Lance is still waiting for the turn." in result.stdout
    assert "waiting_for=prior 2-minute bar high break" in result.stdout
    assert "invalidates_if=prior 2-minute low/high reference fails" in result.stdout
    assert "manual_review=Did the setup work, fail, chop, or reverse?" in result.stdout


def test_readable_output_prints_unified_lance_fields(monkeypatch):
    from cli import lance_desk_cycle

    payload = _payload()
    payload["unified_summary"] = {
        "status": "OK",
        "plan_count": 1,
        "watch_count": 1,
        "review_count": 0,
        "blocked_count": 0,
    }
    payload["unified_carryover"] = {
        "summary": {
            "carry_forward_count": 1,
            "manual_review_count": 0,
            "blocked_count": 0,
            "ignore_count": 0,
        },
        "groups": {
            "carry_forward": [
                {
                    "ticker": "IBM",
                    "action_mode": "watch",
                    "alignment": "aligned",
                    "primary_timeframe": "daily_then_intraday",
                    "thesis": "Daily idea is valid; intraday timing is still forming.",
                }
            ],
            "manual_review": [],
            "blocked": [],
            "ignore": [],
        },
    }
    payload["top_watchlist"] = [
        {
            "ticker": "IBM",
            "state": "watch",
            "score": 94,
            "action_mode": "watch",
            "alignment": "aligned",
            "primary_timeframe": "daily_then_intraday",
            "swing_state": "active_watch",
            "intraday_state": "waiting_for_turn",
            "swing_grade": "ACTIVE_DAILY_WATCH",
            "intraday_grade": "B_WATCH",
            "thesis": "Daily idea is valid; intraday timing is still forming.",
            "waiting_for": ["daily close confirmation", "prior 2-minute bar high break"],
            "invalidates_if": ["daily close loses prior-day low"],
            "data_quality": {
                "gap_pct": 1.4,
                "rel_volume": 2.2,
                "sources": ["fake"],
                "as_of_et": "Jul 1 4:00 PM ET",
                "gap_basis": "last_trade",
                "confidence": "OK",
            },
        }
    ]

    def fake_run_lance_desk_cycle(**kwargs):
        return payload

    monkeypatch.setattr(lance_desk_cycle, "run_lance_desk_cycle", fake_run_lance_desk_cycle)

    result = runner.invoke(lance_desk_cycle.app, ["--tickers", "IBM"])

    assert result.exit_code == 0
    assert "Unified: status=OK plan_count=1 watch_count=1 review_count=0 blocked_count=0" in result.stdout
    assert "IBM state=watch score=94" in result.stdout
    assert "action=watch alignment=aligned primary=daily_then_intraday" in result.stdout
    assert "swing=active_watch intraday=waiting_for_turn" in result.stdout
    assert "swing_grade=ACTIVE_DAILY_WATCH intraday_grade=B_WATCH" in result.stdout
    assert "thesis=Daily idea is valid; intraday timing is still forming." in result.stdout
    assert "Unified Carryover" in result.stdout
    assert "carry_forward_count=1 manual_review_count=0 blocked_count=0 ignore_count=0" in result.stdout
    assert "carry_forward:" in result.stdout
    assert "IBM action=watch alignment=aligned primary=daily_then_intraday" in result.stdout


def test_all_universes_and_persist_options_are_forwarded(monkeypatch):
    from cli import lance_desk_cycle

    calls: list[dict] = []

    def fake_run_lance_desk_cycle(**kwargs):
        calls.append(kwargs)
        return _payload()

    monkeypatch.setattr(lance_desk_cycle, "run_lance_desk_cycle", fake_run_lance_desk_cycle)

    result = runner.invoke(
        lance_desk_cycle.app,
        ["--all-universes", "--max-candidates", "15", "--persist"],
    )

    assert result.exit_code == 0
    assert calls[0]["all_universes"] is True
    assert calls[0]["persist"] is True
    assert calls[0]["max_candidates"] == 15


def test_watch_mode_reruns_cycle_and_prints_compact_changes(monkeypatch):
    from cli import lance_desk_cycle

    calls: list[dict] = []
    sleeps: list[float] = []

    def fake_run_lance_desk_cycle(**kwargs):
        calls.append(kwargs)
        return _watch_payload(len(calls))

    monkeypatch.setattr(lance_desk_cycle, "run_lance_desk_cycle", fake_run_lance_desk_cycle)
    monkeypatch.setattr(lance_desk_cycle.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = runner.invoke(
        lance_desk_cycle.app,
        [
            "--tickers",
            "MRVL,HOOD",
            "--max-candidates",
            "2",
            "--watch",
            "0.01",
            "--watch-iterations",
            "2",
        ],
    )

    assert result.exit_code == 0
    assert len(calls) == 2
    assert calls[0]["tickers"] == "MRVL,HOOD"
    assert calls[1]["tickers"] == "MRVL,HOOD"
    assert calls[0]["persist"] is False
    assert sleeps == [0.01]
    output = result.stdout
    assert "Watch Mode: every 0.01 seconds" in output
    assert "Watch Cycle 1" in output
    assert "Watch Cycle 2" in output
    assert "Lance Watch Changes" in output
    assert "MRVL previous_state=triggered_reference current_state=not_in_play state_changed=True score_delta=-25 gap_pct_delta=-1.4 rel_volume_delta=-1.1 flags=score_deteriorated, rvol_faded as_of=Jul 1 11:32 AM ET gap_basis=last_trade confidence=OK data_status=live" in output


def test_watch_mode_forces_persist_when_requested(monkeypatch):
    from cli import lance_desk_cycle

    calls: list[dict] = []

    def fake_run_lance_desk_cycle(**kwargs):
        calls.append(kwargs)
        return _payload()

    monkeypatch.setattr(lance_desk_cycle, "run_lance_desk_cycle", fake_run_lance_desk_cycle)
    monkeypatch.setattr(lance_desk_cycle.time, "sleep", lambda seconds: None)

    result = runner.invoke(
        lance_desk_cycle.app,
        ["--tickers", "MRVL", "--persist", "--watch", "1", "--watch-iterations", "1"],
    )

    assert result.exit_code == 0
    assert calls[0]["persist"] is True


def test_watch_mode_rejects_json_output():
    from cli import lance_desk_cycle

    result = runner.invoke(
        lance_desk_cycle.app,
        ["--tickers", "MRVL", "--watch", "1", "--json"],
    )

    assert result.exit_code != 0
    assert "--json cannot be combined with --watch" in result.stdout
