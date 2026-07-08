from __future__ import annotations

from pathlib import Path
from typing import Any

from services.lance_market_scan_service import DISCLAIMER


class LanceDeskCycleService:
    """Run Lance's live desk loop as one repeatable operation."""

    def __init__(
        self,
        *,
        scan_service: Any | None = None,
        update_service: Any | None = None,
        timeline_service: Any | None = None,
        review_service: Any | None = None,
        carryover_service: Any | None = None,
        unified_service: Any | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        if scan_service is None:
            from services.lance_advanced_context_service import LanceAdvancedContextService

            scan_service = LanceAdvancedContextService(db_path=db_path)
        if update_service is None:
            from services.lance_desk_update_service import LanceDeskUpdateService

            update_service = LanceDeskUpdateService(db_path=db_path)
        if timeline_service is None:
            from services.lance_session_timeline_service import LanceSessionTimelineService

            timeline_service = LanceSessionTimelineService(db_path=db_path)
        if review_service is None:
            from services.lance_session_review_service import LanceSessionReviewService

            review_service = LanceSessionReviewService(db_path=db_path)
        if carryover_service is None:
            from services.lance_carryover_plan_service import LanceCarryoverPlanService

            carryover_service = LanceCarryoverPlanService(db_path=db_path)
        if unified_service is None:
            from services.lance_unified_plan_service import LanceUnifiedPlanService

            unified_service = LanceUnifiedPlanService(db_path=db_path)

        self.scan_service = scan_service
        self.update_service = update_service
        self.timeline_service = timeline_service
        self.review_service = review_service
        self.carryover_service = carryover_service
        self.unified_service = unified_service

    def run(
        self,
        *,
        tickers: list[str] | str | None = None,
        universe: str | list[str] | None = None,
        watchlist: str | list[str] | None = None,
        all_universes: bool = False,
        market: str | None = None,
        market_limit: int | None = None,
        min_gap_abs: float = 3.0,
        max_candidates: int = 20,
        persist: bool = True,
        session_id: str | None = None,
        max_workers: int = 1,
        include_caveated_context: bool = False,
        update_limit: int = 50,
        review_limit: int = 500,
        target_session_date: str | None = None,
        summary_limit: int = 5,
    ) -> dict[str, Any]:
        if not any([tickers, universe, watchlist, all_universes, market]):
            all_universes = True

        scan = self.scan_service.scan(
            tickers=tickers,
            universe=universe,
            watchlist=watchlist,
            all_universes=all_universes,
            market=market,
            market_limit=market_limit,
            min_gap_abs=min_gap_abs,
            max_candidates=max_candidates,
            persist=persist,
            session_id=session_id,
            max_workers=max_workers,
            include_caveated_context=include_caveated_context,
        )
        resolved_session_id = scan.get("session_id") or session_id
        unified = self._build_unified(scan)
        if resolved_session_id is None:
            return _cycle_output(
                session_id=None,
                status=str(scan.get("status") or "EMPTY"),
                scan=scan,
                unified=unified,
                update=_empty_update(None),
                timeline=_empty_timeline(None),
                review=_empty_review(None),
                carryover=_empty_carryover(None, target_session_date),
                summary_limit=summary_limit,
            )

        update = self.update_service.update(
            session_id=resolved_session_id,
            limit=update_limit,
            persist=persist,
        )
        timeline = self.timeline_service.timeline(
            session_id=resolved_session_id,
            limit=review_limit,
        )
        review = self.review_service.review(
            session_id=resolved_session_id,
            limit=review_limit,
        )
        carryover = self.carryover_service.build(
            session_id=resolved_session_id,
            target_session_date=target_session_date,
            limit=review_limit,
        )

        return _cycle_output(
            session_id=resolved_session_id,
            status=_cycle_status(scan),
            scan=scan,
            unified=unified,
            update=update,
            timeline=timeline,
            review=review,
            carryover=carryover,
            summary_limit=summary_limit,
        )

    def _build_unified(self, scan: dict[str, Any]) -> dict[str, Any]:
        tickers = _watchlist_tickers(scan)
        if not tickers:
            return _empty_unified()
        intraday_plans = _watchlist_intraday_plans(scan)
        try:
            if intraday_plans:
                return self.unified_service.build(
                    tickers=tickers,
                    intraday_plans=intraday_plans,
                )
            return self.unified_service.build(tickers=tickers)
        except Exception as exc:
            return {
                "agent_name": "lance_unified",
                "status": "ERROR",
                "plan_count": 0,
                "plans": [],
                "groups": {},
                "notes": [f"Unified Lance plan failed: {exc}"],
            }


def _cycle_output(
    *,
    session_id: str | None,
    status: str,
    scan: dict[str, Any],
    unified: dict[str, Any],
    update: dict[str, Any],
    timeline: dict[str, Any],
    review: dict[str, Any],
    carryover: dict[str, Any],
    summary_limit: int,
) -> dict[str, Any]:
    return {
        "agent_name": "lance_intraday",
        "mode": "desk_cycle",
        "strategy": "Advanced Lance desk cycle",
        "status": status,
        "session_id": session_id,
        "steps": [
            "run_advanced_lance_scan",
            "build_lance_unified_plan",
            "update_lance_watchlist",
            "get_lance_session_timeline",
            "review_lance_session",
            "build_lance_carryover_plan",
        ],
        "scan_summary": _scan_summary(scan),
        "unified_summary": _unified_summary(unified),
        "updates_summary": _updates_summary(update),
        "timeline_summary": _timeline_summary(timeline),
        "review_summary": _review_summary(review),
        "carryover_summary": _carryover_summary(carryover),
        "market_context": scan.get("market_context") or {},
        "unified_plans": list(unified.get("plans") or [])[:summary_limit],
        "unified_carryover": _unified_carryover(unified),
        "top_watchlist": _top_watchlist(scan, unified, summary_limit),
        "top_updates": list(update.get("updates") or [])[:summary_limit],
        "pending_reviews": list(review.get("pending_reviews") or [])[:summary_limit],
        "carryover_groups": carryover.get("groups") or {},
        "handoff_prompt": (
            "Present Lance as a watchlist/playbook co-pilot: explain what is in play, "
            "what changed, what needs manual review, and what must be freshly confirmed. "
            "Do not call entries, exits, position size, or targets beyond tool-provided references."
        ),
        "disclaimer": scan.get("disclaimer") or DISCLAIMER,
    }


def _cycle_status(scan: dict[str, Any]) -> str:
    return str(scan.get("status") or "UNKNOWN")


def _scan_summary(scan: dict[str, Any]) -> dict[str, Any]:
    watchlist = list(scan.get("watchlist") or [])
    return {
        "status": scan.get("status"),
        "scanned_count": scan.get("scanned_count"),
        "candidate_count": scan.get("candidate_count"),
        "returned_watchlist_count": len(watchlist),
    }


def _unified_summary(unified: dict[str, Any]) -> dict[str, Any]:
    plans = list(unified.get("plans") or [])
    if not plans:
        return {
            "status": unified.get("status") or "EMPTY",
            "plan_count": 0,
            "watch_count": 0,
            "review_count": 0,
            "blocked_count": 0,
        }
    return {
        "status": unified.get("status") or "OK",
        "plan_count": len(plans),
        "watch_count": sum(
            1 for plan in plans if plan.get("action_mode") in {"active_watch", "watch", "carry"}
        ),
        "review_count": sum(1 for plan in plans if plan.get("action_mode") == "review"),
        "blocked_count": sum(1 for plan in plans if plan.get("action_mode") == "blocked"),
    }


def _updates_summary(update: dict[str, Any]) -> dict[str, Any]:
    updates = list(update.get("updates") or [])
    return {
        "status": update.get("status"),
        "tracked_count": update.get("tracked_count"),
        "updated_count": update.get("updated_count"),
        "state_changed_count": sum(1 for row in updates if row.get("state_changed") is True),
    }


def _timeline_summary(timeline: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": timeline.get("status"),
        "event_count": timeline.get("event_count", 0),
        "ticker_count": len(timeline.get("tickers") or []),
    }


def _review_summary(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": review.get("status"),
        "pending_count": review.get("pending_count"),
        "reviewed_count": review.get("reviewed_count"),
    }


def _carryover_summary(carryover: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": carryover.get("status"),
        "carryover_count": carryover.get("carryover_count"),
        "fresh_scan_required": carryover.get("fresh_scan_required", True),
    }


def _top_watchlist(
    scan: dict[str, Any],
    unified: dict[str, Any],
    summary_limit: int,
) -> list[dict[str, Any]]:
    unified_rows = [_unified_row(plan) for plan in list(unified.get("plans") or [])]
    if unified_rows:
        return unified_rows[:summary_limit]
    return list(scan.get("watchlist") or [])[:summary_limit]


def _unified_carryover(unified: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {
        "carry_forward": [],
        "manual_review": [],
        "blocked": [],
        "ignore": [],
    }
    for plan in unified.get("plans") or []:
        row = _unified_carryover_row(plan)
        groups[_unified_carryover_group(plan)].append(row)
    return {
        "summary": {
            "carry_forward_count": len(groups["carry_forward"]),
            "manual_review_count": len(groups["manual_review"]),
            "blocked_count": len(groups["blocked"]),
            "ignore_count": len(groups["ignore"]),
        },
        "groups": groups,
        "note": (
            "Unified carryover is derived from current daily-plus-intraday plan state; "
            "it is not an order plan."
        ),
    }


def _unified_carryover_group(plan: dict[str, Any]) -> str:
    action_mode = str(plan.get("action_mode") or "")
    if action_mode in {"active_watch", "watch", "carry"}:
        return "carry_forward"
    if action_mode == "review":
        return "manual_review"
    if action_mode == "blocked":
        return "blocked"
    return "ignore"


def _unified_carryover_row(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": plan.get("ticker"),
        "action_mode": plan.get("action_mode"),
        "alignment": plan.get("alignment"),
        "primary_timeframe": plan.get("primary_timeframe"),
        "thesis": plan.get("thesis"),
        "waiting_for": list(plan.get("waiting_for") or []),
        "invalidates_if": list(plan.get("invalidates_if") or []),
        "conflict_flags": list(plan.get("conflict_flags") or []),
    }


def _unified_row(plan: dict[str, Any]) -> dict[str, Any]:
    swing = plan.get("swing") or {}
    intraday = plan.get("intraday") or {}
    data_quality = intraday.get("data_quality") or swing.get("data_quality") or {}
    return {
        "ticker": plan.get("ticker"),
        "state": plan.get("action_mode"),
        "score": plan.get("rank_score"),
        "action_mode": plan.get("action_mode"),
        "alignment": plan.get("alignment"),
        "primary_timeframe": plan.get("primary_timeframe"),
        "swing_state": swing.get("state"),
        "intraday_state": intraday.get("state"),
        "swing_grade": swing.get("lance_quality_grade"),
        "intraday_grade": intraday.get("lance_quality_grade"),
        "swing_playbook": swing.get("playbook"),
        "intraday_playbook": intraday.get("playbook"),
        "thesis": plan.get("thesis"),
        "waiting_for": list(plan.get("waiting_for") or []),
        "invalidates_if": list(plan.get("invalidates_if") or []),
        "manual_review_questions": list(plan.get("manual_review_questions") or []),
        "conflict_flags": list(plan.get("conflict_flags") or []),
        "data_quality": data_quality,
        "unified_plan": plan,
    }


def _watchlist_tickers(scan: dict[str, Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for row in scan.get("watchlist") or []:
        ticker = str((row or {}).get("ticker") or "").strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            output.append(ticker)
    return output


def _watchlist_intraday_plans(scan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in scan.get("watchlist") or []:
        ticker = str((row or {}).get("ticker") or "").strip().upper()
        plan = (row or {}).get("plan")
        if ticker and isinstance(plan, dict):
            output[ticker] = plan
    return output


def _empty_unified() -> dict[str, Any]:
    return {
        "agent_name": "lance_unified",
        "status": "EMPTY",
        "plan_count": 0,
        "plans": [],
        "groups": {},
    }


def _empty_update(session_id: str | None) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "status": "EMPTY",
        "tracked_count": 0,
        "updated_count": 0,
        "updates": [],
    }


def _empty_timeline(session_id: str | None) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "status": "EMPTY",
        "event_count": 0,
        "tickers": [],
    }


def _empty_review(session_id: str | None) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "status": "EMPTY",
        "pending_count": 0,
        "reviewed_count": 0,
        "pending_reviews": [],
    }


def _empty_carryover(session_id: str | None, target_session_date: str | None) -> dict[str, Any]:
    return {
        "source_session_id": session_id,
        "target_session_date": target_session_date,
        "status": "EMPTY",
        "carryover_count": 0,
        "fresh_scan_required": True,
        "groups": {},
    }
