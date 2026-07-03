from __future__ import annotations

import json

from typer.testing import CliRunner


runner = CliRunner()


def _dashboard_payload() -> dict:
    return {
        "agent_name": "lance_full_cycle",
        "mode": "session_dashboard",
        "status": "OK",
        "session_ids": {
            "intraday": "2026-07-02-lance-intraday",
            "swing": "2026-07-02-lance-swing",
        },
        "target_session_date": "2026-07-03",
        "summary": {
            "journal_queue_count": 2,
            "intraday_carryover_count": 2,
            "swing_carryover_count": 1,
            "memory_outcome_count": 3,
            "tomorrow_watch_count": 3,
        },
        "dashboard_read": {
            "one_liner": (
                "Fresh scan required. 1 relative-strength watch, 1 swing-reclaim watch, "
                "1 caveated context name, 1 manual-review item."
            ),
            "fresh_scan_required": True,
            "sections": [
                {
                    "name": "fresh_scan_required",
                    "tickers": ["IBM", "MU", "TER"],
                    "note": "Carryover rows are alerts only until a fresh Lance scan confirms current data.",
                },
                {
                    "name": "relative_strength_watch",
                    "tickers": ["IBM"],
                    "rows": [
                        {
                            "lane": "intraday",
                            "ticker": "IBM",
                            "latest_state": "triggered_reference",
                            "playbook": "mean_reversion_after_capitulation",
                            "confidence": "OK",
                            "gap_basis": "premarket",
                            "as_of_et": "Jul 2 4:00 PM ET",
                        }
                    ],
                },
                {
                    "name": "swing_reclaim_watch",
                    "tickers": ["MU"],
                    "rows": [],
                },
                {
                    "name": "caveated_context",
                    "tickers": ["TER"],
                    "rows": [],
                },
                {"name": "manual_review_queue", "count": 1, "tickers": ["IBM"]},
            ],
            "data_caveats": [
                "MU, TER: confidence=STALE_DATA / gap_basis=last_trade as of Jul 2 4:00 PM ET."
            ],
        },
        "buckets": {
            "needs_manual_review": [
                {"lane": "intraday", "ticker": "IBM", "latest_state": "triggered_reference"}
            ],
            "relative_strength_watch": [
                {
                    "lane": "intraday",
                    "ticker": "IBM",
                    "latest_state": "triggered_reference",
                    "playbook": "mean_reversion_after_capitulation",
                    "confidence": "OK",
                    "gap_basis": "premarket",
                    "as_of_et": "Jul 2 4:00 PM ET",
                }
            ],
            "swing_reclaim_watch": [
                {
                    "lane": "swing",
                    "ticker": "MU",
                    "latest_state": "mean_reversion_watch",
                    "playbook": "swing_mean_reversion_reclaim",
                    "confidence": "STALE_DATA",
                    "gap_basis": "last_trade",
                    "as_of_et": "Jul 2 4:00 PM ET",
                }
            ],
            "caveated_context": [{"lane": "intraday", "ticker": "TER"}],
            "invalidated": [{"lane": "intraday", "ticker": "TER"}],
        },
        "memory": {"status": "OK", "outcome_count": 3, "by_playbook": []},
        "next_actions": ["Journal pending outcomes after manual chart review."],
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def _prep_payload() -> dict:
    return {
        "agent_name": "lance_full_cycle",
        "mode": "tomorrow_prep",
        "status": "OK",
        "target_session_date": "2026-07-03",
        "fresh_scan_required": True,
        "watchlist": [
            {
                "ticker": "IBM",
                "lanes": ["intraday"],
                "bucket": "relative_strength_watch",
                "playbook": "mean_reversion_after_capitulation",
                "latest_state": "triggered_reference",
                "confidence": "OK",
                "gap_basis": "premarket",
                "as_of_et": "Jul 2 4:00 PM ET",
            }
        ],
        "confirmation_checklist": ["Run a fresh Lance full-cycle scan."],
        "what_lance_would_do_now": "Prepare the watchlist and wait.",
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def test_lance_dashboard_cli_prints_readable_dashboard(monkeypatch):
    from cli import lance_dashboard

    def fake_dashboard(**kwargs):
        assert kwargs == {
            "intraday_session_id": "2026-07-02-lance-intraday",
            "swing_session_id": "2026-07-02-lance-swing",
            "target_session_date": "2026-07-03",
            "limit": 25,
            "memory_limit": 50,
        }
        return _dashboard_payload()

    monkeypatch.setattr(lance_dashboard, "get_lance_session_dashboard", fake_dashboard)

    result = runner.invoke(
        lance_dashboard.app,
        [
            "dashboard",
            "--intraday-session-id",
            "2026-07-02-lance-intraday",
            "--swing-session-id",
            "2026-07-02-lance-swing",
            "--target-session-date",
            "2026-07-03",
            "--limit",
            "25",
            "--memory-limit",
            "50",
        ],
    )

    assert result.exit_code == 0
    assert "Lance Session Dashboard" in result.stdout
    assert "Fresh Scan Required" in result.stdout
    assert "Fresh scan required. 1 relative-strength watch" in result.stdout
    assert "journal_queue_count=2" in result.stdout
    assert "Manual Review Queue: 1 item(s) - IBM" in result.stdout
    assert "Data Caveats" in result.stdout
    assert "IBM lane=intraday state=triggered_reference" in result.stdout
    assert "Matches your filter - not buy/sell advice" in result.stdout


def test_lance_dashboard_cli_dashboard_json(monkeypatch):
    from cli import lance_dashboard

    monkeypatch.setattr(
        lance_dashboard,
        "get_lance_session_dashboard",
        lambda **kwargs: _dashboard_payload(),
    )

    result = runner.invoke(lance_dashboard.app, ["dashboard", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["mode"] == "session_dashboard"


def test_lance_dashboard_cli_prints_tomorrow_prep(monkeypatch):
    from cli import lance_dashboard

    def fake_prep(**kwargs):
        assert kwargs["target_session_date"] == "2026-07-03"
        return _prep_payload()

    monkeypatch.setattr(lance_dashboard, "build_lance_tomorrow_prep", fake_prep)

    result = runner.invoke(
        lance_dashboard.app,
        ["tomorrow", "--target-session-date", "2026-07-03"],
    )

    assert result.exit_code == 0
    assert "Lance Tomorrow Prep" in result.stdout
    assert "fresh_scan_required=True" in result.stdout
    assert "IBM lane=intraday bucket=relative_strength_watch" in result.stdout
    assert "Run a fresh Lance full-cycle scan." in result.stdout
