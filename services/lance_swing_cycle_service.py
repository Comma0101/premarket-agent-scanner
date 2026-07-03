from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db import insert_lance_watchlist_event, upsert_lance_watchlist_item
from app.models import utc_now_iso


DISCLAIMER = "Matches your filter - not buy/sell advice. Verify before acting."


class LanceSwingCycleService:
    """Run Lance's swing desk workflow and optionally persist the watchlist."""

    def __init__(
        self,
        *,
        swing_service: Any | None = None,
        universe_service: Any | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        if swing_service is None:
            from services.lance_swing_plan_service import LanceSwingPlanService

            swing_service = LanceSwingPlanService()
        if universe_service is None:
            from services.universe_service import UniverseService

            universe_service = UniverseService()

        self.swing_service = swing_service
        self.universe_service = universe_service
        self.db_path = db_path

    def run(
        self,
        *,
        tickers: list[str] | str | None = None,
        universe: str | list[str] | None = None,
        watchlist: str | list[str] | None = None,
        all_universes: bool = False,
        lookback_days: int = 60,
        persist: bool = False,
        session_id: str | None = None,
        summary_limit: int = 10,
    ) -> dict[str, Any]:
        if not any([tickers, universe, watchlist, all_universes]):
            all_universes = True

        resolved_tickers: list[str] | str
        selection_label = "MANUAL"
        selection_count = len(_parse_tickers(tickers)) if tickers else 0
        if any([universe, watchlist, all_universes]):
            selection = self.universe_service.resolve_selection(
                tickers=tickers,
                universe=universe,
                watchlist=watchlist,
                all_universes=all_universes,
            )
            resolved_tickers = selection.tickers
            selection_label = selection.label or "MANUAL"
            selection_count = len(selection.tickers)
        else:
            resolved_tickers = tickers or []

        resolved_session_id = session_id or _session_id()
        if not resolved_tickers:
            return _empty_output(
                session_id=resolved_session_id,
                selection=selection_label,
                selection_count=0,
            )

        swing = self.swing_service.build(
            tickers=resolved_tickers,
            lookback_days=lookback_days,
        )
        plans = list(swing.get("plans") or [])
        plans.sort(key=lambda plan: (-float(plan.get("score") or 0), str(plan.get("ticker") or "")))
        if persist:
            for plan in plans:
                _persist_plan(
                    self.db_path,
                    session_id=resolved_session_id,
                    plan=plan,
                )

        return {
            "agent_name": "lance_swing",
            "mode": "swing_cycle",
            "strategy": "Lance swing desk cycle",
            "session_id": resolved_session_id,
            "status": "OK",
            "selection": selection_label,
            "selection_count": selection_count,
            "lookback_days": lookback_days,
            "summary": _summary(swing),
            "groups": swing.get("groups") or {},
            "top_watchlist": plans[: max(0, int(summary_limit))],
            "notes": list(swing.get("notes") or []),
            "handoff_prompt": (
                "Present Lance swing output as a watchlist workflow: separate continuation "
                "from mean-reversion watches, name the reclaim/invalidation level, and never "
                "turn a watch into advice or an order instruction."
            ),
            "disclaimer": swing.get("disclaimer") or DISCLAIMER,
        }


def _persist_plan(
    db_path: str | Path | None,
    *,
    session_id: str,
    plan: dict[str, Any],
) -> None:
    ticker = str(plan.get("ticker") or "").upper()
    if not ticker:
        return
    state = str(plan.get("state") or "unknown")
    score = float(plan.get("score") or 0)
    playbook = str(plan.get("playbook") or "swing_context")
    data_quality = plan.get("data_quality") or {}
    why_watching = _why_watching(plan)
    invalidates_if = _join(plan.get("invalidates_if"))
    next_step = str(plan.get("next_step") or "")

    upsert_lance_watchlist_item(
        db_path,
        session_id=session_id,
        ticker=ticker,
        state=state,
        score=score,
        playbook=playbook,
        why_watching=why_watching,
        invalidates_if=invalidates_if,
        next_step=next_step,
        data_quality=data_quality,
        plan=plan,
    )
    insert_lance_watchlist_event(
        db_path,
        session_id=session_id,
        ticker=ticker,
        event_type="swing_scan",
        state=state,
        score=score,
        data_quality=data_quality,
        payload={
            "playbook": playbook,
            "why_watching": why_watching,
            "state_reason": plan.get("state_reason"),
            "waiting_for": list(plan.get("waiting_for") or []),
            "invalidates_if": list(plan.get("invalidates_if") or []),
            "next_step": next_step,
            "daily_context": plan.get("daily_context"),
            "relative_strength": plan.get("relative_strength"),
        },
    )


def _summary(swing: dict[str, Any]) -> dict[str, int]:
    groups = swing.get("groups") or {}
    return {
        "plan_count": int(swing.get("plan_count") or len(swing.get("plans") or [])),
        "active_watch_count": len(groups.get("active_watch") or []),
        "mean_reversion_watch_count": len(groups.get("mean_reversion_watch") or []),
        "watching_count": len(groups.get("watching") or []),
        "invalidated_count": len(groups.get("invalidated") or []),
        "blocked_count": len(groups.get("blocked") or []),
    }


def _why_watching(plan: dict[str, Any]) -> str:
    data_quality = plan.get("data_quality") or {}
    relative_strength = plan.get("relative_strength") or {}
    return (
        f"{plan.get('ticker')}: state={plan.get('state')}, playbook={plan.get('playbook')}, "
        f"gap_pct={_value(data_quality.get('gap_pct'))}, "
        f"rvol={_value(data_quality.get('rel_volume'))}, "
        f"rs={_value(relative_strength.get('classification'))}, "
        f"confidence={_value(data_quality.get('confidence'))}, "
        f"gap_basis={_value(data_quality.get('gap_basis'))}."
    )


def _empty_output(
    *,
    session_id: str,
    selection: str,
    selection_count: int,
) -> dict[str, Any]:
    return {
        "agent_name": "lance_swing",
        "mode": "swing_cycle",
        "strategy": "Lance swing desk cycle",
        "session_id": session_id,
        "status": "EMPTY",
        "selection": selection,
        "selection_count": selection_count,
        "summary": {
            "plan_count": 0,
            "active_watch_count": 0,
            "mean_reversion_watch_count": 0,
            "watching_count": 0,
            "invalidated_count": 0,
            "blocked_count": 0,
        },
        "groups": {},
        "top_watchlist": [],
        "notes": ["No tickers resolved for Lance swing cycle."],
        "disclaimer": DISCLAIMER,
    }


def _parse_tickers(tickers: list[str] | str | None) -> list[str]:
    if tickers is None:
        return []
    raw = tickers.split(",") if isinstance(tickers, str) else tickers
    seen = set()
    output = []
    for value in raw:
        normalized = str(value or "").strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def _session_id() -> str:
    day = utc_now_iso()[:10] or "unknown-date"
    return f"{day}-lance-swing"


def _join(values: Any) -> str | None:
    if isinstance(values, list):
        return "; ".join(str(value) for value in values if value is not None)
    if values is None:
        return None
    return str(values)


def _value(value: Any) -> str:
    return "unknown" if value is None else str(value)
