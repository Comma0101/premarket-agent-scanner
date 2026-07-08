from __future__ import annotations

from services.lance_ticker_explain_service import LanceTickerExplainService


def _payload() -> dict:
    return {
        "mode": "command_center",
        "session_banner": "MARKET_CLOSED, Jul 3 10:00 AM ET. US equity market closed.",
        "session_ids": {
            "intraday": "2026-07-03-lance-intraday",
            "swing": "2026-07-03-lance-swing",
        },
        "data_used": {
            "source_paths": [
                "full_cycle.market_context.benchmarks",
                "full_cycle.combined_watchlist",
            ],
            "benchmarks": [
                {
                    "ticker": "SPY",
                    "gap_pct": -0.23,
                    "gap_basis": "last_trade",
                    "confidence": "STALE_DATA",
                    "as_of": "2026-07-02T20:00:00Z",
                    "sources": ["alpaca"],
                }
            ],
            "candidate_rows": [
                {
                    "ticker": "IBM",
                    "intraday_state": "triggered_reference",
                    "swing_state": "active_watch",
                    "intraday_playbook": "mean_reversion_after_capitulation",
                    "swing_playbook": "relative_strength_continuation",
                    "swing_bias": "long_bias",
                    "swing_bias_reason": "relative strength continuation is a long-bias swing watch.",
                    "latest_price": 189.25,
                    "gap_pct": 1.25,
                    "gap_basis": "premarket",
                    "confidence": "OK",
                    "data_status": "live",
                    "rel_volume": 4.2,
                    "rel_volume_basis": "session_volume_vs_average_daily_volume",
                    "volume": 1250000,
                    "as_of": None,
                    "as_of_et": "Jul 3 9:45 AM ET",
                    "sources": ["alpaca", "yfinance"],
                    "data_caveat": None,
                },
                {
                    "ticker": "AAOI",
                    "intraday_state": "blocked_data_quality",
                    "swing_state": None,
                    "intraday_playbook": None,
                    "swing_playbook": None,
                    "latest_price": None,
                    "gap_pct": None,
                    "gap_basis": "last_trade",
                    "confidence": "STALE_DATA",
                    "data_status": "stale",
                    "rel_volume": None,
                    "rel_volume_basis": None,
                    "volume": None,
                    "as_of": None,
                    "as_of_et": "Jul 2 4:00 PM ET",
                    "sources": [],
                    "data_caveat": "POST_MARKET: last_trade / STALE_DATA.",
                },
            ],
        },
        "selection_audit": {
            "requested_tickers": ["IBM", "AAOI", "ARM"],
            "returned_tickers": ["IBM", "AAOI"],
            "omitted_tickers": [
                {
                    "ticker": "ARM",
                    "stage": "source_rows",
                    "present_in": [],
                    "reason": "Requested ticker did not appear in Lance intraday or swing source rows.",
                }
            ],
        },
        "full_cycle": {
            "top_intraday_watchlist": [
                {
                    "ticker": "IBM",
                    "state": "triggered_reference",
                    "playbook": "mean_reversion_after_capitulation",
                    "waiting_for": ["hold above prior 2-minute high"],
                    "invalidates_if": ["breaks prior 2-minute low"],
                    "thesis": "Right-side turn confirmed after capitulation.",
                }
            ],
            "top_swing_watchlist": [
                {
                    "ticker": "IBM",
                    "state": "active_watch",
                    "playbook": "relative_strength_continuation",
                    "bias": "long_bias",
                    "bias_reason": "relative strength continuation is a long-bias swing watch.",
                    "waiting_for": ["daily continuation above prior high"],
                    "invalidates_if": ["daily close loses reclaim level"],
                    "state_reason": "Daily relative strength is holding.",
                }
            ],
        },
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def test_lance_ticker_explain_returns_found_evidence_card():
    output = LanceTickerExplainService().explain(ticker="ibm", payload=_payload())

    assert output["mode"] == "ticker_explain"
    assert output["status"] == "FOUND"
    assert output["ticker"] == "IBM"
    assert output["summary"] == (
        "IBM is in Lance output: intraday=triggered_reference, swing=active_watch, "
        "confidence=OK, gap_basis=premarket."
    )
    assert output["data_quality"] == {
        "latest_price": 189.25,
        "gap_pct": 1.25,
        "gap_basis": "premarket",
        "confidence": "OK",
        "data_status": "live",
        "rel_volume": 4.2,
        "rel_volume_basis": "session_volume_vs_average_daily_volume",
        "volume": 1250000,
        "as_of": None,
        "as_of_et": "Jul 3 9:45 AM ET",
        "sources": ["alpaca", "yfinance"],
        "data_caveat": None,
    }
    assert output["intraday"]["waiting_for"] == ["hold above prior 2-minute high"]
    assert output["lance_state"]["swing_bias"] == "long_bias"
    assert output["swing"]["bias"] == "long_bias"
    assert output["swing"]["invalidates_if"] == ["daily close loses reclaim level"]
    assert output["benchmark_context"][0]["ticker"] == "SPY"
    assert output["source_paths"] == [
        "data_used.candidate_rows",
        "full_cycle.top_intraday_watchlist",
        "full_cycle.top_swing_watchlist",
    ]


def test_lance_ticker_explain_returns_omitted_reason():
    output = LanceTickerExplainService().explain(ticker="ARM", payload=_payload())

    assert output["status"] == "OMITTED"
    assert output["ticker"] == "ARM"
    assert output["omitted_reason"] == {
        "ticker": "ARM",
        "stage": "source_rows",
        "present_in": [],
        "reason": "Requested ticker did not appear in Lance intraday or swing source rows.",
    }
    assert output["summary"] == (
        "ARM was requested but omitted at source_rows: Requested ticker did not appear "
        "in Lance intraday or swing source rows."
    )


def test_lance_ticker_explain_returns_not_found_when_not_requested_or_returned():
    output = LanceTickerExplainService().explain(ticker="XYZ", payload=_payload())

    assert output["status"] == "NOT_FOUND"
    assert output["summary"] == "XYZ was not found in Lance output or requested ticker audit."
