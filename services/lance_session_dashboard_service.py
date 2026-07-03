from __future__ import annotations

from pathlib import Path
from typing import Any

from services.lance_market_scan_service import DISCLAIMER


class LanceSessionDashboardService:
    """Compose Lance session review, carryover, and memory into one desk view."""

    def __init__(
        self,
        *,
        full_cycle_review_service: Any | None = None,
        carryover_service: Any | None = None,
        memory_service: Any | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        if full_cycle_review_service is None:
            from services.lance_full_cycle_review_service import LanceFullCycleReviewService

            full_cycle_review_service = LanceFullCycleReviewService(db_path=db_path)
        if carryover_service is None:
            from services.lance_carryover_plan_service import LanceCarryoverPlanService

            carryover_service = LanceCarryoverPlanService(db_path=db_path)
        if memory_service is None:
            from services.lance_memory_report_service import LanceMemoryReportService

            memory_service = LanceMemoryReportService(db_path=db_path)

        self.full_cycle_review_service = full_cycle_review_service
        self.carryover_service = carryover_service
        self.memory_service = memory_service

    def dashboard(
        self,
        *,
        intraday_session_id: str | None = None,
        swing_session_id: str | None = None,
        target_session_date: str | None = None,
        limit: int = 500,
        memory_limit: int = 100,
    ) -> dict[str, Any]:
        review = self.full_cycle_review_service.review(
            intraday_session_id=intraday_session_id,
            swing_session_id=swing_session_id,
            limit=limit,
        )
        session_ids = review.get("session_ids") if isinstance(review.get("session_ids"), dict) else {}
        intraday_id = session_ids.get("intraday")
        swing_id = session_ids.get("swing")
        intraday_carryover = _carryover_for(
            self.carryover_service,
            session_id=intraday_id,
            target_session_date=target_session_date,
            limit=limit,
            lane="intraday",
        )
        swing_carryover = _carryover_for(
            self.carryover_service,
            session_id=swing_id,
            target_session_date=target_session_date,
            limit=limit,
            lane="swing",
        )
        memory = self.memory_service.summarize(limit=memory_limit)
        carryover_rows = _carryover_rows(intraday_carryover, "intraday") + _carryover_rows(
            swing_carryover,
            "swing",
        )
        buckets = _buckets(review, carryover_rows)
        dashboard_read = _dashboard_read(buckets)
        return {
            "agent_name": "lance_full_cycle",
            "mode": "session_dashboard",
            "strategy": "Lance full-cycle session dashboard",
            "status": _status(review, intraday_carryover, swing_carryover),
            "session_ids": {
                "intraday": intraday_id,
                "swing": swing_id,
            },
            "target_session_date": target_session_date,
            "summary": {
                "journal_queue_count": len(review.get("journal_queue") or []),
                "intraday_carryover_count": _int(intraday_carryover.get("carryover_count")),
                "swing_carryover_count": _int(swing_carryover.get("carryover_count")),
                "memory_outcome_count": _int(memory.get("outcome_count")),
                "tomorrow_watch_count": len(_tomorrow_watchlist(buckets)),
            },
            "review": review,
            "intraday_carryover": intraday_carryover,
            "swing_carryover": swing_carryover,
            "memory": memory,
            "buckets": buckets,
            "dashboard_read": dashboard_read,
            "next_actions": [
                "Journal pending outcomes after manual chart review.",
                "Run a fresh Lance full-cycle scan before upgrading carryover names.",
                "Treat caveated context as alerts only until data quality is current and OK.",
            ],
            "handoff_prompt": (
                "Present this as Lance's workflow dashboard: review queue first, then "
                "carryover watches, then memory context. Do not infer outcomes or present "
                "carryover rows as active setups."
            ),
            "notes": [
                "Outcome counts are journaled labels, not predictions.",
                "Carryover rows require fresh confirmation before next-session use.",
            ],
            "disclaimer": DISCLAIMER,
        }

    def tomorrow_prep(
        self,
        *,
        intraday_session_id: str | None = None,
        swing_session_id: str | None = None,
        target_session_date: str | None = None,
        limit: int = 500,
        memory_limit: int = 100,
    ) -> dict[str, Any]:
        dashboard = self.dashboard(
            intraday_session_id=intraday_session_id,
            swing_session_id=swing_session_id,
            target_session_date=target_session_date,
            limit=limit,
            memory_limit=memory_limit,
        )
        return {
            "agent_name": "lance_full_cycle",
            "mode": "tomorrow_prep",
            "strategy": "Lance next-session preparation",
            "status": dashboard["status"],
            "session_ids": dashboard["session_ids"],
            "target_session_date": target_session_date,
            "fresh_scan_required": True,
            "watchlist": _tomorrow_watchlist(dashboard["buckets"]),
            "dashboard_summary": dashboard["summary"],
            "memory": dashboard["memory"],
            "what_lance_would_do_now": (
                "Prepare the watchlist and wait for tomorrow's fresh scan; carryover rows are alerts, "
                "not active setups."
            ),
            "confirmation_checklist": [
                "Run a fresh Lance full-cycle scan.",
                "Require OK confidence and current as-of timestamps.",
                "Require RVOL >= 3.0 before treating a ticker as in play.",
                "Use 2-minute bar structure before upgrading intraday ideas.",
                "Journal prior outcomes only after manual chart review.",
            ],
            "notes": [
                "Tomorrow prep is a carryover watchlist, not a signal.",
                "Caveated context remains blocked until data quality is current and OK.",
            ],
            "disclaimer": DISCLAIMER,
        }


def _carryover_for(
    service: Any,
    *,
    session_id: str | None,
    target_session_date: str | None,
    limit: int,
    lane: str,
) -> dict[str, Any]:
    if not session_id:
        return _empty_carryover(lane, target_session_date, "No session id available.")
    return service.build(
        session_id=session_id,
        target_session_date=target_session_date,
        limit=limit,
    )


def _empty_carryover(lane: str, target_session_date: str | None, note: str) -> dict[str, Any]:
    return {
        "agent_name": "lance_intraday",
        "strategy": f"Lance {lane} carryover plan",
        "source_session_id": None,
        "target_session_date": target_session_date,
        "status": "EMPTY",
        "carryover_count": 0,
        "fresh_scan_required": True,
        "groups": {},
        "notes": [note],
        "disclaimer": DISCLAIMER,
    }


def _carryover_rows(carryover: dict[str, Any], lane: str) -> list[dict[str, Any]]:
    output = []
    groups = carryover.get("groups") if isinstance(carryover.get("groups"), dict) else {}
    for bucket, rows in groups.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            output.append(_dashboard_row(row, lane=lane, bucket=str(bucket)))
    return output


def _dashboard_row(row: dict[str, Any], *, lane: str, bucket: str) -> dict[str, Any]:
    return {
        "ticker": _ticker(row),
        "lane": lane,
        "bucket": bucket,
        "latest_state": row.get("latest_state"),
        "playbook": row.get("playbook"),
        "gap_pct": row.get("gap_pct"),
        "rel_volume": row.get("rel_volume"),
        "confidence": row.get("confidence"),
        "gap_basis": row.get("gap_basis"),
        "as_of_et": row.get("as_of_et"),
        "sources": list(row.get("sources") or []),
        "review_focus": list(row.get("review_focus") or []),
        "confirmation_checklist": list(row.get("confirmation_checklist") or []),
        "journal_args": row.get("journal_args"),
    }


def _buckets(review: dict[str, Any], carryover_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    needs_manual_review = [
        _review_queue_row(row)
        for row in review.get("journal_queue") or []
        if isinstance(row, dict)
    ]
    relative_strength = [
        row for row in carryover_rows if row["bucket"] in {"strength_carryover", "swing_continuation_carryover"}
    ]
    swing_reclaim = [
        row for row in carryover_rows if row["bucket"] == "swing_mean_reversion_carryover"
    ]
    caveated = [row for row in carryover_rows if _is_caveated(row)]
    invalidated = [row for row in carryover_rows if _is_invalidated(row)]
    return {
        "needs_manual_review": needs_manual_review,
        "relative_strength_watch": _sort_rows(relative_strength),
        "swing_reclaim_watch": _sort_rows(swing_reclaim),
        "caveated_context": caveated,
        "invalidated": invalidated,
    }


def _dashboard_read(buckets: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    seen: set[str] = set()
    relative_rows = _take_unseen(buckets.get("relative_strength_watch") or [], seen)
    swing_rows = _take_unseen(buckets.get("swing_reclaim_watch") or [], seen)
    caveated_rows = _take_unseen(buckets.get("caveated_context") or [], seen)
    manual_rows = buckets.get("needs_manual_review") or []
    watch_tickers = _tickers_from_rows(relative_rows + swing_rows + caveated_rows)
    manual_tickers = _tickers_from_rows(manual_rows)
    return {
        "one_liner": (
            "Fresh scan required. "
            f"{_count_phrase(len(relative_rows), 'relative-strength watch', 'relative-strength watches')}, "
            f"{_count_phrase(len(swing_rows), 'swing-reclaim watch', 'swing-reclaim watches')}, "
            f"{_count_phrase(len(caveated_rows), 'caveated context name', 'caveated context names')}, "
            f"{_count_phrase(len(manual_rows), 'manual-review item', 'manual-review items')}."
        ),
        "fresh_scan_required": True,
        "sections": [
            {
                "name": "fresh_scan_required",
                "tickers": watch_tickers,
                "note": "Carryover rows are alerts only until a fresh Lance scan confirms current data.",
            },
            {
                "name": "relative_strength_watch",
                "tickers": _tickers_from_rows(relative_rows),
                "rows": relative_rows,
            },
            {
                "name": "swing_reclaim_watch",
                "tickers": _tickers_from_rows(swing_rows),
                "rows": swing_rows,
            },
            {
                "name": "caveated_context",
                "tickers": _tickers_from_rows(caveated_rows),
                "rows": caveated_rows,
            },
            {
                "name": "manual_review_queue",
                "count": len(manual_rows),
                "tickers": manual_tickers,
            },
        ],
        "data_caveats": _data_caveats(buckets.get("caveated_context") or []),
    }


def _take_unseen(rows: list[dict[str, Any]], seen: set[str]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        ticker = _ticker(row)
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        output.append(row)
    return output


def _tickers_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    tickers = []
    seen = set()
    for row in rows:
        ticker = _ticker(row)
        if ticker and ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    return tickers


def _data_caveats(rows: list[dict[str, Any]]) -> list[str]:
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for row in rows:
        ticker = _ticker(row)
        confidence = row.get("confidence")
        gap_basis = row.get("gap_basis")
        as_of = row.get("as_of_et")
        if not ticker or confidence in {None, "OK"}:
            continue
        key = (str(confidence), str(gap_basis or "unknown"), str(as_of or "unknown"))
        grouped.setdefault(key, []).append(ticker)

    caveats = []
    for (confidence, gap_basis, as_of), tickers in grouped.items():
        unique = sorted(set(tickers))
        caveats.append(
            f"{', '.join(unique)}: confidence={confidence} / gap_basis={gap_basis} as of {as_of}."
        )
    return caveats


def _count_phrase(count: int, singular: str, plural: str) -> str:
    word = singular if count == 1 else plural
    return f"{count} {word}"


def _review_queue_row(row: dict[str, Any]) -> dict[str, Any]:
    args = row.get("journal_args") if isinstance(row.get("journal_args"), dict) else {}
    return {
        "lane": row.get("lane"),
        "ticker": _ticker(row),
        "latest_state": row.get("latest_state"),
        "playbook": row.get("playbook"),
        "suggested_outcome": row.get("suggested_outcome", "unknown"),
        "journal_args": dict(args),
    }


def _tomorrow_watchlist(buckets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    output = []
    seen = set()
    for bucket in ["relative_strength_watch", "swing_reclaim_watch", "caveated_context"]:
        for row in buckets.get(bucket) or []:
            ticker = _ticker(row)
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            output.append({
                "ticker": ticker,
                "lanes": [row.get("lane")],
                "bucket": bucket,
                "playbook": row.get("playbook"),
                "latest_state": row.get("latest_state"),
                "confidence": row.get("confidence"),
                "gap_basis": row.get("gap_basis"),
                "as_of_et": row.get("as_of_et"),
            })
    return output


def _is_caveated(row: dict[str, Any]) -> bool:
    confidence = row.get("confidence")
    return confidence not in {None, "OK"}


def _is_invalidated(row: dict[str, Any]) -> bool:
    return str(row.get("latest_state") or "") in {
        "blocked_data_quality",
        "invalidated",
        "not_in_play",
    }


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: str(row.get("ticker") or ""))


def _status(*parts: dict[str, Any]) -> str:
    statuses = {str(part.get("status") or "UNKNOWN") for part in parts}
    if statuses == {"OK"}:
        return "OK"
    if "ERROR" in statuses:
        return "ERROR"
    if "OK" in statuses:
        return "PARTIAL"
    if statuses == {"EMPTY"}:
        return "EMPTY"
    return "UNKNOWN"


def _ticker(row: dict[str, Any]) -> str | None:
    ticker = str(row.get("ticker") or "").strip().upper()
    return ticker or None


def _int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0
