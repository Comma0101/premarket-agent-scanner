from __future__ import annotations

from app.db import (
    get_latest_lance_session_id,
    get_lance_watchlist_events,
    initialize_database,
    insert_lance_watchlist_event,
    upsert_lance_watchlist_item,
)
from services.lance_session_timeline_service import LanceSessionTimelineService


def test_lance_watchlist_events_are_append_only_and_ordered(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)

    insert_lance_watchlist_event(
        db_path,
        session_id="session-1",
        ticker="NVDA",
        event_type="scan",
        state="watching",
        score=45,
        data_quality={"gap_pct": 4.0, "rel_volume": 1.2, "confidence": "OK"},
        payload={"why_watching": "initial"},
    )
    insert_lance_watchlist_event(
        db_path,
        session_id="session-1",
        ticker="NVDA",
        event_type="update",
        state="triggered_reference",
        score=95,
        data_quality={"gap_pct": 6.0, "rel_volume": 3.8, "confidence": "OK"},
        payload={"change_flags": ["state_changed", "rvol_expanded"]},
    )

    events = get_lance_watchlist_events(db_path, session_id="session-1", ticker="NVDA")

    assert [event["event_type"] for event in events] == ["scan", "update"]
    assert events[0]["payload"]["why_watching"] == "initial"
    assert events[1]["state"] == "triggered_reference"
    assert events[1]["data_quality"]["rel_volume"] == 3.8


def test_lance_session_timeline_groups_events_by_ticker(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    insert_lance_watchlist_event(
        db_path,
        session_id="session-1",
        ticker="NVDA",
        event_type="scan",
        state="watching",
        score=45,
        data_quality={"gap_pct": 4.0},
        payload={"why_watching": "initial"},
    )
    insert_lance_watchlist_event(
        db_path,
        session_id="session-1",
        ticker="AMD",
        event_type="scan",
        state="not_in_play",
        score=20,
        data_quality={"gap_pct": 3.0},
        payload={"why_watching": "initial"},
    )
    insert_lance_watchlist_event(
        db_path,
        session_id="session-1",
        ticker="NVDA",
        event_type="update",
        state="setup_forming",
        score=70,
        data_quality={"gap_pct": 5.0},
        payload={"change_flags": ["score_improved"]},
    )

    output = LanceSessionTimelineService(db_path=db_path).timeline(session_id="session-1")

    assert output["status"] == "OK"
    assert output["session_id"] == "session-1"
    assert output["event_count"] == 3
    assert [row["ticker"] for row in output["tickers"]] == ["NVDA", "AMD"]
    assert output["tickers"][0]["first_state"] == "watching"
    assert output["tickers"][0]["latest_state"] == "setup_forming"
    assert output["tickers"][0]["score_delta"] == 25
    assert len(output["tickers"][0]["events"]) == 2


def test_latest_lance_session_can_filter_by_session_suffix(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    upsert_lance_watchlist_item(
        db_path,
        session_id="2026-07-02-lance-intraday",
        ticker="IBM",
        state="watching",
        score=40,
        playbook="mean_reversion_after_capitulation",
        why_watching="IBM",
        invalidates_if=None,
        next_step=None,
        data_quality={"confidence": "OK"},
        plan={"ticker": "IBM"},
    )
    upsert_lance_watchlist_item(
        db_path,
        session_id="2026-07-02-lance-swing",
        ticker="MU",
        state="mean_reversion_watch",
        score=75,
        playbook="swing_mean_reversion_reclaim",
        why_watching="MU",
        invalidates_if=None,
        next_step=None,
        data_quality={"confidence": "OK"},
        plan={"ticker": "MU"},
    )

    assert get_latest_lance_session_id(db_path) == "2026-07-02-lance-swing"
    assert (
        get_latest_lance_session_id(db_path, session_id_suffix="-lance-swing")
        == "2026-07-02-lance-swing"
    )
    assert (
        get_latest_lance_session_id(db_path, exclude_session_id_suffix="-lance-swing")
        == "2026-07-02-lance-intraday"
    )
