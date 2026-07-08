from __future__ import annotations

from app.db import (
    get_lance_outcomes,
    initialize_database,
    insert_lance_watchlist_event,
)
from services.lance_replay_service import LanceReplayService


def _event(
    db_path,
    *,
    ticker: str,
    gap_pct: float,
    rel_volume: float,
    score: float,
) -> None:
    insert_lance_watchlist_event(
        db_path,
        session_id="session-1",
        ticker=ticker,
        event_type="update",
        state="not_in_play",
        score=score,
        data_quality={
            "gap_pct": gap_pct,
            "rel_volume": rel_volume,
            "confidence": "OK",
            "gap_basis": "last_trade",
            "as_of_et": "Jul 1 1:45 PM ET",
            "sources": ["fake"],
        },
        payload={"playbook": "mean_reversion_after_capitulation"},
    )


def test_lance_replay_applies_synthetic_outcomes_to_scratch_db_only(tmp_path):
    source_db = tmp_path / "source.sqlite"
    scratch_db = tmp_path / "scratch.sqlite"
    initialize_database(source_db)
    _event(source_db, ticker="OPEN", gap_pct=8.9, rel_volume=1.7, score=70)
    _event(source_db, ticker="MRVL", gap_pct=-7.6, rel_volume=0.4, score=35)

    output = LanceReplayService().replay(
        source_db_path=source_db,
        scratch_db_path=scratch_db,
        session_id="session-1",
        target_session_date="2026-07-02",
        outcomes=[{"ticker": "OPEN", "outcome": "worked"}],
        limit=20,
    )

    assert output["status"] == "OK"
    assert output["mode"] == "replay"
    assert output["session_id"] == "session-1"
    assert output["outcomes_applied"] == [
        {
            "ticker": "OPEN",
            "outcome": "worked",
            "playbook": "mean_reversion_after_capitulation",
            "status": "OK",
        }
    ]
    assert output["initial_review_summary"] == {
        "status": "OK",
        "pending_count": 2,
        "reviewed_count": 0,
    }
    assert output["review"]["pending_count"] == 1
    assert output["review"]["reviewed_count"] == 1
    assert output["memory"]["outcome_count"] == 1
    assert output["carryover"]["carryover_count"] == 1
    assert output["carryover"]["groups"]["weakness_carryover"][0]["ticker"] == "MRVL"
    assert "scratch" in output["notes"][0].lower()

    assert get_lance_outcomes(source_db, session_id="session-1") == []
    scratch_outcomes = get_lance_outcomes(scratch_db, session_id="session-1")
    assert len(scratch_outcomes) == 1
    assert scratch_outcomes[0]["ticker"] == "OPEN"


def test_lance_replay_reports_missing_source_db(tmp_path):
    output = LanceReplayService().replay(
        source_db_path=tmp_path / "missing.sqlite",
        scratch_db_path=tmp_path / "scratch.sqlite",
        session_id="session-1",
    )

    assert output["status"] == "ERROR"
    assert "source database not found" in output["error"]


def test_lance_replay_loads_named_scenario_from_yaml(tmp_path):
    source_db = tmp_path / "source.sqlite"
    scratch_db = tmp_path / "scratch.sqlite"
    scenarios_path = tmp_path / "scenarios.yaml"
    initialize_database(source_db)
    _event(source_db, ticker="OPEN", gap_pct=8.9, rel_volume=1.7, score=70)
    _event(source_db, ticker="MRVL", gap_pct=-7.6, rel_volume=0.4, score=35)
    scenarios_path.write_text(
        """
today_replay:
  description: Synthetic replay of today's saved Lance session.
  session_id: session-1
  target_session_date: "2026-07-02"
  limit: 20
  outcomes:
    - ticker: OPEN
      outcome: worked
      notes: scenario label
  expected:
    initial_pending_count: 2
    final_pending_count: 1
    reviewed_count: 1
    memory_outcome_count: 1
    carryover_count: 1
    outcomes_applied_count: 1
""".strip(),
        encoding="utf-8",
    )

    output = LanceReplayService().replay(
        source_db_path=source_db,
        scratch_db_path=scratch_db,
        scenario_name="today_replay",
        scenarios_path=scenarios_path,
        check_assertions=True,
    )

    assert output["status"] == "OK"
    assert output["scenario"] == {
        "name": "today_replay",
        "description": "Synthetic replay of today's saved Lance session.",
    }
    assert output["session_id"] == "session-1"
    assert output["target_session_date"] == "2026-07-02"
    assert output["outcomes_applied"][0]["ticker"] == "OPEN"
    assert output["memory"]["outcome_count"] == 1
    assert output["carryover"]["carryover_count"] == 1
    assert output["assertions"]["status"] == "PASS"
    assert output["assertions"]["failed_count"] == 0
    assert output["assertions"]["checked_count"] == 6


def test_lance_replay_reports_unknown_scenario_with_valid_names(tmp_path):
    source_db = tmp_path / "source.sqlite"
    scenarios_path = tmp_path / "scenarios.yaml"
    initialize_database(source_db)
    scenarios_path.write_text("today_replay:\n  session_id: session-1\n", encoding="utf-8")

    output = LanceReplayService().replay(
        source_db_path=source_db,
        scenario_name="missing",
        scenarios_path=scenarios_path,
    )

    assert output["status"] == "ERROR"
    assert "Unknown Lance replay scenario" in output["error"]
    assert "today_replay" in output["error"]


def test_lance_replay_assertions_report_failures_without_hiding_output(tmp_path):
    source_db = tmp_path / "source.sqlite"
    scratch_db = tmp_path / "scratch.sqlite"
    scenarios_path = tmp_path / "scenarios.yaml"
    initialize_database(source_db)
    _event(source_db, ticker="OPEN", gap_pct=8.9, rel_volume=1.7, score=70)
    scenarios_path.write_text(
        """
bad_expectation:
  session_id: session-1
  outcomes:
    - ticker: OPEN
      outcome: worked
  expected:
    memory_outcome_count: 99
""".strip(),
        encoding="utf-8",
    )

    output = LanceReplayService().replay(
        source_db_path=source_db,
        scratch_db_path=scratch_db,
        scenario_name="bad_expectation",
        scenarios_path=scenarios_path,
        check_assertions=True,
    )

    assert output["status"] == "OK"
    assert output["memory"]["outcome_count"] == 1
    assert output["assertions"]["status"] == "FAIL"
    assert output["assertions"]["failed_count"] == 1
    assert output["assertions"]["checks"][0] == {
        "field": "memory_outcome_count",
        "expected": 99,
        "actual": 1,
        "status": "FAIL",
    }
