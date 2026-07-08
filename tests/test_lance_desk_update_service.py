from __future__ import annotations

from app.db import (
    get_lance_watchlist_events,
    get_lance_watchlist_items,
    get_latest_lance_session_id,
    initialize_database,
    insert_lance_watchlist_event,
    upsert_lance_watchlist_item,
)
from services.lance_desk_update_service import LanceDeskUpdateService


class FakePlanService:
    def __init__(self, plans: dict[str, dict]) -> None:
        self.plans = plans
        self.calls: list[str] = []

    def build_plan(self, ticker: str) -> dict:
        normalized = ticker.upper()
        self.calls.append(normalized)
        return self.plans[normalized]


def _plan(ticker: str, *, state: str, gap_pct: float, rel_volume: float) -> dict:
    return {
        "ticker": ticker,
        "trader": "lance_breitstein",
        "setup_name": "mean_reversion_after_capitulation",
        "state": state,
        "data_quality": {
            "confidence": "OK",
            "gap_basis": "last_trade",
            "as_of": "2026-07-01T15:00:00Z",
            "as_of_et": "Jul 1 11:00 AM ET",
            "session_mode": "MARKET_OPEN",
            "latest_price": 100 + gap_pct,
            "previous_close": 100,
            "gap_pct": gap_pct,
            "gap_dollar": gap_pct,
            "volume": 1_000_000,
            "rel_volume": rel_volume,
            "sources": ["fake"],
        },
        "conditions": {
            "data_quality": {"status": "PASS"},
            "abnormal_move": {"status": "PASS"},
            "participation": {"status": "PASS" if rel_volume >= 3 else "FAIL"},
            "prior_bar_break": {"status": "PASS" if state == "triggered_reference" else "WAITING"},
            "volume_2x": {"status": "PASS" if state != "not_in_play" else "WAITING"},
            "consecutive_pressure": {"status": "PASS" if state != "not_in_play" else "WAITING"},
            "chop_filter": {"status": "PASS"},
        },
        "trigger_reference": (
            {"direction": "long", "price": 104.25, "source": "prior_2min_bar_high_break"}
            if state == "triggered_reference"
            else None
        ),
        "risk_reference": {"price": 98.75, "source": "prior_2min_bar_low"},
        "target_reference": {"price": 103.5, "source": "20_period_ma"},
        "missing_fields": [],
        "next_step": "Monitor Lance plan.",
    }


def test_lance_desk_update_refreshes_and_persists_watchlist_item(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    previous_plan = _plan("FAST", state="watching", gap_pct=4.0, rel_volume=1.2)
    upsert_lance_watchlist_item(
        db_path,
        session_id="session-1",
        ticker="FAST",
        state="watching",
        score=40,
        playbook="mean_reversion_after_capitulation",
        why_watching="FAST: 4.0% move, 1.2x RVOL, Lance state watching.",
        invalidates_if="Participation does not improve.",
        next_step="Watch only.",
        data_quality=previous_plan["data_quality"],
        plan=previous_plan,
    )
    plan_service = FakePlanService(
        {"FAST": _plan("FAST", state="triggered_reference", gap_pct=6.5, rel_volume=3.6)}
    )

    output = LanceDeskUpdateService(plan_service=plan_service, db_path=db_path).update(
        session_id="session-1"
    )

    assert output["agent_name"] == "lance_intraday"
    assert output["session_id"] == "session-1"
    assert output["status"] == "OK"
    assert output["tracked_count"] == 1
    assert output["updated_count"] == 1
    update = output["updates"][0]
    assert update["ticker"] == "FAST"
    assert update["previous_state"] == "watching"
    assert update["current_state"] == "triggered_reference"
    assert update["state_changed"] is True
    assert update["score_delta"] > 0
    assert update["gap_pct_delta"] == 2.5
    assert update["rel_volume_delta"] == 2.4
    assert "state_changed" in update["change_flags"]
    assert "rvol_expanded" in update["change_flags"]
    assert plan_service.calls == ["FAST"]

    rows = get_lance_watchlist_items(db_path, session_id="session-1")
    events = get_lance_watchlist_events(db_path, session_id="session-1", ticker="FAST")
    assert rows[0]["state"] == "triggered_reference"
    assert rows[0]["plan"]["data_quality"]["rel_volume"] == 3.6
    assert len(events) == 1
    assert events[0]["event_type"] == "update"
    assert events[0]["state"] == "triggered_reference"
    assert "rvol_expanded" in events[0]["payload"]["change_flags"]


def test_lance_desk_update_defaults_to_latest_session(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    old_plan = _plan("OLD", state="watching", gap_pct=3.5, rel_volume=1.0)
    fresh_plan = _plan("FRESH", state="setup_forming", gap_pct=5.0, rel_volume=3.2)
    upsert_lance_watchlist_item(
        db_path,
        session_id="old-session",
        ticker="OLD",
        state="watching",
        score=20,
        playbook="mean_reversion_after_capitulation",
        why_watching="OLD",
        invalidates_if=None,
        next_step=None,
        data_quality=old_plan["data_quality"],
        plan=old_plan,
    )
    upsert_lance_watchlist_item(
        db_path,
        session_id="fresh-session",
        ticker="FRESH",
        state="setup_forming",
        score=70,
        playbook="mean_reversion_after_capitulation",
        why_watching="FRESH",
        invalidates_if=None,
        next_step=None,
        data_quality=fresh_plan["data_quality"],
        plan=fresh_plan,
    )

    assert get_latest_lance_session_id(db_path) == "fresh-session"
    output = LanceDeskUpdateService(
        plan_service=FakePlanService(
            {"FRESH": _plan("FRESH", state="triggered_reference", gap_pct=5.5, rel_volume=3.8)}
        ),
        db_path=db_path,
    ).update()

    assert output["session_id"] == "fresh-session"
    assert [row["ticker"] for row in output["updates"]] == ["FRESH"]


def test_lance_desk_update_default_ignores_latest_swing_session(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    intraday_plan = _plan("IBM", state="watching", gap_pct=4.5, rel_volume=1.5)
    swing_plan = _plan("MU", state="watching", gap_pct=-7.0, rel_volume=2.1)
    upsert_lance_watchlist_item(
        db_path,
        session_id="2026-07-02-lance-intraday",
        ticker="IBM",
        state="watching",
        score=45,
        playbook="mean_reversion_after_capitulation",
        why_watching="IBM",
        invalidates_if=None,
        next_step=None,
        data_quality=intraday_plan["data_quality"],
        plan=intraday_plan,
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
        data_quality=swing_plan["data_quality"],
        plan=swing_plan,
    )

    output = LanceDeskUpdateService(
        plan_service=FakePlanService(
            {"IBM": _plan("IBM", state="setup_forming", gap_pct=5.0, rel_volume=3.1)}
        ),
        db_path=db_path,
    ).update()

    assert output["session_id"] == "2026-07-02-lance-intraday"
    assert [row["ticker"] for row in output["updates"]] == ["IBM"]


def test_lance_desk_update_empty_when_no_session_exists(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)

    output = LanceDeskUpdateService(plan_service=FakePlanService({}), db_path=db_path).update()

    assert output["status"] == "EMPTY"
    assert output["tracked_count"] == 0
    assert output["updates"] == []


def test_lance_desk_update_prefers_latest_event_tickers_over_stale_score_rows(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    stale_plan = _plan("STALE", state="watching", gap_pct=12.0, rel_volume=1.0)
    fresh_plan = _plan("FRESH", state="watching", gap_pct=4.0, rel_volume=1.0)
    upsert_lance_watchlist_item(
        db_path,
        session_id="session-1",
        ticker="STALE",
        state="watching",
        score=100,
        playbook="mean_reversion_after_capitulation",
        why_watching="STALE",
        invalidates_if=None,
        next_step=None,
        data_quality=stale_plan["data_quality"],
        plan=stale_plan,
    )
    upsert_lance_watchlist_item(
        db_path,
        session_id="session-1",
        ticker="FRESH",
        state="watching",
        score=10,
        playbook="mean_reversion_after_capitulation",
        why_watching="FRESH",
        invalidates_if=None,
        next_step=None,
        data_quality=fresh_plan["data_quality"],
        plan=fresh_plan,
    )
    insert_lance_watchlist_event(
        db_path,
        session_id="session-1",
        ticker="STALE",
        event_type="scan",
        state="watching",
        score=100,
        data_quality=stale_plan["data_quality"],
        payload={},
    )
    insert_lance_watchlist_event(
        db_path,
        session_id="session-1",
        ticker="FRESH",
        event_type="scan",
        state="watching",
        score=10,
        data_quality=fresh_plan["data_quality"],
        payload={},
    )

    output = LanceDeskUpdateService(
        plan_service=FakePlanService(
            {"FRESH": _plan("FRESH", state="setup_forming", gap_pct=5.0, rel_volume=3.2)}
        ),
        db_path=db_path,
    ).update(session_id="session-1", limit=1)

    assert [row["ticker"] for row in output["updates"]] == ["FRESH"]
