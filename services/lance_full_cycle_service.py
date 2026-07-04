from __future__ import annotations

from pathlib import Path
from typing import Any

from services.lance_market_scan_service import DISCLAIMER
from services.session_time_service import market_session_context_for


class LanceFullCycleService:
    """Compose Lance intraday and swing cycles into one desk workflow."""

    def __init__(
        self,
        *,
        desk_cycle_service: Any | None = None,
        swing_cycle_service: Any | None = None,
        swing_carryover_service: Any | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        if desk_cycle_service is None:
            from services.lance_desk_cycle_service import LanceDeskCycleService

            desk_cycle_service = LanceDeskCycleService(db_path=db_path)
        if swing_cycle_service is None:
            from services.lance_swing_cycle_service import LanceSwingCycleService

            swing_cycle_service = LanceSwingCycleService(db_path=db_path)
        if swing_carryover_service is None:
            from services.lance_carryover_plan_service import LanceCarryoverPlanService

            swing_carryover_service = LanceCarryoverPlanService(db_path=db_path)

        self.desk_cycle_service = desk_cycle_service
        self.swing_cycle_service = swing_cycle_service
        self.swing_carryover_service = swing_carryover_service

    def run(
        self,
        *,
        tickers: list[str] | str | None = None,
        universe: str | list[str] | None = None,
        watchlist: str | list[str] | None = None,
        all_universes: bool = False,
        min_gap_abs: float = 3.0,
        max_candidates: int = 20,
        persist: bool = True,
        session_id: str | None = None,
        swing_session_id: str | None = None,
        max_workers: int = 1,
        include_caveated_context: bool | None = None,
        lookback_days: int = 60,
        update_limit: int = 50,
        review_limit: int = 500,
        target_session_date: str | None = None,
        summary_limit: int = 5,
    ) -> dict[str, Any]:
        if not any([tickers, universe, watchlist, all_universes]):
            all_universes = True
        resolved_include_caveated_context = _include_caveated_context_default(
            include_caveated_context=include_caveated_context,
            tickers=tickers,
            universe=universe,
            watchlist=watchlist,
            all_universes=all_universes,
        )

        intraday = self.desk_cycle_service.run(
            tickers=tickers,
            universe=universe,
            watchlist=watchlist,
            all_universes=all_universes,
            min_gap_abs=min_gap_abs,
            max_candidates=max_candidates,
            persist=persist,
            session_id=session_id,
            max_workers=max_workers,
            include_caveated_context=resolved_include_caveated_context,
            update_limit=update_limit,
            review_limit=review_limit,
            target_session_date=target_session_date,
            summary_limit=summary_limit,
        )
        swing_scope = _swing_scope(
            tickers=tickers,
            universe=universe,
            watchlist=watchlist,
            all_universes=all_universes,
            intraday=intraday,
        )
        if swing_scope["skip_swing"]:
            swing = _empty_swing_cycle(
                session_id=swing_session_id,
                selection=str(swing_scope["selection"]),
                note=str(swing_scope["note"]),
            )
        else:
            swing = self.swing_cycle_service.run(
                tickers=swing_scope["tickers"],
                universe=swing_scope["universe"],
                watchlist=swing_scope["watchlist"],
                all_universes=bool(swing_scope["all_universes"]),
                lookback_days=lookback_days,
                persist=persist,
                session_id=swing_session_id,
                summary_limit=summary_limit,
            )
        swing_carryover = self._build_swing_carryover(
            session_id=str(swing.get("session_id") or swing_session_id or ""),
            target_session_date=target_session_date,
            limit=review_limit,
        )
        combined = _combined_watchlist(
            intraday.get("top_watchlist") or [],
            swing.get("top_watchlist") or [],
            summary_limit=summary_limit,
        )
        desk_read = _desk_read(combined, swing_carryover.get("groups") or {})
        session_context = market_session_context_for()

        return {
            "agent_name": "lance_full_cycle",
            "mode": "full_cycle",
            "strategy": "Lance full intraday-plus-swing desk cycle",
            "status": _status(intraday, swing),
            "session_banner": _session_banner_from_context(session_context),
            "session_context": session_context,
            "session_ids": {
                "intraday": intraday.get("session_id"),
                "swing": swing.get("session_id"),
            },
            "session_workflow": _session_workflow(
                persisted=persist,
                full_universe=all_universes,
                include_caveated_context=resolved_include_caveated_context,
                intraday_session_id=intraday.get("session_id"),
                swing_session_id=swing.get("session_id"),
                triage=swing_scope["workflow"],
            ),
            "steps": [
                "run_lance_desk_cycle",
                "run_lance_swing_cycle",
                "build_lance_swing_carryover_plan",
                "combine_lance_watchlists",
            ],
            "summary": _summary(intraday, swing, swing_carryover, combined),
            "selection_audit": _selection_audit(
                tickers=tickers,
                combined_rows=combined,
            ),
            "desk_read": desk_read,
            "market_context": intraday.get("market_context") or {},
            "top_intraday_watchlist": _compact_intraday_rows(
                list(intraday.get("top_watchlist") or []),
                summary_limit=summary_limit,
            ),
            "top_swing_watchlist": _compact_swing_rows(
                list(swing.get("top_watchlist") or []),
                summary_limit=summary_limit,
            ),
            "combined_watchlist": combined,
            "top_updates": list(intraday.get("top_updates") or [])[: max(0, int(summary_limit))],
            "pending_reviews": list(intraday.get("pending_reviews") or [])[
                : max(0, int(summary_limit))
            ],
            "carryover_groups": intraday.get("carryover_groups") or {},
            "swing_groups": swing.get("groups") or {},
            "swing_carryover_summary": _carryover_summary(swing_carryover),
            "swing_carryover_groups": swing_carryover.get("groups") or {},
            "handoff_prompt": (
                "Present Lance as one co-pilot with two lanes: intraday execution context "
                "and daily/swing context. Separate what is in play now from what is only a "
                "swing watch, name tool-provided invalidation/waiting conditions, and never "
                "turn references into orders, advice, or position sizing."
            ),
            "disclaimer": intraday.get("disclaimer") or swing.get("disclaimer") or DISCLAIMER,
        }

    def _build_swing_carryover(
        self,
        *,
        session_id: str,
        target_session_date: str | None,
        limit: int,
    ) -> dict[str, Any]:
        if not session_id:
            return _empty_swing_carryover(target_session_date)
        try:
            return self.swing_carryover_service.build(
                session_id=session_id,
                target_session_date=target_session_date,
                limit=limit,
            )
        except Exception as exc:
            return {
                "agent_name": "lance_intraday",
                "strategy": "Lance swing carryover plan",
                "source_session_id": session_id,
                "target_session_date": target_session_date,
                "status": "ERROR",
                "carryover_count": 0,
                "fresh_scan_required": True,
                "groups": {},
                "notes": [f"Lance swing carryover failed: {exc}"],
                "disclaimer": DISCLAIMER,
            }


def _status(intraday: dict[str, Any], swing: dict[str, Any]) -> str:
    statuses = {str(intraday.get("status") or "UNKNOWN"), str(swing.get("status") or "UNKNOWN")}
    if statuses == {"OK"}:
        return "OK"
    if "OK" in statuses:
        return "PARTIAL"
    if "ERROR" in statuses:
        return "ERROR"
    if "EMPTY" in statuses:
        return "EMPTY"
    return "UNKNOWN"


def _session_workflow(
    *,
    persisted: bool,
    full_universe: bool,
    include_caveated_context: bool,
    intraday_session_id: Any,
    swing_session_id: Any,
    triage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    intraday_id = str(intraday_session_id) if intraday_session_id else None
    swing_id = str(swing_session_id) if swing_session_id else None
    review_command = ".venv/bin/python -m cli.lance_full_cycle_eod review"
    if intraday_id:
        review_command = f"{review_command} --intraday-session-id {intraday_id}"
    if swing_id:
        review_command = f"{review_command} --swing-session-id {swing_id}"
    workflow = {
        "persisted": bool(persisted),
        "full_universe": bool(full_universe),
        "include_caveated_context": bool(include_caveated_context),
        "intraday_session_id": intraday_id,
        "swing_session_id": swing_id,
        "review_tool": "review_lance_full_cycle",
        "journal_tool": "journal_lance_full_cycle_outcome",
        "review_command": review_command,
        "journal_note": (
            "Journal observed outcomes only after manual chart review; use unknown when not reviewed."
        ),
    }
    if triage:
        workflow.update(triage)
    return workflow


def _include_caveated_context_default(
    *,
    include_caveated_context: bool | None,
    tickers: list[str] | str | None,
    universe: str | list[str] | None,
    watchlist: str | list[str] | None,
    all_universes: bool,
) -> bool:
    if include_caveated_context is not None:
        return bool(include_caveated_context)
    return bool(all_universes and not any([tickers, universe, watchlist]))


def _swing_scope(
    *,
    tickers: list[str] | str | None,
    universe: str | list[str] | None,
    watchlist: str | list[str] | None,
    all_universes: bool,
    intraday: dict[str, Any],
) -> dict[str, Any]:
    if not all_universes or any([tickers, universe, watchlist]):
        return {
            "tickers": tickers,
            "universe": universe,
            "watchlist": watchlist,
            "all_universes": all_universes,
            "skip_swing": False,
            "selection": "requested_selection",
            "note": "",
            "workflow": None,
        }

    triage_tickers = _tickers_from_rows(intraday.get("top_watchlist") or [])
    workflow = {
        "triage_mode": "full_universe_intraday_first",
        "swing_scope": "intraday_triage",
        "swing_scope_count": len(triage_tickers),
        "triage_note": "Swing scope came from the intraday triage shortlist.",
    }
    if not triage_tickers:
        workflow["triage_note"] = (
            "No intraday triage tickers passed the broad scan; swing deep analysis was skipped."
        )
        return {
            "tickers": [],
            "universe": None,
            "watchlist": None,
            "all_universes": False,
            "skip_swing": True,
            "selection": "intraday_triage",
            "note": "No intraday triage tickers available for swing deep analysis.",
            "workflow": workflow,
        }
    return {
        "tickers": triage_tickers,
        "universe": None,
        "watchlist": None,
        "all_universes": False,
        "skip_swing": False,
        "selection": "intraday_triage",
        "note": "",
        "workflow": workflow,
    }


def _tickers_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    tickers = []
    seen = set()
    for row in rows:
        ticker = _ticker(row)
        if ticker is not None and ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    return tickers


def _empty_swing_cycle(
    *,
    session_id: str | None,
    selection: str,
    note: str,
) -> dict[str, Any]:
    return {
        "agent_name": "lance_swing",
        "mode": "swing_cycle",
        "strategy": "Lance swing desk cycle",
        "session_id": session_id,
        "status": "EMPTY",
        "selection": selection,
        "selection_count": 0,
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
        "notes": [note],
        "disclaimer": DISCLAIMER,
    }


def _summary(
    intraday: dict[str, Any],
    swing: dict[str, Any],
    swing_carryover: dict[str, Any],
    combined: list[dict[str, Any]],
) -> dict[str, int]:
    scan_summary = intraday.get("scan_summary") or {}
    updates_summary = intraday.get("updates_summary") or {}
    review_summary = intraday.get("review_summary") or {}
    swing_summary = swing.get("summary") or {}
    return {
        "intraday_candidate_count": _int(scan_summary.get("candidate_count")),
        "intraday_update_count": _int(updates_summary.get("updated_count")),
        "intraday_pending_review_count": _int(review_summary.get("pending_count")),
        "swing_plan_count": _int(swing_summary.get("plan_count")),
        "swing_active_watch_count": _int(swing_summary.get("active_watch_count")),
        "swing_mean_reversion_watch_count": _int(
            swing_summary.get("mean_reversion_watch_count")
        ),
        "swing_carryover_count": _int(swing_carryover.get("carryover_count")),
        "combined_ticker_count": len(combined),
    }


def _session_banner_from_context(context: dict[str, Any]) -> str:
    mode = str(context.get("session_mode") or "OFF_SESSION")
    as_of = context.get("as_of_et")
    reason = context.get("market_closed_reason")
    if mode == "MARKET_CLOSED":
        suffix = f"US equity market closed: {reason}." if reason else "US equity market closed."
    elif mode == "PRE_MARKET":
        suffix = "Live premarket quotes are eligible for premarket-gap grading."
    elif mode == "MARKET_OPEN":
        suffix = "Regular session; effective price is a regular-session quote."
    elif mode == "POST_MARKET":
        suffix = "last_trade means prior/last-session move, not live premarket."
    else:
        suffix = "Outside US equity trading hours; effective price is not live."
    return f"{mode}, {as_of}. {suffix}" if as_of else f"{mode}. {suffix}"


def _selection_audit(
    *,
    tickers: list[str] | str | None,
    combined_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    requested = _requested_tickers(tickers)
    returned = _tickers_from_rows(combined_rows)
    returned_set = set(returned)
    omitted = [
        {
            "ticker": ticker,
            "reason": (
                "Requested ticker did not appear in Lance's summarized combined watchlist; "
                "it may have been filtered out, ranked below the summary limit, or blocked "
                "before plan construction."
            ),
        }
        for ticker in requested
        if ticker not in returned_set
    ]
    return {
        "requested_tickers": requested,
        "returned_tickers": returned,
        "omitted_tickers": omitted,
    }


def _requested_tickers(value: list[str] | str | None) -> list[str]:
    if value is None:
        return []
    raw = value if isinstance(value, list) else str(value).split(",")
    output = []
    seen = set()
    for item in raw:
        ticker = str(item or "").strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            output.append(ticker)
    return output


def _carryover_summary(carryover: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": carryover.get("status"),
        "carryover_count": carryover.get("carryover_count", 0),
        "fresh_scan_required": carryover.get("fresh_scan_required", True),
    }


def _empty_swing_carryover(target_session_date: str | None) -> dict[str, Any]:
    return {
        "agent_name": "lance_intraday",
        "strategy": "Lance swing carryover plan",
        "source_session_id": None,
        "target_session_date": target_session_date,
        "status": "EMPTY",
        "carryover_count": 0,
        "fresh_scan_required": True,
        "groups": {},
        "notes": ["No swing session id available for carryover."],
        "disclaimer": DISCLAIMER,
    }


def _combined_watchlist(
    intraday_rows: list[dict[str, Any]],
    swing_rows: list[dict[str, Any]],
    *,
    summary_limit: int,
) -> list[dict[str, Any]]:
    by_ticker: dict[str, dict[str, Any]] = {}
    for row in intraday_rows:
        ticker = _ticker(row)
        if ticker is None:
            continue
        combined = by_ticker.setdefault(ticker, _base_row(ticker))
        combined["lanes"].append("intraday")
        combined["intraday_state"] = row.get("state") or row.get("current_state")
        combined["intraday_playbook"] = row.get("playbook")
        combined["intraday_score"] = row.get("score")
        combined["data_quality"] = _data_quality(row)

    for row in swing_rows:
        ticker = _ticker(row)
        if ticker is None:
            continue
        combined = by_ticker.setdefault(ticker, _base_row(ticker))
        combined["lanes"].append("swing")
        combined["swing_state"] = row.get("state")
        combined["swing_playbook"] = row.get("playbook")
        combined["swing_score"] = row.get("score")
        if not combined.get("data_quality"):
            combined["data_quality"] = _data_quality(row)

    rows = [_dedupe_lanes(row) for row in by_ticker.values()]
    rows.sort(
        key=lambda row: (
            len(row["lanes"]),
            _score(row.get("intraday_score")),
            _score(row.get("swing_score")),
            row["ticker"],
        ),
        reverse=True,
    )
    return rows[: max(0, int(summary_limit))]


def _desk_read(
    combined_rows: list[dict[str, Any]],
    swing_carryover_groups: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    intraday_focus = []
    swing_watch = []
    blocked_data_quality = []

    for row in combined_rows:
        compact = _desk_row(row)
        if _is_blocked_or_caveated(row):
            blocked_data_quality.append(compact)
            continue
        if "intraday" in row.get("lanes", []) and _active_intraday_state(row):
            intraday_focus.append(compact)
            continue
        if "swing" in row.get("lanes", []):
            swing_watch.append(compact)

    swing_carryover = _desk_carryover_rows(swing_carryover_groups)
    return {
        "one_liner": (
            f"{len(intraday_focus)} intraday focus, {len(swing_watch)} swing watch, "
            f"{len(blocked_data_quality)} blocked/data-caveat, "
            f"{len(swing_carryover)} swing carryover."
        ),
        "intraday_focus": intraday_focus,
        "swing_watch": swing_watch,
        "blocked_data_quality": blocked_data_quality,
        "swing_carryover": swing_carryover,
        "workflow_notes": [
            "Use intraday focus rows for live desk monitoring only when data quality stays OK.",
            "Swing watches still require their waiting_for conditions before upgrading.",
            "Carryover rows require a fresh scan before next-session decisions.",
        ],
    }


def _desk_row(row: dict[str, Any]) -> dict[str, Any]:
    quality = row.get("data_quality") if isinstance(row.get("data_quality"), dict) else {}
    return {
        "ticker": row.get("ticker"),
        "intraday_state": row.get("intraday_state"),
        "swing_state": row.get("swing_state"),
        "confidence": quality.get("confidence"),
        "gap_basis": quality.get("gap_basis"),
        "as_of_et": quality.get("as_of_et") or quality.get("as_of"),
    }


def _is_blocked_or_caveated(row: dict[str, Any]) -> bool:
    quality = row.get("data_quality") if isinstance(row.get("data_quality"), dict) else {}
    halt_status = quality.get("halt_status") if isinstance(quality.get("halt_status"), dict) else {}
    states = [str(row.get("intraday_state") or ""), str(row.get("swing_state") or "")]
    provider_failures = quality.get("provider_failures")
    return (
        quality.get("confidence") != "OK"
        or quality.get("data_status") in {"stale", "provider_failure", "no_providers"}
        or bool(provider_failures)
        or halt_status.get("status") == "HALTED"
        or any("blocked" in state for state in states)
    )


def _active_intraday_state(row: dict[str, Any]) -> bool:
    return str(row.get("intraday_state") or "") in {
        "triggered_reference",
        "setup_forming",
        "waiting_for_turn",
        "watching",
    }


def _desk_carryover_rows(groups: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for bucket, bucket_rows in groups.items():
        for row in bucket_rows:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper()
            if not ticker:
                continue
            rows.append({
                "ticker": ticker,
                "bucket": bucket,
                "playbook": row.get("playbook"),
                "latest_state": row.get("latest_state"),
            })
    return rows


def _compact_intraday_rows(
    rows: list[dict[str, Any]],
    *,
    summary_limit: int,
) -> list[dict[str, Any]]:
    return [_compact_intraday_row(row) for row in rows[: max(0, int(summary_limit))]]


def _compact_intraday_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "state": row.get("state") or row.get("action_mode") or row.get("current_state"),
        "score": row.get("score") if row.get("score") is not None else row.get("rank_score"),
        "playbook": row.get("playbook"),
        "thesis": row.get("thesis"),
        "data_quality": _data_quality(row),
        "waiting_for": list(row.get("waiting_for") or []),
        "invalidates_if": list(row.get("invalidates_if") or []),
        "conflict_flags": list(row.get("conflict_flags") or []),
    }


def _compact_swing_rows(
    rows: list[dict[str, Any]],
    *,
    summary_limit: int,
) -> list[dict[str, Any]]:
    output = []
    for row in rows[: max(0, int(summary_limit))]:
        daily_context = row.get("daily_context") if isinstance(row.get("daily_context"), dict) else {}
        relative_strength = (
            row.get("relative_strength") if isinstance(row.get("relative_strength"), dict) else {}
        )
        output.append({
            "ticker": row.get("ticker"),
            "state": row.get("state"),
            "grade": row.get("lance_quality_grade"),
            "playbook": row.get("playbook"),
            "score": row.get("score"),
            "state_reason": row.get("state_reason"),
            "data_quality": _data_quality(row),
            "daily_context": {
                "trend": daily_context.get("trend"),
                "structure": daily_context.get("structure"),
                "prior_day_levels": daily_context.get("prior_day_levels"),
            },
            "relative_strength": {
                "classification": relative_strength.get("classification"),
                "vs_QQQ": relative_strength.get("vs_QQQ"),
                "vs_SPY": relative_strength.get("vs_SPY"),
            },
            "waiting_for": list(row.get("waiting_for") or []),
            "invalidates_if": list(row.get("invalidates_if") or []),
        })
    return output


def _base_row(ticker: str) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "lanes": [],
        "intraday_state": None,
        "swing_state": None,
        "intraday_playbook": None,
        "swing_playbook": None,
        "intraday_score": None,
        "swing_score": None,
        "data_quality": {},
    }


def _dedupe_lanes(row: dict[str, Any]) -> dict[str, Any]:
    lanes = []
    for lane in row.get("lanes") or []:
        if lane not in lanes:
            lanes.append(lane)
    row["lanes"] = lanes
    return row


def _ticker(row: dict[str, Any]) -> str | None:
    ticker = str(row.get("ticker") or "").strip().upper()
    return ticker or None


def _data_quality(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("data_quality")
    if isinstance(value, dict):
        return value
    plan = row.get("plan")
    if isinstance(plan, dict) and isinstance(plan.get("data_quality"), dict):
        return plan["data_quality"]
    return {}


def _score(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0
