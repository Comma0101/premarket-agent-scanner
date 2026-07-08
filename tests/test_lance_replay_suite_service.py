from __future__ import annotations

from app.db import get_lance_outcomes, initialize_database, insert_lance_watchlist_event
from services.lance_replay_suite_service import LanceReplaySuiteService


def _event(db_path, *, ticker: str) -> None:
    insert_lance_watchlist_event(
        db_path,
        session_id="session-1",
        ticker=ticker,
        event_type="update",
        state="not_in_play",
        score=70,
        data_quality={
            "gap_pct": 8.9,
            "rel_volume": 1.7,
            "confidence": "OK",
            "gap_basis": "last_trade",
            "as_of_et": "Jul 1 1:45 PM ET",
        },
        payload={"playbook": "mean_reversion_after_capitulation"},
    )


def test_lance_replay_suite_runs_every_scenario_and_aggregates_pass_fail(tmp_path):
    source_db = tmp_path / "source.sqlite"
    scenarios_path = tmp_path / "scenarios.yaml"
    scratch_dir = tmp_path / "scratch"
    initialize_database(source_db)
    _event(source_db, ticker="OPEN")
    scenarios_path.write_text(
        """
passing:
  session_id: session-1
  outcomes:
    - ticker: OPEN
      outcome: worked
  expected:
    memory_outcome_count: 1
    carryover_count: 0
failing:
  session_id: session-1
  outcomes:
    - ticker: OPEN
      outcome: worked
  expected:
    memory_outcome_count: 99
""".strip(),
        encoding="utf-8",
    )

    output = LanceReplaySuiteService().run(
        source_db_path=source_db,
        scenarios_path=scenarios_path,
        scratch_dir=scratch_dir,
    )

    assert output["status"] == "FAIL"
    assert output["scenario_count"] == 2
    assert output["passed_count"] == 1
    assert output["failed_count"] == 1
    assert [row["scenario_name"] for row in output["results"]] == ["passing", "failing"]
    assert output["results"][0]["assertion_status"] == "PASS"
    assert output["results"][1]["assertion_status"] == "FAIL"
    assert output["results"][1]["failed_count"] == 1
    assert output["results"][0]["scratch_db_path"].endswith("lance_replay_passing.sqlite")
    assert output["results"][1]["scratch_db_path"].endswith("lance_replay_failing.sqlite")
    assert get_lance_outcomes(source_db, session_id="session-1") == []


def test_lance_replay_suite_reports_missing_scenario_file(tmp_path):
    source_db = tmp_path / "source.sqlite"
    initialize_database(source_db)

    output = LanceReplaySuiteService().run(
        source_db_path=source_db,
        scenarios_path=tmp_path / "missing.yaml",
        scratch_dir=tmp_path / "scratch",
    )

    assert output["status"] == "ERROR"
    assert "scenarios file not found" in output["error"]
