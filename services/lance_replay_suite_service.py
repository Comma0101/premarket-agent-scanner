from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import yaml

from app.config import BASE_DIR
from services.lance_market_scan_service import DISCLAIMER
from services.lance_replay_service import LanceReplayService


class LanceReplaySuiteService:
    """Run every named Lance replay scenario as a regression suite."""

    def run(
        self,
        *,
        source_db_path: str | Path,
        scenarios_path: str | Path | None = None,
        scratch_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        scenario_path = Path(scenarios_path) if scenarios_path else _default_scenarios_path()
        if not scenario_path.exists():
            return _error(f"Lance replay scenarios file not found: {scenario_path}")

        scenarios = _load_scenarios(scenario_path)
        if isinstance(scenarios, str):
            return _error(scenarios)

        scratch_root = Path(scratch_dir) if scratch_dir else _default_scratch_dir()
        scratch_root.mkdir(parents=True, exist_ok=True)

        results = []
        replay_service = LanceReplayService()
        for scenario_name in scenarios:
            scratch_db_path = scratch_root / f"lance_replay_{_safe_label(scenario_name)}.sqlite"
            replay = replay_service.replay(
                source_db_path=source_db_path,
                scratch_db_path=scratch_db_path,
                scenario_name=scenario_name,
                scenarios_path=scenario_path,
                check_assertions=True,
            )
            results.append(_scenario_result(scenario_name, replay))

        failed_count = sum(1 for result in results if result["assertion_status"] != "PASS")
        return {
            "agent_name": "lance_intraday",
            "mode": "replay_suite",
            "status": "FAIL" if failed_count else "PASS",
            "source_db_path": str(source_db_path),
            "scenarios_path": str(scenario_path),
            "scratch_dir": str(scratch_root),
            "scenario_count": len(results),
            "passed_count": len(results) - failed_count,
            "failed_count": failed_count,
            "results": results,
            "notes": [
                "Replay suite runs scenarios on scratch database copies only.",
                "Scenario outcome labels are synthetic unless manually reviewed.",
            ],
            "disclaimer": DISCLAIMER,
        }


def _load_scenarios(path: Path) -> list[str] | str:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        return f"{path} must contain a mapping of replay scenario names."
    return [str(name) for name in loaded]


def _scenario_result(scenario_name: str, replay: dict[str, Any]) -> dict[str, Any]:
    assertions = replay.get("assertions") or {}
    return {
        "scenario_name": scenario_name,
        "status": replay.get("status"),
        "assertion_status": assertions.get("status") or "ERROR",
        "checked_count": assertions.get("checked_count", 0),
        "failed_count": assertions.get("failed_count", 1),
        "scratch_db_path": replay.get("scratch_db_path"),
        "session_id": replay.get("session_id"),
        "memory_outcome_count": (replay.get("memory") or {}).get("outcome_count"),
        "carryover_count": (replay.get("carryover") or {}).get("carryover_count"),
        "error": replay.get("error"),
        "checks": assertions.get("checks") or [],
    }


def _default_scenarios_path() -> Path:
    return BASE_DIR / "data" / "lance_replay_scenarios.yaml"


def _default_scratch_dir() -> Path:
    return Path(tempfile.gettempdir()) / "lance_replay_suite"


def _safe_label(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)


def _error(message: str) -> dict[str, Any]:
    return {
        "agent_name": "lance_intraday",
        "mode": "replay_suite",
        "status": "ERROR",
        "error": message,
        "disclaimer": DISCLAIMER,
    }
