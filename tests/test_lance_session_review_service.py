from __future__ import annotations

from app.db import (
    initialize_database,
    insert_lance_outcome,
    insert_lance_watchlist_event,
    upsert_lance_watchlist_item,
)
from services.lance_session_review_service import LanceSessionReviewService


def test_lance_session_review_builds_pending_review_queue(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    insert_lance_watchlist_event(
        db_path,
        session_id="session-1",
        ticker="OPEN",
        event_type="scan",
        state="not_in_play",
        score=70,
        data_quality={
            "gap_pct": 9.5,
            "rel_volume": 1.6,
            "confidence": "OK",
            "gap_basis": "last_trade",
            "as_of_et": "Jul 1 1:00 PM ET",
        },
        payload={"playbook": "watchlist_context", "why_watching": "OPEN initial"},
    )
    insert_lance_watchlist_event(
        db_path,
        session_id="session-1",
        ticker="OPEN",
        event_type="update",
        state="setup_forming",
        score=85,
        data_quality={
            "gap_pct": 10.0,
            "rel_volume": 3.2,
            "confidence": "OK",
            "gap_basis": "last_trade",
            "as_of_et": "Jul 1 1:30 PM ET",
        },
        payload={
            "playbook": "mean_reversion_after_capitulation",
            "change_flags": ["state_changed", "rvol_expanded"],
        },
    )
    insert_lance_watchlist_event(
        db_path,
        session_id="session-1",
        ticker="MRVL",
        event_type="scan",
        state="not_in_play",
        score=40,
        data_quality={
            "gap_pct": -7.0,
            "rel_volume": 0.4,
            "confidence": "OK",
            "gap_basis": "last_trade",
            "as_of_et": "Jul 1 1:00 PM ET",
        },
        payload={"playbook": "watchlist_context", "why_watching": "MRVL initial"},
    )
    insert_lance_outcome(
        db_path,
        session_id="session-1",
        ticker="MRVL",
        playbook="watchlist_context",
        outcome="unknown",
        notes="Reviewed manually.",
        plan={"ticker": "MRVL"},
    )

    output = LanceSessionReviewService(db_path=db_path).review(session_id="session-1")

    assert output["status"] == "OK"
    assert output["session_id"] == "session-1"
    assert output["ticker_count"] == 2
    assert output["pending_count"] == 1
    assert output["reviewed_count"] == 1
    pending = output["pending_reviews"][0]
    assert pending["ticker"] == "OPEN"
    assert pending["latest_state"] == "setup_forming"
    assert pending["suggested_outcome"] == "unknown"
    assert pending["journal_args"] == {
        "session_id": "session-1",
        "ticker": "OPEN",
        "playbook": "mean_reversion_after_capitulation",
        "outcome": "unknown",
    }
    assert "rvol_expanded" in pending["review_focus"]
    assert output["reviewed"][0]["ticker"] == "MRVL"


def test_lance_session_review_empty_when_no_events(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)

    output = LanceSessionReviewService(db_path=db_path).review(session_id="session-1")

    assert output["status"] == "EMPTY"
    assert output["pending_reviews"] == []


def test_lance_session_review_default_ignores_latest_swing_session(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    for session_id, ticker, playbook in [
        ("2026-07-02-lance-intraday", "IBM", "mean_reversion_after_capitulation"),
        ("2026-07-02-lance-swing", "MU", "swing_mean_reversion_reclaim"),
    ]:
        upsert_lance_watchlist_item(
            db_path,
            session_id=session_id,
            ticker=ticker,
            state="watching",
            score=60,
            playbook=playbook,
            why_watching=ticker,
            invalidates_if=None,
            next_step=None,
            data_quality={"confidence": "OK"},
            plan={"ticker": ticker, "playbook": playbook},
        )
        insert_lance_watchlist_event(
            db_path,
            session_id=session_id,
            ticker=ticker,
            event_type="scan",
            state="watching",
            score=60,
            data_quality={"confidence": "OK"},
            payload={"playbook": playbook},
        )

    output = LanceSessionReviewService(db_path=db_path).review()

    assert output["status"] == "OK"
    assert output["session_id"] == "2026-07-02-lance-intraday"
    assert output["pending_reviews"][0]["ticker"] == "IBM"
