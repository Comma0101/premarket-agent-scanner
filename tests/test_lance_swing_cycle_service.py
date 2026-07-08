from __future__ import annotations

from app.db import (
    get_lance_watchlist_events,
    get_lance_watchlist_items,
    initialize_database,
)
from services.lance_swing_cycle_service import LanceSwingCycleService


class FakeUniverseService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def resolve_selection(self, **kwargs):
        from services.universe_service import UniverseSelection

        self.calls.append(kwargs)
        return UniverseSelection(
            tickers=["MU", "HOOD", "NVDA"],
            memberships={
                "MU": ["AI_SEMIS_MEMORY"],
                "HOOD": ["WATCHLIST:HOT_ACTIVE"],
                "NVDA": ["AI_SEMIS_MEMORY"],
            },
            label="AI_SEMIS_MEMORY,WATCHLIST:HOT_ACTIVE",
        )


class FakeSwingService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_swing",
            "strategy": "Lance Breitstein daily/swing planning",
            "timeframe": "daily_swing",
            "ticker_count": 3,
            "plan_count": 3,
            "plans": [
                _plan("MU", state="mean_reversion_watch", score=55.0),
                _plan("HOOD", state="active_watch", score=90.0),
                _plan("NVDA", state="invalidated", score=-40.0),
            ],
            "groups": {
                "active_watch": [{"ticker": "HOOD"}],
                "mean_reversion_watch": [{"ticker": "MU"}],
                "watching": [],
                "not_in_play": [],
                "invalidated": [{"ticker": "NVDA"}],
                "blocked": [],
            },
            "disclaimer": "Swing plans are not buy/sell advice.",
        }


def _plan(ticker: str, *, state: str, score: float) -> dict:
    playbook = (
        "swing_mean_reversion_reclaim"
        if state == "mean_reversion_watch"
        else "relative_strength_continuation"
    )
    return {
        "ticker": ticker,
        "state": state,
        "state_reason": f"{ticker} state reason.",
        "lance_quality_grade": "REVERSION_WATCH"
        if state == "mean_reversion_watch"
        else "ACTIVE_DAILY_WATCH",
        "playbook": playbook,
        "score": score,
        "data_quality": {
            "confidence": "OK",
            "gap_basis": "last_trade",
            "as_of_et": "Jul 2 3:31 PM ET",
            "gap_pct": -7.1 if ticker == "MU" else 3.2,
            "rel_volume": 1.2,
            "sources": ["fake"],
        },
        "daily_context": {
            "trend": "mixed",
            "structure": "mixed_range",
            "prior_day_levels": {"high": 110.0, "low": 100.0, "close": 105.0},
        },
        "relative_strength": {"classification": "in_line", "vs_QQQ": -1.2, "vs_SPY": -0.5},
        "waiting_for": ["prior-day low reclaim above 100.0"],
        "invalidates_if": ["daily close remains below prior-day low reference 100.0"],
        "manual_review_questions": ["Did it reclaim or keep liquidating?"],
        "next_step": "Track as a Lance swing watch.",
        "disclaimer": "Swing plans are not buy/sell advice.",
    }


def test_lance_swing_cycle_resolves_selection_groups_and_persists(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    universe = FakeUniverseService()
    swing = FakeSwingService()

    output = LanceSwingCycleService(
        swing_service=swing,
        universe_service=universe,
        db_path=db_path,
    ).run(
        universe="AI_SEMIS_MEMORY",
        watchlist="HOT_ACTIVE",
        session_id="2026-07-02-lance-swing",
        persist=True,
        summary_limit=2,
    )

    assert universe.calls == [{
        "tickers": None,
        "universe": "AI_SEMIS_MEMORY",
        "watchlist": "HOT_ACTIVE",
        "all_universes": False,
    }]
    assert swing.calls == [{"tickers": ["MU", "HOOD", "NVDA"], "lookback_days": 60}]
    assert output["status"] == "OK"
    assert output["session_id"] == "2026-07-02-lance-swing"
    assert output["selection"] == "AI_SEMIS_MEMORY,WATCHLIST:HOT_ACTIVE"
    assert output["selection_count"] == 3
    assert output["summary"] == {
        "plan_count": 3,
        "active_watch_count": 1,
        "mean_reversion_watch_count": 1,
        "watching_count": 0,
        "invalidated_count": 1,
        "blocked_count": 0,
    }
    assert [row["ticker"] for row in output["top_watchlist"]] == ["HOOD", "MU"]
    assert output["groups"]["mean_reversion_watch"][0]["ticker"] == "MU"

    rows = get_lance_watchlist_items(db_path, session_id="2026-07-02-lance-swing", limit=10)
    events = get_lance_watchlist_events(db_path, session_id="2026-07-02-lance-swing", limit=10)
    assert {row["ticker"] for row in rows} == {"MU", "HOOD", "NVDA"}
    mu = next(row for row in rows if row["ticker"] == "MU")
    assert mu["state"] == "mean_reversion_watch"
    assert mu["playbook"] == "swing_mean_reversion_reclaim"
    assert "MU" in mu["why_watching"]
    assert len(events) == 3
    assert {event["event_type"] for event in events} == {"swing_scan"}


def test_lance_swing_cycle_allows_explicit_tickers_without_persistence(tmp_path):
    db_path = tmp_path / "lance.db"
    initialize_database(db_path)
    universe = FakeUniverseService()
    swing = FakeSwingService()

    output = LanceSwingCycleService(
        swing_service=swing,
        universe_service=universe,
        db_path=db_path,
    ).run(
        tickers="MU,HOOD",
        persist=False,
    )

    assert universe.calls == []
    assert swing.calls == [{"tickers": "MU,HOOD", "lookback_days": 60}]
    assert output["selection"] == "MANUAL"
    assert output["selection_count"] == 2
    assert get_lance_watchlist_items(db_path, session_id=output["session_id"], limit=10) == []
