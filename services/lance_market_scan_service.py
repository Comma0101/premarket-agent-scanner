from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db import insert_lance_watchlist_event, upsert_lance_watchlist_item
from app.models import ScanFilters, ScanRunOutput
from services.lance_intraday_plan_service import LanceIntradayPlanService
from services.scanner_service import ScannerService
from services.session_time_service import ny_date_for


DISCLAIMER = "Matches your filter - not buy/sell advice. Verify before acting."


class LanceMarketScanService:
    """Build Lance Breitstein-style intraday watchlists from a market scan."""

    def __init__(
        self,
        *,
        scanner_service: Any | None = None,
        plan_service: Any | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        self.scanner_service = scanner_service or ScannerService(persist=False, db_path=db_path)
        self.plan_service = plan_service or LanceIntradayPlanService()
        self.db_path = db_path

    def scan(
        self,
        *,
        universe: str | list[str] | None = None,
        watchlist: str | list[str] | None = None,
        tickers: list[str] | str | None = None,
        all_universes: bool = False,
        min_gap_abs: float = 3.0,
        max_candidates: int = 20,
        include_caveated_context: bool = False,
        persist: bool = False,
        session_id: str | None = None,
        max_workers: int = 1,
    ) -> dict[str, Any]:
        scan_output = self.scanner_service.scan(
            universe=universe,
            watchlist=watchlist,
            tickers=tickers,
            all_universes=all_universes,
            filters=ScanFilters(
                min_market_cap=0,
                min_gap_abs=min_gap_abs,
                direction="both",
                include_low_confidence=include_caveated_context,
            ),
            max_workers=max_workers,
        )
        resolved_session_id = session_id or _session_id(scan_output)
        candidate_tickers = _candidate_tickers(scan_output.results, tickers)
        candidate_limit = max(0, int(max_candidates))
        candidate_tickers = candidate_tickers[:candidate_limit]
        candidates = [
            _candidate_from_plan(ticker, self._build_plan(ticker))
            for ticker in candidate_tickers
        ]
        candidates.sort(key=lambda row: (row["score"], abs(row["gap_pct"] or 0)), reverse=True)
        limited_candidates = candidates[:candidate_limit]

        if persist:
            for candidate in limited_candidates:
                upsert_lance_watchlist_item(
                    self.db_path,
                    session_id=resolved_session_id,
                    ticker=candidate["ticker"],
                    state=candidate["state"],
                    score=candidate["score"],
                    playbook=candidate["playbook"],
                    why_watching=candidate["why_watching"],
                    invalidates_if=candidate["invalidates_summary"],
                    next_step=candidate["next_step"],
                    data_quality=candidate["data_quality"],
                    plan=candidate["plan"],
                )
                insert_lance_watchlist_event(
                    self.db_path,
                    session_id=resolved_session_id,
                    ticker=candidate["ticker"],
                    event_type="scan",
                    state=candidate["state"],
                    score=candidate["score"],
                    data_quality=candidate["data_quality"],
                    payload={
                        "playbook": candidate["playbook"],
                        "why_watching": candidate["why_watching"],
                        "invalidates_if": candidate["invalidates_if"],
                        "invalidates_summary": candidate["invalidates_summary"],
                        "next_step": candidate["next_step"],
                        "trigger_reference": candidate["trigger_reference"],
                        "risk_reference": candidate["risk_reference"],
                        "target_reference": candidate["target_reference"],
                    },
                )

        return {
            "agent_name": "lance_intraday",
            "strategy": "Lance Breitstein intraday market scan",
            "session_id": resolved_session_id,
            "status": scan_output.status,
            "selection": scan_output.universe,
            "source_run_id": scan_output.run_id,
            "scanned_count": len(scan_output.results),
            "candidate_count": len(candidates),
            "watchlist": limited_candidates,
            "triage_context": _triage_context(include_caveated_context),
            "notes": list(scan_output.notes),
            "disclaimer": DISCLAIMER,
        }

    def _build_plan(self, ticker: str) -> dict[str, Any]:
        try:
            return self.plan_service.build_plan(ticker)
        except Exception as exc:
            return {
                "ticker": ticker.upper(),
                "trader": "lance_breitstein",
                "setup_name": "mean_reversion_after_capitulation",
                "state": "blocked_data_quality",
                "state_reason": "Data quality blocks Lance evaluation.",
                "front_side_status": "blocked",
                "lance_quality_grade": "REJECT",
                "data_quality": {
                    "confidence": "ERROR",
                    "gap_basis": None,
                    "data_caveat": f"Lance plan failed: {exc}",
                },
                "conditions": {"data_quality": {"status": "BLOCKED"}},
                "trigger_reference": None,
                "risk_reference": None,
                "target_reference": None,
                "missing_fields": ["lance_plan"],
                "waiting_for": ["Data quality must return to OK with clear gap basis."],
                "invalidates_if": ["data quality remains blocked"],
                "manual_review_questions": [
                    "Was missing or stale data resolved before making any judgment?"
                ],
                "next_step": "Fix the data path before evaluating this ticker.",
                "disclaimer": DISCLAIMER,
            }


def _candidate_from_plan(ticker: str, plan: dict[str, Any]) -> dict[str, Any]:
    data_quality = plan.get("data_quality") or {}
    state = str(plan.get("state") or "unknown")
    playbook = str(plan.get("setup_name") or "mean_reversion_after_capitulation")
    score = _score_plan(plan)
    invalidates_if = _policy_list(plan.get("invalidates_if"), fallback=_invalidates_if(plan))
    return {
        "ticker": str(plan.get("ticker") or ticker).upper(),
        "state": state,
        "score": score,
        "playbook": playbook,
        "state_reason": plan.get("state_reason"),
        "front_side_status": plan.get("front_side_status"),
        "lance_quality_grade": plan.get("lance_quality_grade"),
        "why_watching": _why_watching(plan),
        "waiting_for": _policy_list(plan.get("waiting_for")),
        "invalidates_if": invalidates_if,
        "invalidates_summary": _join_policy_list(invalidates_if),
        "manual_review_questions": _policy_list(plan.get("manual_review_questions")),
        "next_step": plan.get("next_step"),
        "gap_pct": data_quality.get("gap_pct"),
        "rel_volume": data_quality.get("rel_volume"),
        "data_quality": data_quality,
        "conditions": plan.get("conditions") or {},
        "trigger_reference": plan.get("trigger_reference"),
        "risk_reference": plan.get("risk_reference"),
        "target_reference": plan.get("target_reference"),
        "missing_fields": list(plan.get("missing_fields") or []),
        "plan": plan,
    }


def _triage_context(include_caveated_context: bool) -> dict[str, Any]:
    if not include_caveated_context:
        return {
            "include_caveated_context": False,
            "filter_confidence": "OK_ONLY",
            "caveat": None,
        }
    return {
        "include_caveated_context": True,
        "filter_confidence": "ALLOW_CAVEATED_CONTEXT",
        "caveat": (
            "Caveated context may include STALE_DATA, CONFLICT, or LOW_CONFIDENCE rows; "
            "Lance data gates still block them from A_WATCH/live execution context."
        ),
    }


def _candidate_tickers(
    scan_results: list[Any],
    explicit_tickers: list[str] | str | None,
) -> list[str]:
    tickers: list[str] = []
    seen: set[str] = set()
    for result in scan_results:
        _append_ticker(tickers, seen, result.ticker)
    for ticker in _parse_explicit_tickers(explicit_tickers):
        _append_ticker(tickers, seen, ticker)
    return tickers


def _parse_explicit_tickers(tickers: list[str] | str | None) -> list[str]:
    if tickers is None:
        return []
    if isinstance(tickers, str):
        raw_values = tickers.split(",")
    else:
        raw_values = tickers
    return [value.strip().upper() for value in raw_values if value and value.strip()]


def _append_ticker(output: list[str], seen: set[str], ticker: str) -> None:
    normalized = str(ticker or "").strip().upper()
    if not normalized or normalized in seen:
        return
    seen.add(normalized)
    output.append(normalized)


def _score_plan(plan: dict[str, Any]) -> float:
    data_quality = plan.get("data_quality") or {}
    conditions = plan.get("conditions") or {}
    state = plan.get("state")
    gap_pct = data_quality.get("gap_pct")
    rel_volume = data_quality.get("rel_volume")
    score = 0.0

    if isinstance(gap_pct, int | float):
        move = abs(float(gap_pct))
        if move >= 3:
            score += 25
        if move >= 5:
            score += 10
        if move >= 10:
            score += 10

    if isinstance(rel_volume, int | float):
        rvol = float(rel_volume)
        if rvol >= 3:
            score += 35
        elif rvol >= 1:
            score += 10

    score += {
        "triggered_reference": 30,
        "setup_forming": 20,
        "watching": 5,
        "not_in_play": 0,
        "waiting_for_intraday_data": -15,
        "waiting_for_turn": 20,
        "invalidated": -40,
        "blocked_data_quality": -100,
    }.get(str(state), 0)

    if _condition_status(conditions, "prior_bar_break") == "PASS":
        score += 20
    if _condition_status(conditions, "volume_2x") == "PASS":
        score += 15
    if _condition_status(conditions, "consecutive_pressure") == "PASS":
        score += 10
    if _condition_status(conditions, "chop_filter") == "FAIL":
        score -= 25
    return score


def _condition_status(conditions: dict[str, Any], name: str) -> str | None:
    condition = conditions.get(name)
    if not isinstance(condition, dict):
        return None
    status = condition.get("status")
    return str(status) if status is not None else None


def _why_watching(plan: dict[str, Any]) -> str:
    ticker = str(plan.get("ticker") or "").upper()
    state = plan.get("state") or "unknown"
    data_quality = plan.get("data_quality") or {}
    gap_pct = _format_number(data_quality.get("gap_pct"))
    rel_volume = _format_number(data_quality.get("rel_volume"))
    confidence = data_quality.get("confidence") or "unknown"
    basis = data_quality.get("gap_basis") or "unknown_basis"
    return (
        f"{ticker}: {gap_pct}% move, {rel_volume}x RVOL, Lance state {state}; "
        f"data confidence={confidence}, gap_basis={basis}."
    )


def _invalidates_if(plan: dict[str, Any]) -> str:
    state = plan.get("state")
    if state == "blocked_data_quality":
        return "Data quality remains blocked or provider failures persist."
    if state == "invalidated":
        return "Chop/compression remains active."
    if plan.get("trigger_reference") is not None:
        return "Reference break fails, volume confirmation disappears, or chop develops."
    return "Abnormal move, RVOL participation, or intraday pressure does not improve."


def _policy_list(value: Any, *, fallback: str | None = None) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None and str(item)]
    if value is not None and str(value):
        return [str(value)]
    if fallback:
        return [fallback]
    return []


def _join_policy_list(values: list[str]) -> str | None:
    if not values:
        return None
    return "; ".join(values)


def _format_number(value: Any) -> str:
    if isinstance(value, int | float):
        return f"{float(value):.1f}"
    return "unknown"


def _session_id(scan_output: ScanRunOutput) -> str:
    day = ny_date_for(scan_output.started_at) or (scan_output.started_at or "")[:10] or "unknown-date"
    return f"{day}-lance-intraday"
