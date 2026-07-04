from __future__ import annotations

from services.lance_full_cycle_service import LanceFullCycleService


class FakeDeskCycleService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_intraday",
            "mode": "desk_cycle",
            "status": "OK",
            "session_id": "2026-07-02-lance-intraday",
            "scan_summary": {"candidate_count": 2, "scanned_count": 20},
            "unified_summary": {"plan_count": 2, "watch_count": 1},
            "updates_summary": {"updated_count": 2, "state_changed_count": 1},
            "review_summary": {"pending_count": 1, "reviewed_count": 0},
            "carryover_summary": {"carryover_count": 1},
            "market_context": {"theme_rotation": [{"theme": "AI_SEMIS_MEMORY"}]},
            "top_watchlist": [
                {
                    "ticker": "IBM",
                    "state": "triggered_reference",
                    "score": 92,
                    "playbook": "mean_reversion_after_capitulation",
                    "data_quality": {
                        "confidence": "OK",
                        "gap_basis": "last_trade",
                        "as_of_et": "Jul 2 3:45 PM ET",
                    },
                }
            ],
            "top_updates": [{"ticker": "IBM", "current_state": "triggered_reference"}],
            "pending_reviews": [{"ticker": "IBM", "suggested_outcome": "unknown"}],
            "carryover_groups": {"strength_carryover": [{"ticker": "IBM"}]},
            "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
        }


class FakeSwingCycleService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_swing",
            "mode": "swing_cycle",
            "status": "OK",
            "session_id": "2026-07-02-lance-swing",
            "selection": "AI_SEMIS_MEMORY,WATCHLIST:HOT_ACTIVE",
            "selection_count": 3,
            "summary": {
                "plan_count": 3,
                "active_watch_count": 1,
                "mean_reversion_watch_count": 1,
                "watching_count": 1,
                "invalidated_count": 0,
                "blocked_count": 0,
            },
            "groups": {"mean_reversion_watch": [{"ticker": "MU"}]},
            "top_watchlist": [
                {
                    "ticker": "MU",
                    "state": "mean_reversion_watch",
                    "score": 55,
                    "playbook": "swing_mean_reversion_reclaim",
                    "data_quality": {
                        "confidence": "STALE_DATA",
                        "gap_basis": "last_trade",
                        "as_of_et": "Jul 2 4:00 PM ET",
                    },
                },
                {
                    "ticker": "IBM",
                    "state": "active_watch",
                    "score": 35,
                    "playbook": "relative_strength_continuation",
                    "data_quality": {
                        "confidence": "OK",
                        "gap_basis": "last_trade",
                        "as_of_et": "Jul 2 3:45 PM ET",
                    },
                },
            ],
            "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
        }


class FakeSwingCarryoverService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_intraday",
            "strategy": "Lance carryover plan",
            "source_session_id": kwargs["session_id"],
            "target_session_date": kwargs["target_session_date"],
            "status": "OK",
            "carryover_count": 1,
            "fresh_scan_required": True,
            "groups": {
                "swing_mean_reversion_carryover": [
                    {
                        "ticker": "MU",
                        "playbook": "swing_mean_reversion_reclaim",
                        "latest_state": "mean_reversion_watch",
                    }
                ],
                "swing_continuation_carryover": [],
                "strength_carryover": [],
                "weakness_carryover": [],
                "context_only": [],
            },
        }


class EmptyDeskCycleService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_intraday",
            "mode": "desk_cycle",
            "status": "OK",
            "session_id": "2026-07-02-empty-intraday",
            "scan_summary": {"candidate_count": 0, "scanned_count": 20},
            "updates_summary": {"updated_count": 0},
            "review_summary": {"pending_count": 0, "reviewed_count": 0},
            "market_context": {},
            "top_watchlist": [],
            "top_updates": [],
            "pending_reviews": [],
            "carryover_groups": {},
            "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
        }


class NoCallSwingCycleService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        raise AssertionError("swing cycle should be skipped when triage is empty")


def test_lance_full_cycle_runs_intraday_and_swing_cycles_and_combines_by_ticker():
    desk = FakeDeskCycleService()
    swing = FakeSwingCycleService()
    swing_carryover = FakeSwingCarryoverService()

    output = LanceFullCycleService(
        desk_cycle_service=desk,
        swing_cycle_service=swing,
        swing_carryover_service=swing_carryover,
    ).run(
        universe="AI_SEMIS_MEMORY",
        watchlist="HOT_ACTIVE",
        min_gap_abs=2.5,
        max_candidates=7,
        persist=True,
        session_id="2026-07-02-lance-intraday",
        swing_session_id="2026-07-02-lance-swing",
        max_workers=3,
        lookback_days=80,
        update_limit=9,
        review_limit=11,
        target_session_date="2026-07-03",
        summary_limit=4,
    )

    assert desk.calls == [{
        "tickers": None,
        "universe": "AI_SEMIS_MEMORY",
        "watchlist": "HOT_ACTIVE",
        "all_universes": False,
        "min_gap_abs": 2.5,
        "max_candidates": 7,
        "persist": True,
        "session_id": "2026-07-02-lance-intraday",
        "max_workers": 3,
        "include_caveated_context": False,
        "update_limit": 9,
        "review_limit": 11,
        "target_session_date": "2026-07-03",
        "summary_limit": 4,
    }]
    assert swing.calls == [{
        "tickers": None,
        "universe": "AI_SEMIS_MEMORY",
        "watchlist": "HOT_ACTIVE",
        "all_universes": False,
        "lookback_days": 80,
        "persist": True,
        "session_id": "2026-07-02-lance-swing",
        "summary_limit": 4,
    }]
    assert swing_carryover.calls == [{
        "session_id": "2026-07-02-lance-swing",
        "target_session_date": "2026-07-03",
        "limit": 11,
    }]

    assert output["agent_name"] == "lance_full_cycle"
    assert output["mode"] == "full_cycle"
    assert output["status"] == "OK"
    assert output["session_ids"] == {
        "intraday": "2026-07-02-lance-intraday",
        "swing": "2026-07-02-lance-swing",
    }
    assert output["session_workflow"] == {
        "persisted": True,
        "full_universe": False,
        "include_caveated_context": False,
        "intraday_session_id": "2026-07-02-lance-intraday",
        "swing_session_id": "2026-07-02-lance-swing",
        "review_tool": "review_lance_full_cycle",
        "journal_tool": "journal_lance_full_cycle_outcome",
        "review_command": (
            ".venv/bin/python -m cli.lance_full_cycle_eod review "
            "--intraday-session-id 2026-07-02-lance-intraday "
            "--swing-session-id 2026-07-02-lance-swing"
        ),
        "journal_note": (
            "Journal observed outcomes only after manual chart review; use unknown when not reviewed."
        ),
    }
    assert output["summary"] == {
        "intraday_candidate_count": 2,
        "intraday_update_count": 2,
        "intraday_pending_review_count": 1,
        "swing_plan_count": 3,
        "swing_active_watch_count": 1,
        "swing_mean_reversion_watch_count": 1,
        "swing_carryover_count": 1,
        "combined_ticker_count": 2,
    }
    assert output["desk_read"] == {
        "one_liner": (
            "1 intraday focus, 0 swing watch, 1 blocked/data-caveat, "
            "1 swing carryover."
        ),
        "intraday_focus": [
            {
                "ticker": "IBM",
                "intraday_state": "triggered_reference",
                "swing_state": "active_watch",
                "confidence": "OK",
                "gap_basis": "last_trade",
                "as_of_et": "Jul 2 3:45 PM ET",
            }
        ],
        "swing_watch": [],
        "blocked_data_quality": [
            {
                "ticker": "MU",
                "intraday_state": None,
                "swing_state": "mean_reversion_watch",
                "confidence": "STALE_DATA",
                "gap_basis": "last_trade",
                "as_of_et": "Jul 2 4:00 PM ET",
            }
        ],
        "swing_carryover": [
            {
                "ticker": "MU",
                "bucket": "swing_mean_reversion_carryover",
                "playbook": "swing_mean_reversion_reclaim",
                "latest_state": "mean_reversion_watch",
            }
        ],
        "workflow_notes": [
            "Use intraday focus rows for live desk monitoring only when data quality stays OK.",
            "Swing watches still require their waiting_for conditions before upgrading.",
            "Carryover rows require a fresh scan before next-session decisions.",
        ],
    }
    assert output["top_intraday_watchlist"][0]["ticker"] == "IBM"
    assert output["top_swing_watchlist"][0]["ticker"] == "MU"
    assert "intraday" not in output
    assert "swing" not in output

    combined = {row["ticker"]: row for row in output["combined_watchlist"]}
    assert combined["IBM"]["lanes"] == ["intraday", "swing"]
    assert combined["IBM"]["intraday_state"] == "triggered_reference"
    assert combined["IBM"]["swing_state"] == "active_watch"


def test_lance_full_cycle_full_universe_uses_intraday_triage_for_swing_scope():
    desk = FakeDeskCycleService()
    swing = FakeSwingCycleService()
    swing_carryover = FakeSwingCarryoverService()

    output = LanceFullCycleService(
        desk_cycle_service=desk,
        swing_cycle_service=swing,
        swing_carryover_service=swing_carryover,
    ).run(
        all_universes=True,
        max_candidates=7,
        summary_limit=4,
    )

    assert desk.calls == [{
        "tickers": None,
        "universe": None,
        "watchlist": None,
        "all_universes": True,
        "min_gap_abs": 3.0,
        "max_candidates": 7,
        "persist": True,
        "session_id": None,
        "max_workers": 1,
        "include_caveated_context": True,
        "update_limit": 50,
        "review_limit": 500,
        "target_session_date": None,
        "summary_limit": 4,
    }]
    assert swing.calls == [{
        "tickers": ["IBM"],
        "universe": None,
        "watchlist": None,
        "all_universes": False,
        "lookback_days": 60,
        "persist": True,
        "session_id": None,
        "summary_limit": 4,
    }]
    assert output["session_workflow"]["full_universe"] is True
    assert output["session_workflow"]["triage_mode"] == "full_universe_intraday_first"
    assert output["session_workflow"]["swing_scope"] == "intraday_triage"
    assert output["session_workflow"]["swing_scope_count"] == 1
    assert output["session_workflow"]["include_caveated_context"] is True

    combined = {row["ticker"]: row for row in output["combined_watchlist"]}
    assert "intraday_row" not in combined["IBM"]
    assert "swing_row" not in combined["IBM"]
    assert combined["MU"]["lanes"] == ["swing"]
    assert combined["MU"]["swing_state"] == "mean_reversion_watch"
    assert "run_lance_desk_cycle" in output["steps"]
    assert "run_lance_swing_cycle" in output["steps"]
    assert "build_lance_swing_carryover_plan" in output["steps"]
    assert output["swing_carryover_summary"] == {
        "status": "OK",
        "carryover_count": 1,
        "fresh_scan_required": True,
    }
    assert (
        output["swing_carryover_groups"]["swing_mean_reversion_carryover"][0]["ticker"]
        == "MU"
    )
    assert output["handoff_prompt"]


def test_lance_full_cycle_full_universe_skips_swing_when_triage_is_empty():
    desk = EmptyDeskCycleService()
    swing = NoCallSwingCycleService()

    output = LanceFullCycleService(
        desk_cycle_service=desk,
        swing_cycle_service=swing,
    ).run(all_universes=True)

    assert swing.calls == []
    assert output["status"] == "PARTIAL"
    assert output["session_workflow"]["swing_scope_count"] == 0
    assert output["session_workflow"]["include_caveated_context"] is True
    assert output["session_workflow"]["triage_note"] == (
        "No intraday triage tickers passed the broad scan; swing deep analysis was skipped."
    )
    assert output["summary"]["swing_plan_count"] == 0
    assert output["top_swing_watchlist"] == []


def test_lance_full_cycle_defaults_to_all_universes_when_no_selector():
    desk = FakeDeskCycleService()
    swing = FakeSwingCycleService()

    output = LanceFullCycleService(
        desk_cycle_service=desk,
        swing_cycle_service=swing,
    ).run()

    assert desk.calls[0]["all_universes"] is True
    assert swing.calls[0]["tickers"] == ["IBM"]
    assert swing.calls[0]["all_universes"] is False
    assert output["session_workflow"]["triage_mode"] == "full_universe_intraday_first"
    assert output["status"] == "OK"


def test_lance_full_cycle_explains_requested_tickers_missing_from_output():
    output = LanceFullCycleService(
        desk_cycle_service=FakeDeskCycleService(),
        swing_cycle_service=FakeSwingCycleService(),
    ).run(
        tickers="IBM,MU,ARM",
        summary_limit=4,
    )

    assert output["selection_audit"] == {
        "requested_tickers": ["IBM", "MU", "ARM"],
        "returned_tickers": ["IBM", "MU"],
        "omitted_tickers": [
            {
                "ticker": "ARM",
                "reason": (
                    "Requested ticker did not appear in Lance's summarized combined watchlist; "
                    "it may have been filtered out, ranked below the summary limit, or blocked "
                    "before plan construction."
                ),
            }
        ],
    }
