from __future__ import annotations

from services.lance_command_center_service import LanceCommandCenterService


class FakeFullCycleService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_full_cycle",
            "mode": "full_cycle",
            "status": "OK",
            "session_ids": {
                "intraday": "2026-07-03-lance-intraday",
                "swing": "2026-07-03-lance-swing",
            },
            "session_banner": (
                "MARKET_CLOSED, Jul 3 10:00 AM ET. US equity market closed: "
                "Independence Day observed."
            ),
            "session_context": {
                "session_mode": "MARKET_CLOSED",
                "as_of_et": "Jul 3 10:00 AM ET",
                "trading_date": "2026-07-03",
                "is_market_open": False,
                "is_market_holiday": True,
                "market_closed_reason": "Independence Day observed",
            },
            "selection_audit": {
                "requested_tickers": ["IBM", "MU", "AAOI", "ARM"],
                "returned_tickers": ["IBM", "MU", "AAOI"],
                "omitted_tickers": [{"ticker": "ARM", "reason": "filtered out"}],
            },
            "session_workflow": {
                "review_command": (
                    ".venv/bin/python -m cli.lance_full_cycle_eod review "
                    "--intraday-session-id 2026-07-03-lance-intraday "
                    "--swing-session-id 2026-07-03-lance-swing"
                ),
                "journal_tool": "journal_lance_full_cycle_outcome",
            },
            "desk_read": {
                "one_liner": "1 intraday focus, 1 swing watch, 1 blocked/data-caveat, 0 swing carryover.",
                "intraday_focus": [{"ticker": "IBM"}],
                "swing_watch": [{"ticker": "MU"}],
                "blocked_data_quality": [{"ticker": "AAOI"}],
            },
            "summary": {
                "intraday_candidate_count": 3,
                "intraday_pending_review_count": 1,
                "swing_plan_count": 3,
                "combined_ticker_count": 3,
            },
            "market_context": {
                "benchmarks": {
                    "SPY": {
                        "gap_pct": 0.42,
                        "gap_basis": "premarket",
                        "confidence": "OK",
                        "as_of": "2026-07-03T13:30:00Z",
                        "sources": ["alpaca"],
                    }
                }
            },
            "combined_watchlist": [
                _combined_row(
                    "IBM",
                    intraday_state="triggered_reference",
                    swing_state=None,
                    confidence="OK",
                    gap_basis="premarket",
                    as_of_et="Jul 3 9:45 AM ET",
                    data_status="live",
                    rel_volume=4.2,
                    latest_price=189.25,
                    gap_pct=1.25,
                    sources=["alpaca", "yfinance"],
                ),
                _combined_row(
                    "MU",
                    intraday_state=None,
                    swing_state="mean_reversion_watch",
                    confidence="OK",
                    gap_basis="last_trade",
                    as_of_et="Jul 3 9:45 AM ET",
                    data_status="live",
                    rel_volume=2.5,
                    latest_price=118.40,
                    gap_pct=-0.85,
                    sources=["alpaca"],
                ),
                _combined_row(
                    "AAOI",
                    intraday_state="blocked_data_quality",
                    swing_state=None,
                    confidence="STALE_DATA",
                    gap_basis="last_trade",
                    as_of_et="Jul 2 4:00 PM ET",
                    data_status="stale",
                    rel_volume=None,
                    latest_price=None,
                    gap_pct=None,
                    sources=[],
                ),
            ],
            "pending_reviews": [
                {
                    "ticker": "IBM",
                    "lane": "intraday",
                    "playbook": "mean_reversion_after_capitulation",
                    "suggested_outcome": "unknown",
                }
            ],
            "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
        }


class FakeTrackerService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def diff(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_full_cycle",
            "mode": "session_tracker",
            "status": "OK",
            "one_liner": "1 new, 0 upgraded, 0 downgraded, 0 unchanged, 0 removed, 0 data caveats.",
            "summary": {"new_count": 1},
            "groups": {"new": [{"ticker": "IBM"}]},
            "data_caveats": [],
            "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
        }


class EmptyFullCycleService:
    def run(self, **kwargs):
        return {
            "agent_name": "lance_full_cycle",
            "mode": "full_cycle",
            "status": "OK",
            "session_ids": {
                "intraday": "empty-intraday",
                "swing": "empty-swing",
            },
            "combined_watchlist": [],
            "pending_reviews": [],
            "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
        }


def _combined_row(
    ticker: str,
    *,
    intraday_state: str | None,
    swing_state: str | None,
    confidence: str,
    gap_basis: str,
    as_of_et: str,
    data_status: str,
    rel_volume: float | None,
    latest_price: float | None,
    gap_pct: float | None,
    sources: list[str],
) -> dict:
    return {
        "ticker": ticker,
        "lanes": ["intraday"] if intraday_state else ["swing"],
        "intraday_state": intraday_state,
        "swing_state": swing_state,
        "data_quality": {
            "confidence": confidence,
            "gap_basis": gap_basis,
            "as_of_et": as_of_et,
            "data_status": data_status,
            "rel_volume": rel_volume,
            "latest_price": latest_price,
            "gap_pct": gap_pct,
            "sources": sources,
        },
    }


def test_lance_command_center_runs_full_cycle_and_builds_single_read():
    full_cycle = FakeFullCycleService()
    tracker = FakeTrackerService()

    output = LanceCommandCenterService(
        full_cycle_service=full_cycle,
        tracker_service=tracker,
    ).run(
        tickers="IBM,MU,AAOI",
        previous={"combined_watchlist": []},
        persist=True,
        target_session_date="2026-07-06",
        summary_limit=3,
    )

    assert full_cycle.calls[0]["tickers"] == "IBM,MU,AAOI"
    assert full_cycle.calls[0]["persist"] is True
    assert full_cycle.calls[0]["target_session_date"] == "2026-07-06"
    assert tracker.calls[0]["previous"] == {"combined_watchlist": []}

    assert output["agent_name"] == "lance_full_cycle"
    assert output["mode"] == "command_center"
    assert output["status"] == "OK"
    assert output["session_banner"].startswith("MARKET_CLOSED, Jul 3 10:00 AM ET")
    assert output["session_context"]["market_closed_reason"] == "Independence Day observed"
    assert output["selection_audit"]["omitted_tickers"] == [{"ticker": "ARM", "reason": "filtered out"}]
    assert output["single_run_read"]["one_liner"] == (
        "1 active monitor, 1 swing watch, 1 blocked/data-caveat, 1 pending review."
    )
    assert output["single_run_read"]["active_monitor"] == ["IBM"]
    assert output["single_run_read"]["swing_watch"] == ["MU"]
    assert output["single_run_read"]["blocked_data_quality"] == ["AAOI"]
    assert output["data_doctor"]["doctor_read"]["one_liner"] == (
        "2 ready, 1 blocked. Main blockers: stale_or_off_session=1."
    )
    assert output["data_doctor"]["root_causes"]["ready"] == ["IBM", "MU"]
    assert output["data_doctor"]["root_causes"]["stale_or_off_session"] == ["AAOI"]
    assert output["decision_brief"]["mode"] == "decision_brief"
    assert output["decision_brief"]["lance_posture"] == "stand_down"
    assert output["decision_brief"]["headline"] == (
        "Stand down: market is closed and 1 ticker(s) are blocked by data quality."
    )
    assert output["decision_brief"]["focus"][0]["ticker"] == "IBM"
    assert output["decision_brief"]["swing_watch"][0]["ticker"] == "MU"
    assert output["decision_brief"]["blocked"][0]["ticker"] == "AAOI"
    assert output["tracker"]["one_liner"].startswith("1 new")
    assert output["tomorrow_prep"]["fresh_scan_required"] is True
    assert output["tomorrow_prep"]["watchlist"] == ["IBM", "MU", "AAOI"]
    assert output["outcome_loop"]["pending_review_count"] == 1
    assert output["outcome_loop"]["pending_review_tickers"] == ["IBM"]
    assert output["outcome_loop"]["journal_commands"] == [
        "journal_lance_full_cycle_outcome lane=intraday ticker=IBM playbook=mean_reversion_after_capitulation outcome=unknown"
    ]
    assert output["outcome_loop"]["review_command"].startswith(
        ".venv/bin/python -m cli.lance_full_cycle_eod review"
    )
    assert output["outcome_loop"]["journal_tool"] == "journal_lance_full_cycle_outcome"
    assert output["workflow_commands"]["now"].startswith(".venv/bin/python -m cli.lance")
    assert output["workflow_commands"]["watch"].startswith(".venv/bin/python -m cli.lance_full_cycle")
    assert output["workflow_commands"]["explain"] == (
        ".venv/bin/python -m cli.lance_explain <TICKER> --payload data/live_sessions/latest_command_center.json"
    )
    assert output["workflow_commands"]["tomorrow"].startswith(".venv/bin/python -m cli.lance_dashboard tomorrow")
    assert output["data_used"]["summary"] == "3 candidate rows, 1 benchmark row."
    assert output["data_used"]["source_paths"] == [
        "full_cycle.market_context.benchmarks",
        "full_cycle.combined_watchlist",
    ]
    assert output["data_used"]["benchmarks"] == [
        {
            "ticker": "SPY",
            "gap_pct": 0.42,
            "gap_basis": "premarket",
            "confidence": "OK",
            "as_of": "2026-07-03T13:30:00Z",
            "sources": ["alpaca"],
        }
    ]
    ibm_data = output["data_used"]["candidate_rows"][0]
    assert ibm_data == {
        "ticker": "IBM",
        "intraday_state": "triggered_reference",
        "swing_state": None,
        "intraday_playbook": None,
        "swing_playbook": None,
        "latest_price": 189.25,
        "gap_pct": 1.25,
        "gap_basis": "premarket",
        "confidence": "OK",
        "data_status": "live",
        "rel_volume": 4.2,
        "volume": None,
        "as_of": None,
        "as_of_et": "Jul 3 9:45 AM ET",
        "sources": ["alpaca", "yfinance"],
        "data_caveat": None,
    }
    assert output["agent_handoff"] == {
        "summary": "1 active monitor, 1 swing watch, 1 blocked/data-caveat, 1 pending review.",
        "session_ids": {
            "intraday": "2026-07-03-lance-intraday",
            "swing": "2026-07-03-lance-swing",
        },
        "active_monitor": ["IBM"],
        "swing_watch": ["MU"],
        "blocked_data_quality": ["AAOI"],
        "data_doctor": "2 ready, 1 blocked. Main blockers: stale_or_off_session=1.",
        "data_used": output["data_used"],
        "session_banner": output["session_banner"],
        "selection_audit": output["selection_audit"],
        "decision_brief": output["decision_brief"],
        "pending_review_tickers": ["IBM"],
        "next_commands": output["workflow_commands"],
        "handoff_prompt": (
            "Use this block to brief another agent: preserve data-quality caveats, "
            "do not infer missing market numbers, and keep outcomes unknown until manual review."
        ),
    }

    signal = {row["ticker"]: row for row in output["signal_quality"]}
    assert signal["IBM"]["posture"] == "active_monitor"
    assert signal["IBM"]["rel_volume"] == 4.2
    assert signal["IBM"]["confidence"] == "OK"
    assert signal["IBM"]["gap_basis"] == "premarket"
    assert signal["MU"]["posture"] == "swing_watch"
    assert signal["AAOI"]["posture"] == "blocked_data_quality"
    assert "confidence=STALE_DATA" in signal["AAOI"]["quality_reason"]


def test_lance_command_center_without_previous_skips_tracker():
    output = LanceCommandCenterService(
        full_cycle_service=FakeFullCycleService(),
        tracker_service=FakeTrackerService(),
    ).run(tickers="IBM")

    assert output["tracker"] is None
    assert output["single_run_read"]["pending_review_count"] == 1


def test_lance_command_center_uses_readable_plural_labels():
    output = LanceCommandCenterService(
        full_cycle_service=EmptyFullCycleService(),
        tracker_service=FakeTrackerService(),
    ).run(tickers="IBM")

    assert output["single_run_read"]["one_liner"] == (
        "0 active monitors, 0 swing watches, 0 blocked/data-caveat names, 0 pending reviews."
    )


def test_lance_command_center_accepts_prior_command_center_payload_for_tracking():
    tracker = FakeTrackerService()

    output = LanceCommandCenterService(
        full_cycle_service=FakeFullCycleService(),
        tracker_service=tracker,
    ).run(
        tickers="IBM",
        previous={
            "mode": "command_center",
            "full_cycle": {
                "session_ids": {"intraday": "previous-intraday"},
                "combined_watchlist": [],
            },
        },
    )

    assert output["tracker"]["mode"] == "session_tracker"
    assert tracker.calls[0]["previous"] == {
        "session_ids": {"intraday": "previous-intraday"},
        "combined_watchlist": [],
    }
