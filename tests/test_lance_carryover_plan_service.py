from __future__ import annotations

from app.db import initialize_database, insert_lance_outcome, insert_lance_watchlist_event
from services.lance_carryover_plan_service import LanceCarryoverPlanService


def _event(
    db_path,
    *,
    ticker: str,
    gap_pct: float,
    rel_volume: float,
    state: str = "not_in_play",
    score: float = 50,
) -> None:
    insert_lance_watchlist_event(
        db_path,
        session_id="session-1",
        ticker=ticker,
        event_type="update",
        state=state,
        score=score,
        data_quality={
            "gap_pct": gap_pct,
            "rel_volume": rel_volume,
            "confidence": "OK",
            "gap_basis": "last_trade",
            "as_of_et": "Jul 1 1:45 PM ET",
            "sources": ["fake"],
        },
        payload={
            "playbook": "mean_reversion_after_capitulation",
            "change_flags": ["move_stalled"],
        },
    )


def test_lance_carryover_plan_groups_tomorrow_watchlist_without_inventing_outcomes(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    _event(db_path, ticker="OPEN", gap_pct=8.9, rel_volume=1.7, score=70)
    _event(db_path, ticker="AMAT", gap_pct=-10.8, rel_volume=1.0, score=65)
    _event(db_path, ticker="FIGR", gap_pct=3.2, rel_volume=0.6, score=35)
    _event(db_path, ticker="MRVL", gap_pct=-7.6, rel_volume=0.4, score=35)
    insert_lance_outcome(
        db_path,
        session_id="session-1",
        ticker="MRVL",
        playbook="mean_reversion_after_capitulation",
        outcome="unknown",
        notes="Already reviewed.",
        plan={"ticker": "MRVL"},
    )

    output = LanceCarryoverPlanService(db_path=db_path).build(
        session_id="session-1",
        target_session_date="2026-07-02",
    )

    assert output["status"] == "OK"
    assert output["target_session_date"] == "2026-07-02"
    assert output["source_session_id"] == "session-1"
    assert output["carryover_count"] == 3
    assert output["groups"]["strength_carryover"][0]["ticker"] == "OPEN"
    assert output["groups"]["weakness_carryover"][0]["ticker"] == "AMAT"
    assert output["groups"]["context_only"][0]["ticker"] == "FIGR"
    assert output["excluded_reviewed"][0]["ticker"] == "MRVL"
    assert output["fresh_scan_required"] is True
    assert output["what_lance_would_do_now"] == "Prepare alerts and wait; no active setup is carried without fresh volume and 2-minute structure."
    assert output["groups"]["strength_carryover"][0]["confirmation_checklist"] == [
        "Run a fresh Advanced Lance scan before the next session.",
        "Require OK confidence and current as-of timestamps.",
        "Require RVOL >= 3.0 before treating it as in play.",
        "Use build_lance_intraday_plan after 2-minute bars exist.",
        "Stand down if the state remains not_in_play.",
    ]


def test_lance_carryover_plan_empty_when_session_has_no_pending_reviews(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)

    output = LanceCarryoverPlanService(db_path=db_path).build(session_id="session-1")

    assert output["status"] == "EMPTY"
    assert output["carryover_count"] == 0


def test_lance_carryover_plan_preserves_swing_playbook_bucket(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    insert_lance_watchlist_event(
        db_path,
        session_id="2026-07-02-lance-swing",
        ticker="MU",
        event_type="swing_scan",
        state="mean_reversion_watch",
        score=78,
        data_quality={
            "gap_pct": -7.2,
            "rel_volume": 2.4,
            "confidence": "OK",
            "gap_basis": "last_trade",
            "as_of_et": "Jul 2 4:00 PM ET",
            "sources": ["fake"],
        },
        payload={
            "playbook": "swing_mean_reversion_reclaim",
            "waiting_for": ["Reclaim the prior day low"],
            "invalidates_if": ["Rejects reclaim level"],
        },
    )

    output = LanceCarryoverPlanService(db_path=db_path).build(
        session_id="2026-07-02-lance-swing",
        target_session_date="2026-07-03",
    )

    assert output["status"] == "OK"
    assert output["carryover_count"] == 1
    row = output["groups"]["swing_mean_reversion_carryover"][0]
    assert row["ticker"] == "MU"
    assert row["playbook"] == "swing_mean_reversion_reclaim"
    assert row["latest_event_type"] == "swing_scan"
    assert "Require daily reclaim/hold before upgrading the swing idea." in row["confirmation_checklist"]
