from __future__ import annotations

from app.db import get_lance_outcomes, initialize_database, insert_lance_outcome
from services.lance_system_check_service import LanceSystemCheckService


class FakePassingSuiteService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "agent_name": "lance_intraday",
            "mode": "replay_suite",
            "status": "PASS",
            "source_db_path": str(kwargs["source_db_path"]),
            "scenarios_path": str(kwargs["scenarios_path"]),
            "scratch_dir": str(kwargs["scratch_dir"]),
            "scenario_count": 2,
            "passed_count": 2,
            "failed_count": 0,
            "results": [],
        }


def test_lance_system_check_passes_when_suite_passes_and_source_outcomes_unchanged(
    tmp_path,
):
    source_db = tmp_path / "source.sqlite"
    scenarios_path = tmp_path / "scenarios.yaml"
    scratch_dir = tmp_path / "scratch"
    initialize_database(source_db)
    insert_lance_outcome(
        source_db,
        session_id="session-1",
        ticker="OPEN",
        playbook="mean_reversion_after_capitulation",
        outcome="worked",
    )
    suite = FakePassingSuiteService()

    output = LanceSystemCheckService(suite_service=suite).run(
        source_db_path=source_db,
        scenarios_path=scenarios_path,
        scratch_dir=scratch_dir,
    )

    assert output["mode"] == "system_check"
    assert output["status"] == "PASS"
    assert output["replay_suite"]["status"] == "PASS"
    assert output["safety_checks"]["status"] == "PASS"
    assert output["safety_checks"]["checks"] == [
        {
            "name": "source_outcome_count_unchanged",
            "status": "PASS",
            "before": 1,
            "after": 1,
        }
    ]
    assert output["summary"] == {
        "suite_status": "PASS",
        "suite_scenarios": 2,
        "suite_passed": 2,
        "suite_failed": 0,
        "source_outcomes_before": 1,
        "source_outcomes_after": 1,
    }
    assert suite.calls[0]["source_db_path"] == source_db
    assert suite.calls[0]["scenarios_path"] == scenarios_path
    assert suite.calls[0]["scratch_dir"] == scratch_dir
    assert len(get_lance_outcomes(source_db, limit=10)) == 1


def test_lance_system_check_fails_when_suite_pollutes_source_outcome_journal(tmp_path):
    source_db = tmp_path / "source.sqlite"
    initialize_database(source_db)

    class PollutingSuiteService:
        def run(self, **kwargs):
            insert_lance_outcome(
                kwargs["source_db_path"],
                session_id="session-1",
                ticker="OPEN",
                playbook="mean_reversion_after_capitulation",
                outcome="worked",
            )
            return {
                "agent_name": "lance_intraday",
                "mode": "replay_suite",
                "status": "PASS",
                "scenario_count": 1,
                "passed_count": 1,
                "failed_count": 0,
                "results": [],
            }

    output = LanceSystemCheckService(suite_service=PollutingSuiteService()).run(
        source_db_path=source_db,
        scenarios_path=tmp_path / "scenarios.yaml",
        scratch_dir=tmp_path / "scratch",
    )

    assert output["status"] == "FAIL"
    assert output["safety_checks"]["status"] == "FAIL"
    assert output["safety_checks"]["checks"][0]["before"] == 0
    assert output["safety_checks"]["checks"][0]["after"] == 1
    assert "Source outcome journal changed during replay suite." in output["notes"]


def test_lance_system_check_returns_error_when_replay_suite_errors(tmp_path):
    source_db = tmp_path / "source.sqlite"
    initialize_database(source_db)

    class ErrorSuiteService:
        def run(self, **kwargs):
            return {
                "agent_name": "lance_intraday",
                "mode": "replay_suite",
                "status": "ERROR",
                "error": "scenario file missing",
            }

    output = LanceSystemCheckService(suite_service=ErrorSuiteService()).run(
        source_db_path=source_db,
        scenarios_path=tmp_path / "missing.yaml",
        scratch_dir=tmp_path / "scratch",
    )

    assert output["status"] == "ERROR"
    assert output["replay_suite"]["error"] == "scenario file missing"
    assert output["safety_checks"]["status"] == "PASS"
