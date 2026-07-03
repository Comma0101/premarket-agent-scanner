from __future__ import annotations

from services.lance_session_dashboard_service import LanceSessionDashboardService


class FakeFullCycleReviewService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def review(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_full_cycle",
            "mode": "full_cycle_review",
            "status": "OK",
            "session_ids": {
                "intraday": "2026-07-02-lance-intraday",
                "swing": "2026-07-02-lance-swing",
            },
            "summary": {
                "intraday_pending_count": 1,
                "intraday_reviewed_count": 0,
                "swing_pending_count": 1,
                "swing_reviewed_count": 0,
                "journal_queue_count": 2,
            },
            "journal_queue": [
                {
                    "lane": "intraday",
                    "ticker": "IBM",
                    "latest_state": "triggered_reference",
                    "playbook": "mean_reversion_after_capitulation",
                    "suggested_outcome": "unknown",
                    "journal_args": {
                        "lane": "intraday",
                        "session_id": "2026-07-02-lance-intraday",
                        "ticker": "IBM",
                        "playbook": "mean_reversion_after_capitulation",
                        "outcome": "unknown",
                    },
                },
                {
                    "lane": "swing",
                    "ticker": "MU",
                    "latest_state": "mean_reversion_watch",
                    "playbook": "swing_mean_reversion_reclaim",
                    "suggested_outcome": "unknown",
                    "journal_args": {
                        "lane": "swing",
                        "session_id": "2026-07-02-lance-swing",
                        "ticker": "MU",
                        "playbook": "swing_mean_reversion_reclaim",
                        "outcome": "unknown",
                    },
                },
            ],
            "notes": ["Outcomes are not inferred."],
            "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
        }


class FakeCarryoverService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build(self, **kwargs):
        self.calls.append(kwargs)
        session_id = kwargs["session_id"]
        if session_id.endswith("-swing"):
            return {
                "agent_name": "lance_intraday",
                "strategy": "Lance carryover plan",
                "source_session_id": session_id,
                "target_session_date": kwargs["target_session_date"],
                "status": "OK",
                "carryover_count": 1,
                "fresh_scan_required": True,
                "groups": {
                    "swing_mean_reversion_carryover": [
                        _carryover_row(
                            "MU",
                            latest_state="mean_reversion_watch",
                            playbook="swing_mean_reversion_reclaim",
                            confidence="STALE_DATA",
                            gap_basis="last_trade",
                        )
                    ],
                    "swing_continuation_carryover": [],
                    "strength_carryover": [],
                    "weakness_carryover": [],
                    "context_only": [],
                },
            }
        return {
            "agent_name": "lance_intraday",
            "strategy": "Lance carryover plan",
            "source_session_id": session_id,
            "target_session_date": kwargs["target_session_date"],
            "status": "OK",
            "carryover_count": 2,
            "fresh_scan_required": True,
            "groups": {
                "swing_mean_reversion_carryover": [],
                "swing_continuation_carryover": [],
                "strength_carryover": [
                    _carryover_row(
                        "IBM",
                        latest_state="triggered_reference",
                        playbook="mean_reversion_after_capitulation",
                        confidence="OK",
                        gap_basis="premarket",
                    )
                ],
                "weakness_carryover": [],
                "context_only": [
                    _carryover_row(
                        "TER",
                        latest_state="blocked_data_quality",
                        playbook="watchlist_context",
                        confidence="STALE_DATA",
                        gap_basis="last_trade",
                    )
                ],
            },
        }


class FakeMemoryService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def summarize(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_intraday",
            "strategy": "Lance market memory report",
            "status": "OK",
            "outcome_count": 3,
            "by_playbook": [
                {
                    "playbook": "mean_reversion_after_capitulation",
                    "total": 2,
                    "outcomes": {
                        "worked": 1,
                        "failed": 1,
                        "chop": 0,
                        "reversed": 0,
                        "unknown": 0,
                    },
                    "worked_rate": 0.5,
                }
            ],
            "recent_outcomes": [{"ticker": "IBM", "outcome": "worked"}],
            "notes": ["Outcome counts are journaled labels."],
            "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
        }


def _carryover_row(
    ticker: str,
    *,
    latest_state: str,
    playbook: str,
    confidence: str,
    gap_basis: str,
) -> dict:
    return {
        "ticker": ticker,
        "latest_state": latest_state,
        "playbook": playbook,
        "gap_pct": 6.2,
        "rel_volume": 4.1,
        "confidence": confidence,
        "gap_basis": gap_basis,
        "as_of_et": "Jul 2 4:00 PM ET",
        "sources": ["fake"],
        "score_delta": 1.5,
        "review_focus": ["manual_chart_review_required"],
        "journal_args": {
            "session_id": "session",
            "ticker": ticker,
            "playbook": playbook,
            "outcome": "unknown",
        },
        "confirmation_checklist": ["Run a fresh Advanced Lance scan before the next session."],
    }


def test_lance_session_dashboard_combines_review_carryover_and_memory():
    review = FakeFullCycleReviewService()
    carryover = FakeCarryoverService()
    memory = FakeMemoryService()

    output = LanceSessionDashboardService(
        full_cycle_review_service=review,
        carryover_service=carryover,
        memory_service=memory,
    ).dashboard(
        intraday_session_id="2026-07-02-lance-intraday",
        swing_session_id="2026-07-02-lance-swing",
        target_session_date="2026-07-03",
        limit=25,
        memory_limit=50,
    )

    assert review.calls == [{
        "intraday_session_id": "2026-07-02-lance-intraday",
        "swing_session_id": "2026-07-02-lance-swing",
        "limit": 25,
    }]
    assert carryover.calls == [
        {
            "session_id": "2026-07-02-lance-intraday",
            "target_session_date": "2026-07-03",
            "limit": 25,
        },
        {
            "session_id": "2026-07-02-lance-swing",
            "target_session_date": "2026-07-03",
            "limit": 25,
        },
    ]
    assert memory.calls == [{"limit": 50}]

    assert output["agent_name"] == "lance_full_cycle"
    assert output["mode"] == "session_dashboard"
    assert output["status"] == "OK"
    assert output["session_ids"] == {
        "intraday": "2026-07-02-lance-intraday",
        "swing": "2026-07-02-lance-swing",
    }
    assert output["summary"] == {
        "journal_queue_count": 2,
        "intraday_carryover_count": 2,
        "swing_carryover_count": 1,
        "memory_outcome_count": 3,
        "tomorrow_watch_count": 3,
    }
    assert output["dashboard_read"] == {
        "one_liner": (
            "Fresh scan required. 1 relative-strength watch, 1 swing-reclaim watch, "
            "1 caveated context name, 2 manual-review items."
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
                "rows": output["dashboard_read"]["sections"][1]["rows"],
            },
            {
                "name": "swing_reclaim_watch",
                "tickers": ["MU"],
                "rows": output["dashboard_read"]["sections"][2]["rows"],
            },
            {
                "name": "caveated_context",
                "tickers": ["TER"],
                "rows": output["dashboard_read"]["sections"][3]["rows"],
            },
            {
                "name": "manual_review_queue",
                "count": 2,
                "tickers": ["IBM", "MU"],
            },
        ],
        "data_caveats": [
            "MU, TER: confidence=STALE_DATA / gap_basis=last_trade as of Jul 2 4:00 PM ET."
        ],
    }
    assert [row["ticker"] for row in output["buckets"]["needs_manual_review"]] == ["IBM", "MU"]
    assert [row["ticker"] for row in output["buckets"]["relative_strength_watch"]] == ["IBM"]
    assert [row["ticker"] for row in output["buckets"]["swing_reclaim_watch"]] == ["MU"]
    assert [row["ticker"] for row in output["buckets"]["caveated_context"]] == ["TER", "MU"]
    assert [row["ticker"] for row in output["buckets"]["invalidated"]] == ["TER"]
    assert output["memory"]["by_playbook"][0]["worked_rate"] == 0.5
    assert output["next_actions"][0] == "Journal pending outcomes after manual chart review."
    assert output["disclaimer"] == "Matches your filter - not buy/sell advice. Verify before acting."


def test_lance_tomorrow_prep_returns_fresh_scan_plan_and_watchlist():
    output = LanceSessionDashboardService(
        full_cycle_review_service=FakeFullCycleReviewService(),
        carryover_service=FakeCarryoverService(),
        memory_service=FakeMemoryService(),
    ).tomorrow_prep(
        intraday_session_id="2026-07-02-lance-intraday",
        swing_session_id="2026-07-02-lance-swing",
        target_session_date="2026-07-03",
        limit=25,
    )

    assert output["agent_name"] == "lance_full_cycle"
    assert output["mode"] == "tomorrow_prep"
    assert output["fresh_scan_required"] is True
    assert output["target_session_date"] == "2026-07-03"
    assert output["watchlist"] == [
        {
            "ticker": "IBM",
            "lanes": ["intraday"],
            "bucket": "relative_strength_watch",
            "playbook": "mean_reversion_after_capitulation",
            "latest_state": "triggered_reference",
            "confidence": "OK",
            "gap_basis": "premarket",
            "as_of_et": "Jul 2 4:00 PM ET",
        },
        {
            "ticker": "MU",
            "lanes": ["swing"],
            "bucket": "swing_reclaim_watch",
            "playbook": "swing_mean_reversion_reclaim",
            "latest_state": "mean_reversion_watch",
            "confidence": "STALE_DATA",
            "gap_basis": "last_trade",
            "as_of_et": "Jul 2 4:00 PM ET",
        },
        {
            "ticker": "TER",
            "lanes": ["intraday"],
            "bucket": "caveated_context",
            "playbook": "watchlist_context",
            "latest_state": "blocked_data_quality",
            "confidence": "STALE_DATA",
            "gap_basis": "last_trade",
            "as_of_et": "Jul 2 4:00 PM ET",
        },
    ]
    assert output["what_lance_would_do_now"] == (
        "Prepare the watchlist and wait for tomorrow's fresh scan; carryover rows are alerts, "
        "not active setups."
    )
    assert output["confirmation_checklist"][0] == "Run a fresh Lance full-cycle scan."
