from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

from app.config import BASE_DIR
from app.db import get_latest_lance_session_id
from services.lance_carryover_plan_service import LanceCarryoverPlanService
from services.lance_market_scan_service import DISCLAIMER
from services.lance_memory_report_service import LanceMemoryReportService
from services.lance_outcome_journal_service import LanceOutcomeJournalService
from services.lance_session_review_service import LanceSessionReviewService


class LanceReplayService:
    """Replay Lance session workflow against a scratch SQLite copy."""

    def replay(
        self,
        *,
        source_db_path: str | Path,
        scratch_db_path: str | Path | None = None,
        scenario_name: str | None = None,
        scenarios_path: str | Path | None = None,
        session_id: str | None = None,
        target_session_date: str | None = None,
        outcomes: list[dict[str, Any]] | None = None,
        limit: int = 500,
        check_assertions: bool = False,
    ) -> dict[str, Any]:
        source_path = Path(source_db_path)
        if not source_path.exists():
            return _error(f"source database not found: {source_path}")

        scenario = _load_scenario(scenario_name, scenarios_path)
        if scenario.get("error"):
            return _error(str(scenario["error"]))

        scratch_path = _scratch_path(scratch_db_path, session_id)
        if source_path.resolve() == scratch_path.resolve():
            return _error("scratch database must be different from source database.")

        scratch_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, scratch_path)

        resolved_session_id = (
            session_id
            or _string_or_none(scenario.get("session_id"))
            or get_latest_lance_session_id(scratch_path)
        )
        if resolved_session_id is None:
            return _error("no Lance session found in source database.")
        resolved_target_session_date = target_session_date or _string_or_none(
            scenario.get("target_session_date")
        )
        resolved_limit = _scenario_limit(scenario, limit)
        resolved_outcomes = list(scenario.get("outcomes") or [])
        resolved_outcomes.extend(outcomes or [])

        review_service = LanceSessionReviewService(db_path=scratch_path)
        initial_review = review_service.review(
            session_id=resolved_session_id,
            limit=resolved_limit,
        )
        playbooks = _playbooks_by_ticker(initial_review)
        applied = _apply_outcomes(
            scratch_path=scratch_path,
            session_id=resolved_session_id,
            playbooks=playbooks,
            outcomes=resolved_outcomes,
        )
        final_review = review_service.review(
            session_id=resolved_session_id,
            limit=resolved_limit,
        )
        memory = LanceMemoryReportService(db_path=scratch_path).summarize(
            session_id=resolved_session_id,
            limit=resolved_limit,
        )
        carryover = LanceCarryoverPlanService(db_path=scratch_path).build(
            session_id=resolved_session_id,
            target_session_date=resolved_target_session_date,
            limit=resolved_limit,
        )
        assertions = _evaluate_assertions(
            scenario=scenario,
            enabled=check_assertions,
            initial_review=initial_review,
            final_review=final_review,
            memory=memory,
            carryover=carryover,
            outcomes_applied=applied,
        )

        return {
            "agent_name": "lance_intraday",
            "mode": "replay",
            "status": "OK",
            "scenario": _scenario_summary(scenario),
            "source_db_path": str(source_path),
            "scratch_db_path": str(scratch_path),
            "session_id": resolved_session_id,
            "target_session_date": resolved_target_session_date,
            "outcomes_applied": applied,
            "initial_review_summary": _review_summary(initial_review),
            "review": final_review,
            "memory": memory,
            "carryover": carryover,
            "assertions": assertions,
            "notes": [
                "Replay runs on a scratch database copy; source market data and journal rows are not modified.",
                "Synthetic outcomes are workflow labels for testing unless manually reviewed.",
            ],
            "disclaimer": DISCLAIMER,
        }


def _load_scenario(
    scenario_name: str | None,
    scenarios_path: str | Path | None,
) -> dict[str, Any]:
    if not scenario_name:
        return {}
    path = Path(scenarios_path) if scenarios_path else BASE_DIR / "data" / "lance_replay_scenarios.yaml"
    if not path.exists():
        return {"error": f"Lance replay scenarios file not found: {path}"}
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        return {"error": f"{path} must contain a mapping of replay scenario names."}
    key = scenario_name.strip()
    raw = loaded.get(key)
    if raw is None:
        valid = ", ".join(sorted(str(name) for name in loaded)) or "(none)"
        return {
            "error": (
                f"Unknown Lance replay scenario: {scenario_name}. "
                f"Valid scenarios: {valid}."
            )
        }
    if not isinstance(raw, dict):
        return {"error": f"Lance replay scenario '{key}' must be a mapping."}
    scenario = dict(raw)
    scenario["name"] = key
    outcomes = scenario.get("outcomes") or []
    if not isinstance(outcomes, list):
        return {"error": f"Lance replay scenario '{key}' outcomes must be a list."}
    scenario["outcomes"] = [dict(item) for item in outcomes if isinstance(item, dict)]
    return scenario


def _scenario_summary(scenario: dict[str, Any]) -> dict[str, Any] | None:
    name = _string_or_none(scenario.get("name"))
    if name is None:
        return None
    return {
        "name": name,
        "description": _string_or_none(scenario.get("description")),
    }


def _scenario_limit(scenario: dict[str, Any], fallback: int) -> int:
    value = scenario.get("limit")
    if value is None:
        return fallback
    return int(value)


def _evaluate_assertions(
    *,
    scenario: dict[str, Any],
    enabled: bool,
    initial_review: dict[str, Any],
    final_review: dict[str, Any],
    memory: dict[str, Any],
    carryover: dict[str, Any],
    outcomes_applied: list[dict[str, Any]],
) -> dict[str, Any]:
    expected = scenario.get("expected") or {}
    if not isinstance(expected, dict):
        return {
            "status": "ERROR",
            "checked_count": 0,
            "failed_count": 1,
            "checks": [{
                "field": "expected",
                "expected": "mapping",
                "actual": type(expected).__name__,
                "status": "FAIL",
            }],
        }
    if not enabled:
        return {
            "status": "SKIPPED",
            "checked_count": 0,
            "failed_count": 0,
            "checks": [],
        }

    actuals = {
        "initial_pending_count": initial_review.get("pending_count"),
        "final_pending_count": final_review.get("pending_count"),
        "reviewed_count": final_review.get("reviewed_count"),
        "memory_outcome_count": memory.get("outcome_count"),
        "carryover_count": carryover.get("carryover_count"),
        "outcomes_applied_count": len(outcomes_applied),
    }
    checks = []
    for field, expected_value in expected.items():
        actual_value = actuals.get(str(field))
        status = "PASS" if actual_value == expected_value else "FAIL"
        checks.append({
            "field": str(field),
            "expected": expected_value,
            "actual": actual_value,
            "status": status,
        })
    failed_count = sum(1 for check in checks if check["status"] == "FAIL")
    return {
        "status": "FAIL" if failed_count else "PASS",
        "checked_count": len(checks),
        "failed_count": failed_count,
        "checks": checks,
    }


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _scratch_path(scratch_db_path: str | Path | None, session_id: str | None) -> Path:
    if scratch_db_path is not None:
        return Path(scratch_db_path)
    label = _safe_label(session_id or "latest")
    return Path(tempfile.gettempdir()) / f"lance_replay_{label}.sqlite"


def _safe_label(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)


def _playbooks_by_ticker(review: dict[str, Any]) -> dict[str, str]:
    playbooks: dict[str, str] = {}
    for row in review.get("pending_reviews") or []:
        args = row.get("journal_args") or {}
        ticker = str(args.get("ticker") or row.get("ticker") or "").upper()
        playbook = str(args.get("playbook") or "").strip()
        if ticker and playbook:
            playbooks[ticker] = playbook
    return playbooks


def _apply_outcomes(
    *,
    scratch_path: Path,
    session_id: str,
    playbooks: dict[str, str],
    outcomes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    journal = LanceOutcomeJournalService(db_path=scratch_path)
    applied: list[dict[str, Any]] = []
    for outcome in outcomes:
        ticker = str(outcome.get("ticker") or "").strip().upper()
        label = str(outcome.get("outcome") or "").strip().lower()
        playbook = str(
            outcome.get("playbook")
            or playbooks.get(ticker)
            or "mean_reversion_after_capitulation"
        )
        result = journal.record(
            session_id=session_id,
            ticker=ticker,
            playbook=playbook,
            outcome=label,
            notes=outcome.get("notes"),
        )
        applied.append(
            {
                "ticker": ticker,
                "outcome": label,
                "playbook": playbook,
                "status": str(result.get("status") or "ERROR"),
            }
        )
    return applied


def _review_summary(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": review.get("status"),
        "pending_count": review.get("pending_count"),
        "reviewed_count": review.get("reviewed_count"),
    }


def _error(message: str) -> dict[str, Any]:
    return {
        "agent_name": "lance_intraday",
        "mode": "replay",
        "status": "ERROR",
        "error": message,
        "disclaimer": DISCLAIMER,
    }
