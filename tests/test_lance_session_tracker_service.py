from __future__ import annotations

from services.lance_session_tracker_service import LanceSessionTrackerService


def _row(
    ticker: str,
    *,
    lanes: list[str],
    intraday_state: str | None = None,
    swing_state: str | None = None,
    intraday_score: float | None = None,
    swing_score: float | None = None,
    confidence: str = "OK",
    gap_basis: str = "premarket",
    as_of_et: str = "Jul 2 10:00 AM ET",
) -> dict:
    return {
        "ticker": ticker,
        "lanes": lanes,
        "intraday_state": intraday_state,
        "swing_state": swing_state,
        "intraday_score": intraday_score,
        "swing_score": swing_score,
        "data_quality": {
            "confidence": confidence,
            "gap_basis": gap_basis,
            "as_of_et": as_of_et,
            "data_status": "live" if confidence == "OK" else "stale",
        },
    }


def _payload(session: str, rows: list[dict]) -> dict:
    return {
        "agent_name": "lance_full_cycle",
        "mode": "full_cycle",
        "status": "OK",
        "session_ids": {"intraday": f"{session}-intraday", "swing": f"{session}-swing"},
        "combined_watchlist": rows,
        "disclaimer": "Matches your filter - not buy/sell advice. Verify before acting.",
    }


def test_lance_session_tracker_groups_new_upgraded_downgraded_removed_and_unchanged():
    previous = _payload(
        "prev",
        [
            _row("IBM", lanes=["intraday"], intraday_state="watching", intraday_score=45),
            _row("MU", lanes=["swing"], swing_state="active_watch", swing_score=80),
            _row("TER", lanes=["swing"], swing_state="mean_reversion_watch", swing_score=60),
            _row("OLD", lanes=["intraday"], intraday_state="setup_forming", intraday_score=70),
        ],
    )
    current = _payload(
        "current",
        [
            _row("IBM", lanes=["intraday"], intraday_state="triggered_reference", intraday_score=78),
            _row(
                "MU",
                lanes=["swing"],
                swing_state="blocked_data_quality",
                swing_score=20,
                confidence="STALE_DATA",
                gap_basis="last_trade",
                as_of_et="Jul 2 4:00 PM ET",
            ),
            _row("TER", lanes=["swing"], swing_state="mean_reversion_watch", swing_score=61),
            _row("NEW", lanes=["intraday"], intraday_state="setup_forming", intraday_score=55),
        ],
    )

    output = LanceSessionTrackerService().diff(previous=previous, current=current)

    assert output["agent_name"] == "lance_full_cycle"
    assert output["mode"] == "session_tracker"
    assert output["status"] == "OK"
    assert output["previous_session_ids"]["intraday"] == "prev-intraday"
    assert output["current_session_ids"]["intraday"] == "current-intraday"
    assert output["summary"] == {
        "previous_count": 4,
        "current_count": 4,
        "new_count": 1,
        "upgraded_count": 1,
        "downgraded_count": 1,
        "unchanged_count": 1,
        "removed_count": 1,
        "data_caveat_count": 1,
    }
    assert output["one_liner"] == (
        "1 new, 1 upgraded, 1 downgraded, 1 unchanged, 1 removed, 1 data caveat."
    )
    assert [row["ticker"] for row in output["groups"]["new"]] == ["NEW"]
    assert [row["ticker"] for row in output["groups"]["upgraded"]] == ["IBM"]
    assert [row["ticker"] for row in output["groups"]["downgraded"]] == ["MU"]
    assert [row["ticker"] for row in output["groups"]["unchanged"]] == ["TER"]
    assert [row["ticker"] for row in output["groups"]["removed"]] == ["OLD"]
    assert output["groups"]["upgraded"][0]["change_flags"] == [
        "state_upgraded",
        "score_improved",
    ]
    assert "data_caveat" in output["groups"]["downgraded"][0]["change_flags"]
    assert output["data_caveats"] == [
        "MU: confidence=STALE_DATA / gap_basis=last_trade as of Jul 2 4:00 PM ET."
    ]


def test_lance_session_tracker_returns_empty_when_no_prior_payload():
    current = _payload(
        "current",
        [_row("IBM", lanes=["intraday"], intraday_state="setup_forming", intraday_score=55)],
    )

    output = LanceSessionTrackerService().diff(previous=None, current=current)

    assert output["status"] == "OK"
    assert output["summary"]["previous_count"] == 0
    assert output["summary"]["new_count"] == 1
    assert output["groups"]["new"][0]["ticker"] == "IBM"
