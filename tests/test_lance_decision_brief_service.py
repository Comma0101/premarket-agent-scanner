from __future__ import annotations

from services.lance_decision_brief_service import LanceDecisionBriefService


def _blocked_payload() -> dict:
    return {
        "mode": "command_center",
        "session_banner": "MARKET_CLOSED, Jul 3 9:28 PM ET. US equity market closed.",
        "session_context": {
            "session_mode": "MARKET_CLOSED",
            "market_closed_reason": "Independence Day observed",
            "is_market_open": False,
        },
        "single_run_read": {
            "active_monitor": [],
            "swing_watch": [],
            "blocked_data_quality": ["MU", "IBM"],
            "one_liner": "0 active monitors, 0 swing watches, 2 blocked/data-caveat names, 0 pending reviews.",
        },
        "data_doctor": {
            "doctor_read": {
                "one_liner": "0 ready, 2 blocked. Main blockers: stale_or_off_session=2."
            },
            "root_causes": {
                "stale_or_off_session": ["MU", "IBM"],
                "confidence": ["MU", "IBM"],
            },
            "next_actions": ["Resolve stale/off-session data before treating rows as live."],
        },
        "data_used": {
            "candidate_rows": [
                {
                    "ticker": "MU",
                    "intraday_state": "blocked",
                    "swing_state": "mean_reversion_watch",
                    "swing_playbook": "swing_mean_reversion_reclaim",
                    "latest_price": 974.23,
                    "gap_pct": -5.62,
                    "gap_basis": "last_trade",
                    "confidence": "STALE_DATA",
                    "data_status": "stale",
                    "rel_volume": 1.19,
                    "as_of_et": "Jul 2 4:00 PM ET",
                    "sources": ["yfinance", "alpaca"],
                    "data_caveat": "POST_MARKET: last_trade / STALE_DATA.",
                },
            ],
        },
        "selection_audit": {
            "omitted_tickers": [
                {
                    "ticker": "ARM",
                    "stage": "source_rows",
                    "reason": "Requested ticker did not appear in Lance intraday or swing source rows.",
                }
            ]
        },
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def _active_payload() -> dict:
    return {
        "mode": "command_center",
        "session_banner": "MARKET_OPEN, Jul 6 10:15 AM ET. Regular session.",
        "session_context": {"session_mode": "MARKET_OPEN", "is_market_open": True},
        "single_run_read": {
            "active_monitor": ["IBM"],
            "swing_watch": ["HOOD"],
            "blocked_data_quality": [],
            "one_liner": "1 active monitor, 1 swing watch, 0 blocked/data-caveat names, 0 pending reviews.",
        },
        "data_doctor": {
            "doctor_read": {"one_liner": "2 ready, 0 blocked."},
            "root_causes": {"ready": ["IBM", "HOOD"]},
            "next_actions": [],
        },
        "data_used": {
            "candidate_rows": [
                {
                    "ticker": "IBM",
                    "intraday_state": "triggered_reference",
                    "swing_state": "active_watch",
                    "intraday_playbook": "mean_reversion_after_capitulation",
                    "swing_playbook": "relative_strength_continuation",
                    "latest_price": 189.25,
                    "gap_pct": 1.25,
                    "gap_basis": "premarket",
                    "confidence": "OK",
                    "data_status": "live",
                    "rel_volume": 4.2,
                    "as_of_et": "Jul 6 10:15 AM ET",
                    "sources": ["alpaca"],
                    "data_caveat": None,
                }
            ],
        },
        "full_cycle": {
            "top_intraday_watchlist": [
                {
                    "ticker": "IBM",
                    "state": "triggered_reference",
                    "playbook": "mean_reversion_after_capitulation",
                    "thesis": "Right-side turn after capitulation.",
                    "waiting_for": ["hold above prior 2-minute high"],
                    "invalidates_if": ["breaks prior 2-minute low"],
                }
            ],
            "top_swing_watchlist": [
                {
                    "ticker": "HOOD",
                    "state": "active_watch",
                    "playbook": "relative_strength_continuation",
                    "state_reason": "Daily relative strength is holding.",
                    "waiting_for": ["continuation above prior high"],
                    "invalidates_if": ["daily close loses reclaim level"],
                }
            ],
        },
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def test_decision_brief_stands_down_when_market_closed_and_data_blocked():
    output = LanceDecisionBriefService().build(_blocked_payload())

    assert output["mode"] == "decision_brief"
    assert output["lance_posture"] == "stand_down"
    assert output["headline"] == (
        "Stand down: market is closed and 2 ticker(s) are blocked by data quality."
    )
    assert output["focus"] == []
    assert output["blocked"][0] == {
        "ticker": "MU",
        "reason": "confidence=STALE_DATA / gap_basis=last_trade / status=stale",
        "caveat": "POST_MARKET: last_trade / STALE_DATA.",
    }
    assert output["omitted"][0]["ticker"] == "ARM"
    assert output["what_would_change"] == [
        "Resolve stale/off-session data before treating rows as live.",
        "Market must be open or a fresh premarket print must be available before live Lance upgrades.",
    ]
    assert output["talk_track"][0] == (
        "No Lance live action context: market is closed and current rows are caveated."
    )


def test_decision_brief_summarizes_active_monitor_with_confirmation_and_invalidation():
    output = LanceDecisionBriefService().build(_active_payload())

    assert output["lance_posture"] == "monitor"
    assert output["headline"] == "Monitor 1 active ticker(s); 1 swing watch(es); 0 blocked."
    assert output["focus"][0] == {
        "ticker": "IBM",
        "lane": "intraday",
        "state": "triggered_reference",
        "playbook": "mean_reversion_after_capitulation",
        "why": "Right-side turn after capitulation.",
        "waiting_for": ["hold above prior 2-minute high"],
        "invalidates_if": ["breaks prior 2-minute low"],
        "data_quality": "confidence=OK / gap_basis=premarket / as_of=Jul 6 10:15 AM ET",
    }
    assert output["swing_watch"][0]["ticker"] == "HOOD"
    assert output["what_would_change"] == [
        "IBM: breaks prior 2-minute low",
        "HOOD: daily close loses reclaim level",
    ]
    assert output["talk_track"][0] == (
        "Lance focus is IBM: triggered_reference under mean_reversion_after_capitulation."
    )
