from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db import get_lance_outcomes, get_latest_lance_session_id
from services.lance_market_scan_service import DISCLAIMER
from services.lance_session_timeline_service import LanceSessionTimelineService


class LanceSessionReviewService:
    """Build a safe human review queue from Lance timeline events."""

    def __init__(self, *, db_path: str | Path | None = None) -> None:
        self.db_path = db_path
        self.timeline_service = LanceSessionTimelineService(db_path=db_path)

    def review(
        self,
        *,
        session_id: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        resolved_session_id = session_id or get_latest_lance_session_id(
            self.db_path,
            exclude_session_id_suffix="-lance-swing",
        )
        if resolved_session_id is None:
            return _empty(None, "No persisted Lance session found.")

        timeline = self.timeline_service.timeline(session_id=resolved_session_id, limit=limit)
        if timeline["status"] == "EMPTY":
            return _empty(resolved_session_id, "No Lance timeline events found for review.")

        pending_reviews = []
        reviewed = []
        for row in timeline["tickers"]:
            outcomes = get_lance_outcomes(
                self.db_path,
                session_id=resolved_session_id,
                ticker=row["ticker"],
                limit=5,
            )
            if outcomes:
                reviewed.append({
                    "ticker": row["ticker"],
                    "latest_state": row["latest_state"],
                    "outcomes": outcomes,
                })
                continue
            pending_reviews.append(_pending_review(resolved_session_id, row))

        return {
            "agent_name": "lance_intraday",
            "strategy": "Lance session review queue",
            "session_id": resolved_session_id,
            "status": "OK",
            "ticker_count": len(timeline["tickers"]),
            "pending_count": len(pending_reviews),
            "reviewed_count": len(reviewed),
            "pending_reviews": pending_reviews,
            "reviewed": reviewed,
            "notes": [
                "Outcomes are not inferred. Review the chart/session manually before journaling."
            ],
            "disclaimer": DISCLAIMER,
        }


def _empty(session_id: str | None, note: str) -> dict[str, Any]:
    return {
        "agent_name": "lance_intraday",
        "strategy": "Lance session review queue",
        "session_id": session_id,
        "status": "EMPTY",
        "ticker_count": 0,
        "pending_count": 0,
        "reviewed_count": 0,
        "pending_reviews": [],
        "reviewed": [],
        "notes": [note],
        "disclaimer": DISCLAIMER,
    }


def _pending_review(session_id: str, row: dict[str, Any]) -> dict[str, Any]:
    latest_event = row["events"][-1]
    latest_payload = latest_event.get("payload") or {}
    data_quality = latest_event.get("data_quality") or {}
    playbook = _playbook_from_events(row["events"])
    return {
        "ticker": row["ticker"],
        "first_state": row["first_state"],
        "latest_state": row["latest_state"],
        "score_delta": row["score_delta"],
        "gap_pct_delta": row["gap_pct_delta"],
        "rel_volume_delta": row["rel_volume_delta"],
        "latest_data_quality": data_quality,
        "latest_event_type": latest_event.get("event_type"),
        "review_focus": _review_focus(row, latest_payload),
        "suggested_outcome": "unknown",
        "journal_args": {
            "session_id": session_id,
            "ticker": row["ticker"],
            "playbook": playbook,
            "outcome": "unknown",
        },
    }


def _playbook_from_events(events: list[dict[str, Any]]) -> str:
    for event in reversed(events):
        payload = event.get("payload") or {}
        playbook = payload.get("playbook")
        if playbook:
            return str(playbook)
    return "watchlist_context"


def _review_focus(row: dict[str, Any], latest_payload: dict[str, Any]) -> list[str]:
    focus = []
    change_flags = latest_payload.get("change_flags")
    if isinstance(change_flags, list):
        focus.extend(str(flag) for flag in change_flags)
    if row["first_state"] != row["latest_state"]:
        focus.append("state_changed")
    if row["rel_volume_delta"] is not None and row["rel_volume_delta"] >= 1:
        focus.append("rvol_expanded")
    if row["gap_pct_delta"] is not None and abs(row["gap_pct_delta"]) >= 2:
        focus.append("move_expanded")
    return _dedupe(focus) or ["manual_chart_review_required"]


def _dedupe(values: list[str]) -> list[str]:
    output = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
