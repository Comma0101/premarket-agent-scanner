from __future__ import annotations

from services.lance_desk_cycle_service import LanceDeskCycleService


class FakeAdvancedScanService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def scan(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_intraday",
            "mode": "advanced",
            "strategy": "Advanced Lance intraday co-pilot",
            "session_id": "session-1",
            "status": "OK",
            "scanned_count": 20,
            "candidate_count": 2,
            "watchlist": [
                {"ticker": "IBM", "state": "setup_forming", "score": 85, "plan": {"ticker": "IBM", "state": "setup_forming"}},
                {"ticker": "MRVL", "state": "not_in_play", "score": 20, "plan": {"ticker": "MRVL", "state": "not_in_play"}},
            ],
            "market_context": {"theme_rotation": [{"theme": "AI_SEMIS_MEMORY"}]},
            "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
        }


class FakeUpdateService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def update(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_intraday",
            "session_id": kwargs["session_id"],
            "status": "OK",
            "tracked_count": 2,
            "updated_count": 2,
            "updates": [
                {"ticker": "IBM", "current_state": "triggered_reference", "state_changed": True},
                {"ticker": "MRVL", "current_state": "not_in_play", "state_changed": False},
            ],
        }


class FakeTimelineService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def timeline(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_intraday",
            "session_id": kwargs["session_id"],
            "status": "OK",
            "event_count": 4,
            "tickers": [{"ticker": "IBM"}, {"ticker": "MRVL"}],
        }


class FakeReviewService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def review(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_intraday",
            "session_id": kwargs["session_id"],
            "status": "OK",
            "pending_count": 1,
            "reviewed_count": 0,
            "pending_reviews": [{"ticker": "IBM", "suggested_outcome": "unknown"}],
        }


class FakeCarryoverService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_intraday",
            "source_session_id": kwargs["session_id"],
            "target_session_date": kwargs["target_session_date"],
            "status": "OK",
            "carryover_count": 1,
            "groups": {"strength_carryover": [{"ticker": "IBM"}]},
        }


class FakeUnifiedService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_unified",
            "plan_count": 2,
            "plans": [
                {
                    "ticker": "IBM",
                    "action_mode": "watch",
                    "alignment": "aligned",
                    "primary_timeframe": "daily_then_intraday",
                    "rank_score": 94,
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
                    "waiting_for": ["daily close confirmation", "prior 2-minute bar high break"],
                    "invalidates_if": ["daily close loses prior-day low"],
                    "conflict_flags": [],
                },
                {
                    "ticker": "MRVL",
                    "action_mode": "ignore",
                    "alignment": "not_aligned",
                    "primary_timeframe": "daily_invalidated",
                    "rank_score": -30,
                    "thesis": "Daily swing structure is invalidated.",
                    "swing": {"state": "invalidated"},
                    "intraday": {"state": "not_in_play"},
                    "waiting_for": [],
                    "invalidates_if": [],
                    "conflict_flags": [],
                },
            ],
            "groups": {"watch": [{"ticker": "IBM"}], "ignore": [{"ticker": "MRVL"}]},
        }


def test_lance_desk_cycle_runs_advanced_scan_update_timeline_review_and_carryover():
    scan = FakeAdvancedScanService()
    update = FakeUpdateService()
    timeline = FakeTimelineService()
    review = FakeReviewService()
    carryover = FakeCarryoverService()
    unified = FakeUnifiedService()

    output = LanceDeskCycleService(
        scan_service=scan,
        update_service=update,
        timeline_service=timeline,
        review_service=review,
        carryover_service=carryover,
        unified_service=unified,
    ).run(
        tickers=["IBM", "MRVL"],
        max_candidates=2,
        session_id="requested-session",
        target_session_date="2026-07-02",
        update_limit=5,
        review_limit=6,
    )

    assert scan.calls == [{
        "tickers": ["IBM", "MRVL"],
        "universe": None,
        "watchlist": None,
        "all_universes": False,
        "min_gap_abs": 3.0,
        "max_candidates": 2,
        "persist": True,
        "session_id": "requested-session",
        "max_workers": 1,
        "include_caveated_context": False,
    }]
    assert update.calls == [{"session_id": "session-1", "limit": 5, "persist": True}]
    assert timeline.calls == [{"session_id": "session-1", "limit": 6}]
    assert review.calls == [{"session_id": "session-1", "limit": 6}]
    assert carryover.calls == [{
        "session_id": "session-1",
        "target_session_date": "2026-07-02",
        "limit": 6,
    }]
    assert output["status"] == "OK"
    assert output["session_id"] == "session-1"
    assert output["steps"] == [
        "run_advanced_lance_scan",
        "build_lance_unified_plan",
        "update_lance_watchlist",
        "get_lance_session_timeline",
        "review_lance_session",
        "build_lance_carryover_plan",
    ]
    assert unified.calls == [{
        "tickers": ["IBM", "MRVL"],
        "intraday_plans": {
            "IBM": {"ticker": "IBM", "state": "setup_forming"},
            "MRVL": {"ticker": "MRVL", "state": "not_in_play"},
        },
    }]
    assert output["scan_summary"] == {
        "status": "OK",
        "scanned_count": 20,
        "candidate_count": 2,
        "returned_watchlist_count": 2,
    }
    assert output["updates_summary"]["state_changed_count"] == 1
    assert output["unified_summary"] == {
        "status": "OK",
        "plan_count": 2,
        "watch_count": 1,
        "review_count": 0,
        "blocked_count": 0,
    }
    assert output["unified_plans"][0]["ticker"] == "IBM"
    assert output["unified_carryover"]["summary"] == {
        "carry_forward_count": 1,
        "manual_review_count": 0,
        "blocked_count": 0,
        "ignore_count": 1,
    }
    assert output["unified_carryover"]["groups"]["carry_forward"][0]["ticker"] == "IBM"
    assert output["unified_carryover"]["groups"]["ignore"][0]["ticker"] == "MRVL"
    assert output["top_watchlist"][0]["ticker"] == "IBM"
    assert output["top_watchlist"][0]["action_mode"] == "watch"
    assert output["top_watchlist"][0]["swing_state"] == "active_watch"
    assert output["top_watchlist"][0]["intraday_state"] == "waiting_for_turn"
    assert output["review_summary"]["pending_count"] == 1
    assert output["carryover_summary"]["carryover_count"] == 1
    assert output["top_updates"][0]["ticker"] == "IBM"
    assert output["pending_reviews"][0]["ticker"] == "IBM"


def test_lance_desk_cycle_defaults_to_all_universes_and_skips_timeline_without_session():
    scan = FakeAdvancedScanService()

    def scan_without_session(**kwargs):
        scan.calls.append(kwargs)
        return {
            "agent_name": "lance_intraday",
            "mode": "advanced",
            "status": "EMPTY",
            "watchlist": [],
            "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
        }

    scan.scan = scan_without_session

    output = LanceDeskCycleService(
        scan_service=scan,
        update_service=FakeUpdateService(),
        timeline_service=FakeTimelineService(),
        review_service=FakeReviewService(),
        carryover_service=FakeCarryoverService(),
        unified_service=FakeUnifiedService(),
    ).run()

    assert scan.calls[0]["all_universes"] is True
    assert scan.calls[0]["persist"] is True
    assert output["status"] == "EMPTY"
    assert output["session_id"] is None
    assert output["timeline_summary"]["status"] == "EMPTY"
    assert output["timeline_summary"]["event_count"] == 0
