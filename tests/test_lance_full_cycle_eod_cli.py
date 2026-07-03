from __future__ import annotations

import json

from typer.testing import CliRunner


runner = CliRunner()


def test_lance_full_cycle_eod_review_prints_queue(monkeypatch):
    from cli import lance_full_cycle_eod

    def fake_review_lance_full_cycle(**kwargs):
        assert kwargs == {
            "intraday_session_id": "2026-07-02-lance-intraday",
            "swing_session_id": "2026-07-02-lance-swing",
            "limit": 25,
        }
        return {
            "agent_name": "lance_full_cycle",
            "mode": "full_cycle_review",
            "session_ids": {
                "intraday": "2026-07-02-lance-intraday",
                "swing": "2026-07-02-lance-swing",
            },
            "summary": {"journal_queue_count": 2},
            "journal_queue": [
                {
                    "lane": "intraday",
                    "ticker": "IBM",
                    "latest_state": "triggered_reference",
                    "playbook": "mean_reversion_after_capitulation",
                    "suggested_outcome": "unknown",
                },
                {
                    "lane": "swing",
                    "ticker": "MU",
                    "latest_state": "mean_reversion_watch",
                    "playbook": "swing_mean_reversion_reclaim",
                    "suggested_outcome": "unknown",
                },
            ],
            "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
        }

    monkeypatch.setattr(
        lance_full_cycle_eod,
        "review_lance_full_cycle",
        fake_review_lance_full_cycle,
    )

    result = runner.invoke(
        lance_full_cycle_eod.app,
        [
            "review",
            "--intraday-session-id",
            "2026-07-02-lance-intraday",
            "--swing-session-id",
            "2026-07-02-lance-swing",
            "--limit",
            "25",
        ],
    )

    assert result.exit_code == 0
    assert "Lance Full-Cycle EOD Review" in result.stdout
    assert "journal_queue_count=2" in result.stdout
    assert "intraday IBM" in result.stdout
    assert "swing MU" in result.stdout
    assert "Matches your filter - not buy/sell advice" in result.stdout


def test_lance_full_cycle_eod_review_json(monkeypatch):
    from cli import lance_full_cycle_eod

    def fake_review_lance_full_cycle(**kwargs):
        return {
            "agent_name": "lance_full_cycle",
            "mode": "full_cycle_review",
            "journal_queue": [{"lane": "intraday", "ticker": "IBM"}],
        }

    monkeypatch.setattr(
        lance_full_cycle_eod,
        "review_lance_full_cycle",
        fake_review_lance_full_cycle,
    )

    result = runner.invoke(lance_full_cycle_eod.app, ["review", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "full_cycle_review"


def test_lance_full_cycle_eod_journal_prints_record(monkeypatch):
    from cli import lance_full_cycle_eod

    def fake_journal_lance_full_cycle_outcome(**kwargs):
        assert kwargs == {
            "lane": "swing",
            "session_id": "2026-07-02-lance-swing",
            "ticker": "MU",
            "playbook": "swing_mean_reversion_reclaim",
            "outcome": "chop",
            "notes": "Manual review.",
            "plan": None,
        }
        return {
            "agent_name": "lance_full_cycle",
            "mode": "full_cycle_journal",
            "lane": "swing",
            "journal": {
                "status": "OK",
                "recorded": {
                    "ticker": "MU",
                    "outcome": "chop",
                    "playbook": "swing_mean_reversion_reclaim",
                    "session_id": "2026-07-02-lance-swing",
                },
            },
            "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
        }

    monkeypatch.setattr(
        lance_full_cycle_eod,
        "journal_lance_full_cycle_outcome",
        fake_journal_lance_full_cycle_outcome,
    )

    result = runner.invoke(
        lance_full_cycle_eod.app,
        [
            "journal",
            "--lane",
            "swing",
            "--session-id",
            "2026-07-02-lance-swing",
            "--ticker",
            "MU",
            "--playbook",
            "swing_mean_reversion_reclaim",
            "--outcome",
            "chop",
            "--notes",
            "Manual review.",
        ],
    )

    assert result.exit_code == 0
    assert "Recorded Full-Cycle Outcome" in result.stdout
    assert "lane=swing" in result.stdout
    assert "MU outcome=chop" in result.stdout
