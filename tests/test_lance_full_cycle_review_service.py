from __future__ import annotations

from services.lance_full_cycle_review_service import LanceFullCycleReviewService


class FakeReviewService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def review(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["session_id"].endswith("-lance-intraday"):
            return {
                "agent_name": "lance_intraday",
                "status": "OK",
                "session_id": kwargs["session_id"],
                "pending_count": 1,
                "reviewed_count": 0,
                "pending_reviews": [
                    {
                        "ticker": "IBM",
                        "latest_state": "triggered_reference",
                        "suggested_outcome": "unknown",
                        "journal_args": {
                            "session_id": kwargs["session_id"],
                            "ticker": "IBM",
                            "playbook": "mean_reversion_after_capitulation",
                            "outcome": "unknown",
                        },
                    }
                ],
                "reviewed": [],
            }
        return {
            "agent_name": "lance_intraday",
            "status": "OK",
            "session_id": kwargs["session_id"],
            "pending_count": 1,
            "reviewed_count": 0,
            "pending_reviews": [
                {
                    "ticker": "MU",
                    "latest_state": "mean_reversion_watch",
                    "suggested_outcome": "unknown",
                    "journal_args": {
                        "session_id": kwargs["session_id"],
                        "ticker": "MU",
                        "playbook": "swing_mean_reversion_reclaim",
                        "outcome": "unknown",
                    },
                }
            ],
            "reviewed": [],
        }


class FakeJournalService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def record(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_intraday",
            "status": "OK",
            "recorded": {
                "session_id": kwargs["session_id"],
                "ticker": kwargs["ticker"],
                "playbook": kwargs["playbook"],
                "outcome": kwargs["outcome"],
                "notes": kwargs.get("notes"),
            },
            "recent_outcomes": [],
        }


def test_lance_full_cycle_review_combines_intraday_and_swing_queues():
    review = FakeReviewService()

    output = LanceFullCycleReviewService(review_service=review).review(
        intraday_session_id="2026-07-02-lance-intraday",
        swing_session_id="2026-07-02-lance-swing",
        limit=25,
    )

    assert review.calls == [
        {"session_id": "2026-07-02-lance-intraday", "limit": 25},
        {"session_id": "2026-07-02-lance-swing", "limit": 25},
    ]
    assert output["agent_name"] == "lance_full_cycle"
    assert output["mode"] == "full_cycle_review"
    assert output["session_ids"] == {
        "intraday": "2026-07-02-lance-intraday",
        "swing": "2026-07-02-lance-swing",
    }
    assert output["summary"] == {
        "intraday_pending_count": 1,
        "intraday_reviewed_count": 0,
        "swing_pending_count": 1,
        "swing_reviewed_count": 0,
        "journal_queue_count": 2,
    }
    assert output["journal_queue"] == [
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
    ]
    assert output["notes"] == [
        "Outcomes are not inferred. Journal only after manual chart review."
    ]


def test_lance_full_cycle_review_journals_outcome_by_lane():
    journal = FakeJournalService()

    output = LanceFullCycleReviewService(journal_service=journal).record_outcome(
        lane="swing",
        session_id="2026-07-02-lance-swing",
        ticker="MU",
        playbook="swing_mean_reversion_reclaim",
        outcome="chop",
        notes="Manual review: reclaim failed and chopped.",
        plan={"ticker": "MU"},
    )

    assert journal.calls == [{
        "session_id": "2026-07-02-lance-swing",
        "ticker": "MU",
        "playbook": "swing_mean_reversion_reclaim",
        "outcome": "chop",
        "notes": "Manual review: reclaim failed and chopped.",
        "plan": {"ticker": "MU"},
    }]
    assert output["agent_name"] == "lance_full_cycle"
    assert output["mode"] == "full_cycle_journal"
    assert output["lane"] == "swing"
    assert output["journal"]["recorded"]["ticker"] == "MU"
