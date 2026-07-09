from __future__ import annotations

import json

from typer.testing import CliRunner


runner = CliRunner()


def _review_payload() -> dict:
    return {
        "agent_name": "lance_intraday",
        "strategy": "Lance session review queue",
        "session_id": "session-1",
        "status": "OK",
        "ticker_count": 2,
        "pending_count": 1,
        "reviewed_count": 1,
        "pending_reviews": [
            {
                "ticker": "MRVL",
                "latest_state": "setup_forming",
                "score_delta": 18,
                "gap_pct_delta": 2.1,
                "rel_volume_delta": 1.2,
                "review_focus": ["state_changed", "rvol_expanded"],
                "journal_args": {
                    "session_id": "session-1",
                    "ticker": "MRVL",
                    "playbook": "mean_reversion_after_capitulation",
                    "outcome": "unknown",
                },
            }
        ],
        "reviewed": [{"ticker": "IBM", "latest_state": "not_in_play", "outcomes": []}],
        "notes": ["Outcomes are not inferred."],
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def _journal_payload() -> dict:
    return {
        "agent_name": "lance_intraday",
        "status": "OK",
        "recorded": {
            "session_id": "session-1",
            "ticker": "MRVL",
            "playbook": "mean_reversion_after_capitulation",
            "outcome": "worked",
            "notes": "Held relative strength.",
        },
        "recent_outcomes": [{"ticker": "MRVL", "outcome": "worked"}],
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def _carryover_payload() -> dict:
    return {
        "agent_name": "lance_intraday",
        "strategy": "Lance carryover plan",
        "source_session_id": "session-1",
        "target_session_date": "2026-07-02",
        "status": "OK",
        "carryover_count": 2,
        "fresh_scan_required": True,
        "groups": {
            "strength_carryover": [
                {
                    "ticker": "HOOD",
                    "latest_state": "setup_forming",
                    "gap_pct": 8.1,
                    "rel_volume": 3.4,
                    "confidence": "OK",
                    "gap_basis": "last_trade",
                    "as_of_et": "Jul 1 3:30 PM ET",
                    "review_focus": ["rvol_expanded"],
                }
            ],
            "weakness_carryover": [],
            "context_only": [{"ticker": "IBM", "latest_state": "not_in_play"}],
        },
        "notes": ["This is a carryover watch plan, not a trade signal."],
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def _memory_payload() -> dict:
    return {
        "agent_name": "lance_intraday",
        "strategy": "Lance market memory report",
        "status": "OK",
        "outcome_count": 3,
        "filters": {"session_id": "session-1", "ticker": None, "limit": 25},
        "by_playbook": [
            {
                "playbook": "mean_reversion_after_capitulation",
                "total": 2,
                "outcomes": {"worked": 1, "failed": 1, "chop": 0, "reversed": 0, "unknown": 0},
                "worked_rate": 0.5,
            }
        ],
        "by_ticker": [
            {
                "ticker": "MRVL",
                "total": 2,
                "outcomes": {"worked": 1, "failed": 1, "chop": 0, "reversed": 0, "unknown": 0},
                "worked_rate": 0.5,
            }
        ],
        "by_action_mode": [
            {
                "action_mode": "watch",
                "total": 2,
                "outcomes": {"worked": 1, "failed": 1, "chop": 0, "reversed": 0, "unknown": 0},
                "worked_rate": 0.5,
            }
        ],
        "by_alignment": [
            {
                "alignment": "aligned",
                "total": 2,
                "outcomes": {"worked": 1, "failed": 1, "chop": 0, "reversed": 0, "unknown": 0},
                "worked_rate": 0.5,
            }
        ],
        "by_primary_timeframe": [
            {
                "primary_timeframe": "daily_then_intraday",
                "total": 2,
                "outcomes": {"worked": 1, "failed": 1, "chop": 0, "reversed": 0, "unknown": 0},
                "worked_rate": 0.5,
            }
        ],
        "recent_outcomes": [{"ticker": "MRVL", "outcome": "worked"}],
        "notes": ["Outcome counts are journaled labels, not P&L."],
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def test_lance_eod_review_json_forwards_args(monkeypatch):
    from cli import lance_eod

    calls: list[dict] = []

    def fake_review(**kwargs):
        calls.append(kwargs)
        return _review_payload()

    monkeypatch.setattr(lance_eod, "review_lance_session", fake_review)

    result = runner.invoke(
        lance_eod.app,
        ["review", "--session-id", "session-1", "--limit", "20", "--json"],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == _review_payload()
    assert calls == [{"session_id": "session-1", "limit": 20}]


def test_lance_eod_review_readable_shows_pending_review_queue(monkeypatch):
    from cli import lance_eod

    monkeypatch.setattr(lance_eod, "review_lance_session", lambda **kwargs: _review_payload())

    result = runner.invoke(lance_eod.app, ["review", "--session-id", "session-1"])

    assert result.exit_code == 0
    output = result.stdout
    assert "Lance EOD Review" in output
    assert "Session: session-1" in output
    assert "pending=1 reviewed=1" in output
    assert "MRVL latest_state=setup_forming score_delta=18 gap_pct_delta=2.1 rel_volume_delta=1.2 focus=state_changed, rvol_expanded" in output
    assert "journal: session_id=session-1 ticker=MRVL playbook=mean_reversion_after_capitulation outcome=unknown" in output
    assert "Matches your filter - not buy/sell advice. Verify before acting." in output


def test_lance_eod_journal_records_outcome(monkeypatch):
    from cli import lance_eod

    calls: list[dict] = []

    def fake_journal(**kwargs):
        calls.append(kwargs)
        return _journal_payload()

    monkeypatch.setattr(lance_eod, "journal_lance_outcome", fake_journal)

    result = runner.invoke(
        lance_eod.app,
        [
            "journal",
            "--session-id",
            "session-1",
            "--ticker",
            "MRVL",
            "--playbook",
            "mean_reversion_after_capitulation",
            "--outcome",
            "worked",
            "--notes",
            "Held relative strength.",
        ],
    )

    assert result.exit_code == 0
    assert calls == [{
        "session_id": "session-1",
        "ticker": "MRVL",
        "playbook": "mean_reversion_after_capitulation",
        "outcome": "worked",
        "notes": "Held relative strength.",
        "plan": None,
    }]
    assert "Recorded Outcome" in result.stdout
    assert "MRVL outcome=worked playbook=mean_reversion_after_capitulation" in result.stdout


def test_lance_eod_journal_accepts_unified_plan_json(monkeypatch):
    from cli import lance_eod

    calls: list[dict] = []
    payload = _journal_payload()
    payload["recorded"]["plan_summary"] = {
        "action_mode": "watch",
        "alignment": "aligned",
        "primary_timeframe": "daily_then_intraday",
        "thesis": "Daily idea is valid; intraday timing is still forming.",
    }

    def fake_journal(**kwargs):
        calls.append(kwargs)
        return payload

    monkeypatch.setattr(lance_eod, "journal_lance_outcome", fake_journal)

    result = runner.invoke(
        lance_eod.app,
        [
            "journal",
            "--session-id",
            "session-1",
            "--ticker",
            "IBM",
            "--playbook",
            "relative_strength_continuation",
            "--outcome",
            "worked",
            "--plan-json",
            '{"action_mode":"watch","alignment":"aligned","primary_timeframe":"daily_then_intraday"}',
        ],
    )

    assert result.exit_code == 0
    assert calls[0]["plan"] == {
        "action_mode": "watch",
        "alignment": "aligned",
        "primary_timeframe": "daily_then_intraday",
    }
    assert "plan_summary: action_mode=watch alignment=aligned primary_timeframe=daily_then_intraday" in result.stdout


def test_lance_eod_journal_rejects_bad_plan_json(monkeypatch):
    from cli import lance_eod

    calls: list[dict] = []
    monkeypatch.setattr(lance_eod, "journal_lance_outcome", lambda **kwargs: calls.append(kwargs))

    result = runner.invoke(
        lance_eod.app,
        [
            "journal",
            "--session-id",
            "session-1",
            "--ticker",
            "IBM",
            "--playbook",
            "relative_strength_continuation",
            "--outcome",
            "worked",
            "--plan-json",
            "not-json",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid --plan-json" in result.stdout
    assert calls == []


def test_lance_eod_carryover_readable_groups_next_session_plan(monkeypatch):
    from cli import lance_eod

    calls: list[dict] = []

    def fake_carryover(**kwargs):
        calls.append(kwargs)
        return _carryover_payload()

    monkeypatch.setattr(lance_eod, "build_lance_carryover_plan", fake_carryover)

    result = runner.invoke(
        lance_eod.app,
        [
            "carryover",
            "--session-id",
            "session-1",
            "--target-session-date",
            "2026-07-02",
            "--limit",
            "20",
        ],
    )

    assert result.exit_code == 0
    assert calls == [{
        "session_id": "session-1",
        "target_session_date": "2026-07-02",
        "limit": 20,
    }]
    output = result.stdout
    assert "Lance Carryover Plan" in output
    assert "source_session=session-1 target_session=2026-07-02 carryover_count=2 fresh_scan_required=True" in output
    assert "strength_carryover:" in output
    assert "HOOD latest_state=setup_forming gap_pct=8.1% rvol=3.4 as_of=Jul 1 3:30 PM ET gap_basis=last_trade confidence=OK focus=rvol_expanded" in output
    assert "context_only:" in output
    assert "IBM latest_state=not_in_play" in output


def test_lance_eod_memory_json_forwards_filters(monkeypatch):
    from cli import lance_eod

    calls: list[dict] = []

    def fake_memory(**kwargs):
        calls.append(kwargs)
        return _memory_payload()

    monkeypatch.setattr(lance_eod, "summarize_lance_memory", fake_memory)

    result = runner.invoke(
        lance_eod.app,
        ["memory", "--session-id", "session-1", "--ticker", "MRVL", "--limit", "25", "--json"],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == _memory_payload()
    assert calls == [{"session_id": "session-1", "ticker": "MRVL", "limit": 25}]


def test_lance_eod_memory_readable_summarizes_playbooks_and_tickers(monkeypatch):
    from cli import lance_eod

    monkeypatch.setattr(lance_eod, "summarize_lance_memory", lambda **kwargs: _memory_payload())

    result = runner.invoke(lance_eod.app, ["memory", "--session-id", "session-1"])

    assert result.exit_code == 0
    output = result.stdout
    assert "Lance Market Memory" in output
    assert "outcome_count=3" in output
    assert "mean_reversion_after_capitulation total=2 worked=1 failed=1 chop=0 reversed=0 unknown=0 worked_rate=0.5" in output
    assert "MRVL total=2 worked=1 failed=1 chop=0 reversed=0 unknown=0 worked_rate=0.5" in output
    assert "By Action Mode" in output
    assert "watch total=2 worked=1 failed=1 chop=0 reversed=0 unknown=0 worked_rate=0.5" in output
    assert "By Alignment" in output
    assert "aligned total=2 worked=1 failed=1 chop=0 reversed=0 unknown=0 worked_rate=0.5" in output
    assert "By Primary Timeframe" in output
    assert "daily_then_intraday total=2 worked=1 failed=1 chop=0 reversed=0 unknown=0 worked_rate=0.5" in output
    assert "Outcome counts are journaled labels" in output


def test_lance_eod_summary_saves_daily_json_and_markdown(monkeypatch, tmp_path):
    from cli import lance_eod

    monkeypatch.setattr(lance_eod, "review_lance_session", lambda **kwargs: _review_payload())
    monkeypatch.setattr(lance_eod, "summarize_lance_memory", lambda **kwargs: _memory_payload())
    monkeypatch.setattr(lance_eod, "build_lance_carryover_plan", lambda **kwargs: _carryover_payload())

    result = runner.invoke(
        lance_eod.app,
        [
            "summary",
            "--session-id",
            "session-1",
            "--date",
            "2026-07-02",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "Lance Daily Summary" in result.stdout
    payload = json.loads((tmp_path / "2026-07-02.json").read_text())
    assert payload["watched"]["tickers"] == ["MRVL", "IBM"]
    assert payload["outcomes"]["counts"]["worked"] == 1
    assert payload["outcomes"]["counts"]["failed"] == 0
    assert payload["tomorrow_follow_up"] == [
        {"ticker": "MRVL", "source": "pending_review"},
        {"ticker": "HOOD", "source": "strength_carryover"},
        {"ticker": "IBM", "source": "context_only"},
    ]
    assert payload["tim_sykes"]["status"] == "unknown"
    markdown = (tmp_path / "2026-07-02.md").read_text()
    assert "Daily Trading Summary - 2026-07-02" in markdown
    assert "Tim/Sykes session persistence is not wired" in markdown


def test_lance_eod_summary_marks_old_session_as_prep_only(monkeypatch, tmp_path):
    from cli import lance_eod

    review = _review_payload()
    review["session_id"] = "2026-07-02-live-clean-lance-intraday"
    monkeypatch.setattr(lance_eod, "review_lance_session", lambda **kwargs: review)
    monkeypatch.setattr(lance_eod, "summarize_lance_memory", lambda **kwargs: _memory_payload())
    monkeypatch.setattr(lance_eod, "build_lance_carryover_plan", lambda **kwargs: _carryover_payload())

    result = runner.invoke(
        lance_eod.app,
        [
            "summary",
            "--date",
            "2026-07-08",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "Live session captured: no" in result.stdout
    payload = json.loads((tmp_path / "2026-07-08.json").read_text())
    assert payload["status"] == "PREP_ONLY"
    assert payload["live_session_captured"] is False
    assert payload["source_session_date"] == "2026-07-02"
    assert "No live Lance session captured for 2026-07-08" in payload["notes"][0]
