from __future__ import annotations

from typing import Any

from services.lance_market_scan_service import DISCLAIMER


ROOT_CAUSE_KEYS = [
    "ready",
    "provider_failure",
    "missing_price",
    "stale_or_off_session",
    "halted",
    "confidence",
    "unknown",
]


class LanceDataDoctorService:
    """Explain why Lance can or cannot evaluate current ticker data."""

    def __init__(self, *, validation_service: Any | None = None) -> None:
        if validation_service is None:
            from services.live_market_validation_service import LiveMarketValidationService

            validation_service = LiveMarketValidationService()
        self.validation_service = validation_service

    def diagnose(
        self,
        *,
        tickers: list[str] | str,
        max_candidates: int = 5,
        persist: bool = False,
        summary_limit: int | None = None,
        review_limit: int = 10,
        max_workers: int = 1,
        now: str | None = None,
    ) -> dict[str, Any]:
        validation = self.validation_service.run(
            tickers=tickers,
            max_candidates=max_candidates,
            persist=persist,
            summary_limit=summary_limit if summary_limit is not None else max_candidates,
            review_limit=review_limit,
            max_workers=max_workers,
            now=now,
        )
        return _build_output(
            status=str(validation.get("status") or "unknown"),
            rows=list(validation.get("snapshot_checks") or []),
            validation=validation,
        )

    @staticmethod
    def from_signal_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
        checks = [_signal_row_to_check(row) for row in rows if isinstance(row, dict)]
        status = "blocked" if any(check["readiness"] == "blocked" for check in checks) else "ready"
        return _build_output(status=status, rows=checks, validation=None)


def _build_output(
    *,
    status: str,
    rows: list[dict[str, Any]],
    validation: dict[str, Any] | None,
) -> dict[str, Any]:
    root_causes = _empty_root_causes()
    diagnostics = []
    for row in rows:
        diagnostic = _diagnostic(row)
        diagnostics.append(diagnostic)
        for cause in diagnostic["root_causes"]:
            root_causes.setdefault(cause, []).append(diagnostic["ticker"])

    ready_count = len(root_causes["ready"])
    blocked_count = sum(1 for row in diagnostics if row["readiness"] == "blocked")
    one_liner = _one_liner(ready_count=ready_count, blocked_count=blocked_count, root_causes=root_causes)
    return {
        "agent_name": "lance_data_doctor",
        "mode": "data_doctor",
        "status": status,
        "doctor_read": {
            "one_liner": one_liner,
            "ready_count": ready_count,
            "blocked_count": blocked_count,
        },
        "root_causes": root_causes,
        "diagnostics": diagnostics,
        "next_actions": _next_actions(root_causes),
        "validation": validation,
        "disclaimer": (validation or {}).get("disclaimer") or DISCLAIMER,
    }


def _diagnostic(row: dict[str, Any]) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").strip().upper()
    causes = _classify(row)
    return {
        "ticker": ticker,
        "readiness": "ready" if causes == ["ready"] else "blocked",
        "root_causes": causes,
        "confidence": row.get("confidence"),
        "gap_basis": row.get("gap_basis"),
        "data_status": row.get("data_status"),
        "as_of_et": row.get("as_of_et"),
        "blockers": list(row.get("blockers") or []),
        "provider_failures": dict(row.get("provider_failures") or {}),
    }


def _classify(row: dict[str, Any]) -> list[str]:
    blockers = [str(value) for value in row.get("blockers") or []]
    failures = row.get("provider_failures") or {}
    data_status = row.get("data_status")
    confidence = row.get("confidence")
    causes = []
    if row.get("readiness") == "ready" and confidence == "OK" and data_status in {None, "live"}:
        return ["ready"]
    if failures or data_status == "provider_failure" or "provider_failures present" in blockers:
        causes.append("provider_failure")
    if any("missing effective price" in blocker for blocker in blockers):
        causes.append("missing_price")
    if data_status == "stale" or any("data_status=stale" in blocker for blocker in blockers):
        causes.append("stale_or_off_session")
    if "halt_status=HALTED" in blockers:
        causes.append("halted")
    if confidence not in {None, "OK"}:
        causes.append("confidence")
    if not causes:
        causes.append("unknown")
    return _dedupe(causes)


def _signal_row_to_check(row: dict[str, Any]) -> dict[str, Any]:
    confidence = row.get("confidence")
    data_status = row.get("data_status")
    blockers = []
    if data_status in {"provider_failure", "stale", "no_providers"}:
        blockers.append(f"data_status={data_status}")
    if confidence != "OK":
        blockers.append(f"confidence={confidence or 'unknown'}")
    return {
        "ticker": row.get("ticker"),
        "readiness": "ready" if not blockers else "blocked",
        "confidence": confidence,
        "gap_basis": row.get("gap_basis"),
        "data_status": data_status,
        "as_of_et": row.get("as_of_et"),
        "blockers": blockers,
        "provider_failures": row.get("provider_failures") or {},
    }


def _empty_root_causes() -> dict[str, list[str]]:
    return {key: [] for key in ROOT_CAUSE_KEYS}


def _one_liner(
    *,
    ready_count: int,
    blocked_count: int,
    root_causes: dict[str, list[str]],
) -> str:
    primary_keys = ["provider_failure", "stale_or_off_session", "halted"]
    secondary_keys = ["missing_price", "confidence", "unknown"]
    causes = [
        f"{key}={len(values)}"
        for key in primary_keys
        if (values := root_causes.get(key))
    ]
    if not causes:
        causes = [
            f"{key}={len(values)}"
            for key in secondary_keys
            if (values := root_causes.get(key))
        ]
    if not causes:
        cause_text = "none"
    else:
        cause_text = ", ".join(causes)
    return f"{ready_count} ready, {blocked_count} blocked. Main blockers: {cause_text}."


def _next_actions(root_causes: dict[str, list[str]]) -> list[str]:
    actions = []
    if root_causes.get("provider_failure"):
        actions.append("Check provider connectivity/credentials before trusting Lance output.")
    if root_causes.get("missing_price"):
        actions.append("Resolve missing effective price before calculating moves or RVOL.")
    if root_causes.get("stale_or_off_session"):
        actions.append("Resolve stale/off-session data before treating rows as live.")
    if root_causes.get("halted"):
        actions.append("Keep halted names blocked until the halt feed shows resumed status.")
    if root_causes.get("confidence"):
        actions.append("Review non-OK confidence rows before upgrading any setup.")
    if not actions:
        actions.append("Data doctor found no blocking root causes.")
    return actions


def _dedupe(values: list[str]) -> list[str]:
    output = []
    for value in values:
        if value not in output:
            output.append(value)
    return output
