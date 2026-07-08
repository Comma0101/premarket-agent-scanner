from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db import (
    get_lance_watchlist_items,
    get_lance_watchlist_events,
    get_latest_lance_session_id,
    insert_lance_watchlist_event,
    upsert_lance_watchlist_item,
)
from services.lance_intraday_plan_service import LanceIntradayPlanService
from services.lance_market_scan_service import (
    DISCLAIMER,
    _candidate_from_plan,
)


class LanceDeskUpdateService:
    """Refresh a persisted Lance watchlist and report session changes."""

    def __init__(
        self,
        *,
        plan_service: Any | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        self.plan_service = plan_service or LanceIntradayPlanService()
        self.db_path = db_path

    def update(
        self,
        *,
        session_id: str | None = None,
        limit: int = 50,
        persist: bool = True,
    ) -> dict[str, Any]:
        resolved_session_id = session_id or get_latest_lance_session_id(
            self.db_path,
            exclude_session_id_suffix="-lance-swing",
        )
        if resolved_session_id is None:
            return {
                "agent_name": "lance_intraday",
                "strategy": "Lance Breitstein desk-mode watchlist update",
                "session_id": None,
                "status": "EMPTY",
                "tracked_count": 0,
                "updated_count": 0,
                "updates": [],
                "notes": ["No persisted Lance watchlist session found."],
                "disclaimer": DISCLAIMER,
            }

        prior_rows = get_lance_watchlist_items(
            self.db_path,
            session_id=resolved_session_id,
            limit=500,
        )
        prior_rows = _select_rows_for_update(
            prior_rows,
            get_lance_watchlist_events(
                self.db_path,
                session_id=resolved_session_id,
                limit=500,
            ),
            limit=limit,
        )
        if not prior_rows:
            return {
                "agent_name": "lance_intraday",
                "strategy": "Lance Breitstein desk-mode watchlist update",
                "session_id": resolved_session_id,
                "status": "EMPTY",
                "tracked_count": 0,
                "updated_count": 0,
                "updates": [],
                "notes": ["No Lance watchlist rows found for the requested session."],
                "disclaimer": DISCLAIMER,
            }

        updates = []
        for prior in prior_rows:
            current_plan = self._build_plan(str(prior["ticker"]))
            candidate = _candidate_from_plan(str(prior["ticker"]), current_plan)
            update = _build_update(prior, candidate)
            updates.append(update)
            if persist:
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
                    event_type="update",
                    state=candidate["state"],
                    score=candidate["score"],
                    data_quality=candidate["data_quality"],
                    payload={
                        "previous_state": update["previous_state"],
                        "current_state": update["current_state"],
                        "state_changed": update["state_changed"],
                        "score_delta": update["score_delta"],
                        "gap_pct_delta": update["gap_pct_delta"],
                        "rel_volume_delta": update["rel_volume_delta"],
                        "change_flags": update["change_flags"],
                        "why_now": update["why_now"],
                        "trigger_reference": update["trigger_reference"],
                        "risk_reference": update["risk_reference"],
                        "target_reference": update["target_reference"],
                    },
                )

        updates.sort(
            key=lambda row: (
                bool(row["state_changed"]),
                abs(row["score_delta"] or 0),
                row["current_score"],
            ),
            reverse=True,
        )
        return {
            "agent_name": "lance_intraday",
            "strategy": "Lance Breitstein desk-mode watchlist update",
            "session_id": resolved_session_id,
            "status": "OK",
            "tracked_count": len(prior_rows),
            "updated_count": len(updates),
            "updates": updates,
            "notes": [],
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
                    "data_caveat": f"Lance update failed: {exc}",
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


def _build_update(prior: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    prior_quality = prior.get("data_quality") or {}
    current_quality = current.get("data_quality") or {}
    previous_score = float(prior.get("score") or 0)
    current_score = float(current.get("score") or 0)
    previous_state = str(prior.get("state") or "unknown")
    current_state = str(current.get("state") or "unknown")
    score_delta = round(current_score - previous_score, 2)
    gap_pct_delta = _delta(current_quality.get("gap_pct"), prior_quality.get("gap_pct"))
    rel_volume_delta = _delta(current_quality.get("rel_volume"), prior_quality.get("rel_volume"))
    flags = _change_flags(
        previous_state=previous_state,
        current_state=current_state,
        score_delta=score_delta,
        gap_pct_delta=gap_pct_delta,
        rel_volume_delta=rel_volume_delta,
        current=current,
    )
    return {
        "ticker": current["ticker"],
        "previous_state": previous_state,
        "current_state": current_state,
        "state_changed": previous_state != current_state,
        "previous_score": previous_score,
        "current_score": current_score,
        "score_delta": score_delta,
        "gap_pct_delta": gap_pct_delta,
        "rel_volume_delta": rel_volume_delta,
        "change_flags": flags,
        "why_before": prior.get("why_watching"),
        "why_now": current["why_watching"],
        "invalidates_if": current["invalidates_if"],
        "next_step": current["next_step"],
        "data_quality": current_quality,
        "trigger_reference": current["trigger_reference"],
        "risk_reference": current["risk_reference"],
        "target_reference": current["target_reference"],
        "current_plan": current["plan"],
    }


def _delta(current: Any, previous: Any) -> float | None:
    if isinstance(current, int | float) and isinstance(previous, int | float):
        return round(float(current) - float(previous), 2)
    return None


def _change_flags(
    *,
    previous_state: str,
    current_state: str,
    score_delta: float,
    gap_pct_delta: float | None,
    rel_volume_delta: float | None,
    current: dict[str, Any],
) -> list[str]:
    flags = []
    if previous_state != current_state:
        flags.append("state_changed")
    if score_delta >= 15:
        flags.append("score_improved")
    elif score_delta <= -15:
        flags.append("score_deteriorated")
    if rel_volume_delta is not None:
        if rel_volume_delta >= 1:
            flags.append("rvol_expanded")
        elif rel_volume_delta <= -1:
            flags.append("rvol_faded")
    if gap_pct_delta is not None:
        if abs(gap_pct_delta) >= 2:
            flags.append("move_expanded")
        elif abs(gap_pct_delta) <= 0.25:
            flags.append("move_stalled")
    if current.get("trigger_reference") is not None:
        flags.append("has_trigger_reference")
    if not flags:
        flags.append("no_material_change")
    return flags


def _select_rows_for_update(
    rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    row_by_ticker = {str(row["ticker"]): row for row in rows}
    selected = []
    seen: set[str] = set()
    for event in reversed(events):
        ticker = str(event["ticker"])
        if ticker in seen or ticker not in row_by_ticker:
            continue
        selected.append(row_by_ticker[ticker])
        seen.add(ticker)
        if len(selected) >= max(0, int(limit)):
            return selected
    for row in rows:
        ticker = str(row["ticker"])
        if ticker in seen:
            continue
        selected.append(row)
        if len(selected) >= max(0, int(limit)):
            break
    return selected
