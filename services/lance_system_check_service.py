from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db import get_connection
from services.lance_market_scan_service import DISCLAIMER
from services.lance_replay_suite_service import LanceReplaySuiteService


class LanceSystemCheckService:
    """Run the Lance replay suite and verify it does not mutate source memory."""

    def __init__(self, *, suite_service: Any | None = None) -> None:
        self.suite_service = suite_service or LanceReplaySuiteService()

    def run(
        self,
        *,
        source_db_path: str | Path,
        scenarios_path: str | Path | None = None,
        scratch_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        before_count = _count_lance_outcomes(source_db_path)
        replay_suite = self.suite_service.run(
            source_db_path=source_db_path,
            scenarios_path=scenarios_path,
            scratch_dir=scratch_dir,
        )
        after_count = _count_lance_outcomes(source_db_path)

        safety_checks = _safety_checks(before_count=before_count, after_count=after_count)
        status = _system_status(
            suite_status=str(replay_suite.get("status") or "ERROR"),
            safety_status=str(safety_checks["status"]),
        )
        notes = [
            "System check runs replay scenarios through scratch database copies.",
            "Source DB safety passes only when the Lance outcome journal count is unchanged.",
        ]
        if safety_checks["status"] != "PASS":
            notes.append("Source outcome journal changed during replay suite.")

        return {
            "agent_name": "lance_intraday",
            "mode": "system_check",
            "status": status,
            "source_db_path": str(source_db_path),
            "scenarios_path": None if scenarios_path is None else str(scenarios_path),
            "scratch_dir": None if scratch_dir is None else str(scratch_dir),
            "replay_suite": replay_suite,
            "safety_checks": safety_checks,
            "summary": {
                "suite_status": replay_suite.get("status"),
                "suite_scenarios": replay_suite.get("scenario_count", 0),
                "suite_passed": replay_suite.get("passed_count", 0),
                "suite_failed": replay_suite.get("failed_count", 0),
                "source_outcomes_before": before_count,
                "source_outcomes_after": after_count,
            },
            "notes": notes,
            "disclaimer": DISCLAIMER,
        }


def _count_lance_outcomes(db_path: str | Path) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) AS count FROM lance_outcomes").fetchone()
    finally:
        conn.close()
    return int(row["count"] if row is not None else 0)


def _safety_checks(*, before_count: int, after_count: int) -> dict[str, Any]:
    status = "PASS" if before_count == after_count else "FAIL"
    return {
        "status": status,
        "checks": [
            {
                "name": "source_outcome_count_unchanged",
                "status": status,
                "before": before_count,
                "after": after_count,
            }
        ],
    }


def _system_status(*, suite_status: str, safety_status: str) -> str:
    if suite_status == "ERROR":
        return "ERROR"
    if suite_status != "PASS" or safety_status != "PASS":
        return "FAIL"
    return "PASS"
