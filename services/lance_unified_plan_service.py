from __future__ import annotations

from pathlib import Path
from typing import Any


DISCLAIMER = (
    "Unified Lance plans are not buy/sell advice. They combine daily/swing "
    "context with intraday timing references from the data layer; verify before acting."
)


class LanceUnifiedPlanService:
    """Compose Lance daily/swing context with intraday timing."""

    def __init__(
        self,
        *,
        swing_service: Any | None = None,
        intraday_service: Any | None = None,
        memory_service: Any | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        self.swing_service = swing_service
        self.intraday_service = intraday_service
        self.memory_service = memory_service
        self.db_path = db_path

    def build(
        self,
        *,
        tickers: list[str] | str,
        lookback_days: int = 60,
        intraday_plans: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        resolved = _parse_tickers(tickers)
        overrides = _normalize_plan_overrides(intraday_plans)
        plans = [
            self._build_plan(
                ticker,
                lookback_days=lookback_days,
                intraday_plan=overrides.get(ticker),
            )
            for ticker in resolved
        ]
        plans.sort(key=lambda row: (row["rank_score"], row["ticker"]), reverse=True)
        return {
            "agent_name": "lance_unified",
            "strategy": "Lance daily/swing context plus intraday timing",
            "timeframe": "daily_plus_intraday",
            "ticker_count": len(resolved),
            "plan_count": len(plans),
            "plans": plans,
            "groups": _group_plans(plans),
            "disclaimer": DISCLAIMER,
        }

    def build_plan(self, ticker: str, *, lookback_days: int = 60) -> dict[str, Any]:
        return self._build_plan(ticker, lookback_days=lookback_days, intraday_plan=None)

    def _build_plan(
        self,
        ticker: str,
        *,
        lookback_days: int = 60,
        intraday_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("ticker is required.")

        intraday = intraday_plan or self._intraday_service().build_plan(normalized)
        swing = self._build_swing_plan(
            normalized,
            lookback_days=lookback_days,
            data_quality_override=_data_quality_override_from_plan(intraday_plan),
        )
        conflict_flags = _conflict_flags(swing, intraday)
        alignment = _alignment(swing, intraday, conflict_flags)
        action_mode = _action_mode(swing, intraday, alignment)
        outcome_memory = self._outcome_memory(
            ticker=normalized,
            action_mode=action_mode,
            alignment=alignment,
        )
        return {
            "ticker": normalized,
            "trader": "lance_breitstein",
            "primary_timeframe": _primary_timeframe(action_mode, swing, intraday),
            "action_mode": action_mode,
            "alignment": alignment,
            "conflict_flags": conflict_flags,
            "rank_score": _rank_score(action_mode, swing, intraday),
            "thesis": _thesis(action_mode, swing, intraday),
            "outcome_memory": outcome_memory,
            "swing": _compact_layer(swing),
            "intraday": _compact_layer(intraday),
            "waiting_for": _merge_policy_lists(
                swing.get("waiting_for"),
                intraday.get("waiting_for"),
            ),
            "invalidates_if": _merge_policy_lists(
                swing.get("invalidates_if"),
                intraday.get("invalidates_if"),
            ),
            "manual_review_questions": _merge_policy_lists(
                swing.get("manual_review_questions"),
                intraday.get("manual_review_questions"),
            ),
            "next_step": _next_step(action_mode),
            "raw_plans": {
                "swing": swing,
                "intraday": intraday,
            },
            "disclaimer": DISCLAIMER,
        }

    def _swing_service(self) -> Any:
        if self.swing_service is None:
            from services.lance_swing_plan_service import LanceSwingPlanService

            self.swing_service = LanceSwingPlanService()
        return self.swing_service

    def _build_swing_plan(
        self,
        ticker: str,
        *,
        lookback_days: int,
        data_quality_override: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if data_quality_override is None:
            return self._swing_service().build_plan(ticker, lookback_days=lookback_days)
        return self._swing_service().build_plan(
            ticker,
            lookback_days=lookback_days,
            data_quality_override=data_quality_override,
        )

    def _intraday_service(self) -> Any:
        if self.intraday_service is None:
            from services.lance_intraday_plan_service import LanceIntradayPlanService

            self.intraday_service = LanceIntradayPlanService()
        return self.intraday_service

    def _memory_service(self) -> Any | None:
        if self.memory_service is not None:
            return self.memory_service
        if self.db_path is None:
            return None
        from services.lance_memory_report_service import LanceMemoryReportService

        self.memory_service = LanceMemoryReportService(db_path=self.db_path)
        return self.memory_service

    def _outcome_memory(
        self,
        *,
        ticker: str,
        action_mode: str,
        alignment: str,
    ) -> dict[str, Any]:
        memory_service = self._memory_service()
        if memory_service is None:
            return {
                "status": "UNAVAILABLE",
                "outcome_count": 0,
                "matching_action_mode": None,
                "matching_alignment": None,
                "recent_outcomes": [],
                "note": "No Lance memory service configured; do not infer outcome history.",
            }
        report = memory_service.summarize(ticker=ticker, limit=100)
        return {
            "status": report.get("status"),
            "outcome_count": report.get("outcome_count", 0),
            "matching_action_mode": _find_group(
                report.get("by_action_mode") or [],
                "action_mode",
                action_mode,
            ),
            "matching_alignment": _find_group(
                report.get("by_alignment") or [],
                "alignment",
                alignment,
            ),
            "recent_outcomes": list(report.get("recent_outcomes") or [])[:5],
            "note": "Journaled outcomes only; not P&L, prediction, or trade advice.",
        }


def _parse_tickers(tickers: list[str] | str) -> list[str]:
    raw = tickers.split(",") if isinstance(tickers, str) else tickers
    seen: set[str] = set()
    output: list[str] = []
    for value in raw:
        normalized = str(value or "").strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    if not output:
        raise ValueError("at least one ticker is required.")
    return output


def _normalize_plan_overrides(
    plans: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if not plans:
        return {}
    output = {}
    for ticker, plan in plans.items():
        normalized = str(ticker or "").strip().upper()
        if normalized and isinstance(plan, dict):
            output[normalized] = plan
    return output


def _data_quality_override_from_plan(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(plan, dict):
        return None
    data_quality = plan.get("data_quality")
    if not isinstance(data_quality, dict):
        return None
    return dict(data_quality)


def _compact_layer(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": plan.get("ticker"),
        "state": plan.get("state"),
        "lance_quality_grade": plan.get("lance_quality_grade"),
        "playbook": plan.get("playbook") or plan.get("setup_name"),
        "state_reason": plan.get("state_reason"),
        "data_quality": plan.get("data_quality") or {},
        "waiting_for": list(plan.get("waiting_for") or []),
        "invalidates_if": list(plan.get("invalidates_if") or []),
        "trigger_reference": plan.get("trigger_reference"),
        "risk_reference": plan.get("risk_reference"),
        "daily_context": plan.get("daily_context"),
        "relative_strength": plan.get("relative_strength"),
    }


def _find_group(rows: list[dict[str, Any]], key: str, value: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get(key) == value:
            return row
    return None


def _conflict_flags(swing: dict[str, Any], intraday: dict[str, Any]) -> list[str]:
    swing_state = str(swing.get("state") or "")
    intraday_state = str(intraday.get("state") or "")
    flags = []
    if swing_state == "active_watch" and intraday_state == "invalidated":
        flags.append("intraday_invalidated_daily_active")
    if swing_state == "invalidated" and intraday_state == "triggered_reference":
        flags.append("intraday_trigger_against_invalid_daily")
    if _is_blocked(swing) and not _is_blocked(intraday):
        flags.append("swing_data_blocked")
    if _is_blocked(intraday) and not _is_blocked(swing):
        flags.append("intraday_data_blocked")
    return flags


def _alignment(
    swing: dict[str, Any],
    intraday: dict[str, Any],
    conflict_flags: list[str],
) -> str:
    if _is_blocked(swing) or _is_blocked(intraday):
        return "blocked"
    if conflict_flags:
        return "conflict"
    swing_state = str(swing.get("state") or "")
    intraday_state = str(intraday.get("state") or "")
    if swing_state in {"active_watch", "confirmation_needed"} and intraday_state in {
        "waiting_for_turn",
        "setup_forming",
        "triggered_reference",
    }:
        return "aligned"
    if swing_state == "invalidated":
        return "not_aligned"
    return "mixed"


def _action_mode(
    swing: dict[str, Any],
    intraday: dict[str, Any],
    alignment: str,
) -> str:
    swing_state = str(swing.get("state") or "")
    intraday_state = str(intraday.get("state") or "")
    if alignment == "blocked":
        return "blocked"
    if alignment == "conflict":
        return "review"
    if swing_state == "invalidated" and intraday_state != "triggered_reference":
        return "ignore"
    if intraday_state == "triggered_reference" and swing_state in {
        "active_watch",
        "confirmation_needed",
    }:
        return "active_watch"
    if swing_state == "active_watch" and intraday_state in {
        "waiting_for_turn",
        "setup_forming",
    }:
        return "watch"
    if swing_state in {"active_watch", "confirmation_needed"}:
        return "carry"
    return "wait"


def _primary_timeframe(
    action_mode: str,
    swing: dict[str, Any],
    intraday: dict[str, Any],
) -> str:
    if action_mode in {"watch", "active_watch"}:
        return "daily_then_intraday"
    if action_mode == "carry":
        return "daily"
    if action_mode == "review" and intraday.get("state") == "triggered_reference":
        return "intraday_conflicts_with_daily"
    if action_mode == "blocked":
        return "data_quality"
    if swing.get("state") == "invalidated":
        return "daily_invalidated"
    return "context"


def _rank_score(
    action_mode: str,
    swing: dict[str, Any],
    intraday: dict[str, Any],
) -> float:
    score = {
        "active_watch": 100.0,
        "watch": 85.0,
        "carry": 65.0,
        "wait": 35.0,
        "review": 10.0,
        "ignore": -30.0,
        "blocked": -100.0,
    }.get(action_mode, 0.0)
    swing_score = swing.get("score")
    if isinstance(swing_score, int | float):
        score += min(float(swing_score), 100.0) / 10
    if intraday.get("state") == "triggered_reference":
        score += 10
    return round(score, 2)


def _thesis(action_mode: str, swing: dict[str, Any], intraday: dict[str, Any]) -> str:
    if action_mode == "blocked":
        return "Data quality blocks Lance evaluation on at least one timeframe."
    if action_mode == "review":
        return "Daily and intraday states conflict; Lance should review before carrying the idea."
    if action_mode == "ignore":
        return "Daily swing structure is invalidated and intraday does not restore the idea."
    if action_mode == "active_watch":
        return "Daily idea is valid and intraday reference is active."
    if action_mode == "watch":
        return "Daily idea is valid; intraday timing is still forming."
    if action_mode == "carry":
        return "Daily idea can carry forward, but intraday timing is not active."
    return "Lance has context, but no clean daily-plus-intraday plan yet."


def _next_step(action_mode: str) -> str:
    return {
        "active_watch": "Monitor only as a reference plan; require human verification.",
        "watch": "Keep on watch and wait for intraday confirmation.",
        "carry": "Carry the daily idea forward and re-check intraday conditions.",
        "wait": "Wait for either daily structure or intraday timing to improve.",
        "review": "Review the conflict manually before trusting the setup.",
        "ignore": "Keep off active Lance watch until daily structure repairs.",
        "blocked": "Fix missing/stale/conflicting data before making a judgment.",
    }.get(action_mode, "Review manually.")


def _merge_policy_lists(*values: Any) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        for item in value:
            text = str(item)
            if text and text not in seen:
                seen.add(text)
                output.append(text)
    return output


def _is_blocked(plan: dict[str, Any]) -> bool:
    if plan.get("state") == "blocked_data_quality":
        return True
    data_quality = plan.get("data_quality") or {}
    return data_quality.get("confidence") == "ERROR"


def _group_plans(plans: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {
        "active_watch": [],
        "watch": [],
        "carry": [],
        "wait": [],
        "review": [],
        "ignore": [],
        "blocked": [],
    }
    for plan in plans:
        key = str(plan.get("action_mode") or "wait")
        groups.setdefault(key, []).append(_plan_summary(plan))
    return groups


def _plan_summary(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": plan["ticker"],
        "action_mode": plan["action_mode"],
        "alignment": plan["alignment"],
        "primary_timeframe": plan["primary_timeframe"],
        "rank_score": plan["rank_score"],
        "thesis": plan["thesis"],
        "conflict_flags": list(plan.get("conflict_flags") or []),
        "swing_state": (plan.get("swing") or {}).get("state"),
        "intraday_state": (plan.get("intraday") or {}).get("state"),
        "waiting_for": list(plan.get("waiting_for") or []),
        "invalidates_if": list(plan.get("invalidates_if") or []),
    }
