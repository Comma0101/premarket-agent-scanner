from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db import get_latest_lance_session_id
from services.lance_market_scan_service import DISCLAIMER


class LanceFullCycleReviewService:
    """Review and journal full-cycle Lance sessions across intraday and swing lanes."""

    def __init__(
        self,
        *,
        review_service: Any | None = None,
        journal_service: Any | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        if review_service is None:
            from services.lance_session_review_service import LanceSessionReviewService

            review_service = LanceSessionReviewService(db_path=db_path)
        if journal_service is None:
            from services.lance_outcome_journal_service import LanceOutcomeJournalService

            journal_service = LanceOutcomeJournalService(db_path=db_path)

        self.review_service = review_service
        self.journal_service = journal_service
        self.db_path = db_path

    def review(
        self,
        *,
        intraday_session_id: str | None = None,
        swing_session_id: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        intraday_id = intraday_session_id or get_latest_lance_session_id(
            self.db_path,
            exclude_session_id_suffix="-lance-swing",
        )
        swing_id = swing_session_id or get_latest_lance_session_id(
            self.db_path,
            session_id_suffix="-lance-swing",
        )

        intraday_review = (
            self.review_service.review(session_id=intraday_id, limit=limit)
            if intraday_id
            else _empty_review(None, "intraday")
        )
        swing_review = (
            self.review_service.review(session_id=swing_id, limit=limit)
            if swing_id
            else _empty_review(None, "swing")
        )
        journal_queue = _journal_queue("intraday", intraday_review) + _journal_queue(
            "swing",
            swing_review,
        )

        return {
            "agent_name": "lance_full_cycle",
            "mode": "full_cycle_review",
            "strategy": "Lance full-cycle EOD review",
            "status": _status(intraday_review, swing_review),
            "session_ids": {
                "intraday": intraday_id,
                "swing": swing_id,
            },
            "summary": {
                "intraday_pending_count": _int(intraday_review.get("pending_count")),
                "intraday_reviewed_count": _int(intraday_review.get("reviewed_count")),
                "swing_pending_count": _int(swing_review.get("pending_count")),
                "swing_reviewed_count": _int(swing_review.get("reviewed_count")),
                "journal_queue_count": len(journal_queue),
            },
            "intraday_review": _compact_review(intraday_review),
            "swing_review": _compact_review(swing_review),
            "journal_queue": journal_queue,
            "notes": [
                "Outcomes are not inferred. Journal only after manual chart review."
            ],
            "disclaimer": DISCLAIMER,
        }

    def record_outcome(
        self,
        *,
        lane: str,
        session_id: str | None = None,
        ticker: str,
        playbook: str,
        outcome: str,
        notes: str | None = None,
        plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_lane = lane.strip().lower()
        if normalized_lane not in {"intraday", "swing"}:
            return {"error": "lane must be intraday or swing."}
        resolved_session_id = session_id or _latest_session_for_lane(
            self.db_path,
            normalized_lane,
        )
        if resolved_session_id is None:
            return {"error": f"no {normalized_lane} Lance session found."}

        journal = self.journal_service.record(
            session_id=resolved_session_id,
            ticker=ticker,
            playbook=playbook,
            outcome=outcome,
            notes=notes,
            plan=plan,
        )
        return {
            "agent_name": "lance_full_cycle",
            "mode": "full_cycle_journal",
            "lane": normalized_lane,
            "session_id": resolved_session_id,
            "journal": journal,
            "disclaimer": journal.get("disclaimer") or DISCLAIMER,
        }


def _latest_session_for_lane(db_path: str | Path | None, lane: str) -> str | None:
    if lane == "swing":
        return get_latest_lance_session_id(db_path, session_id_suffix="-lance-swing")
    return get_latest_lance_session_id(
        db_path,
        exclude_session_id_suffix="-lance-swing",
    )


def _journal_queue(lane: str, review: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for row in review.get("pending_reviews") or []:
        args = row.get("journal_args") if isinstance(row.get("journal_args"), dict) else {}
        output.append({
            "lane": lane,
            "ticker": row.get("ticker"),
            "latest_state": row.get("latest_state"),
            "playbook": args.get("playbook"),
            "suggested_outcome": row.get("suggested_outcome", "unknown"),
            "journal_args": {
                "lane": lane,
                "session_id": args.get("session_id") or review.get("session_id"),
                "ticker": args.get("ticker") or row.get("ticker"),
                "playbook": args.get("playbook"),
                "outcome": args.get("outcome", "unknown"),
            },
        })
    return output


def _compact_review(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": review.get("status"),
        "session_id": review.get("session_id"),
        "pending_count": review.get("pending_count", 0),
        "reviewed_count": review.get("reviewed_count", 0),
        "pending_reviews": list(review.get("pending_reviews") or []),
        "reviewed": list(review.get("reviewed") or []),
    }


def _empty_review(session_id: str | None, lane: str) -> dict[str, Any]:
    return {
        "agent_name": "lance_intraday",
        "strategy": f"Lance {lane} session review queue",
        "session_id": session_id,
        "status": "EMPTY",
        "pending_count": 0,
        "reviewed_count": 0,
        "pending_reviews": [],
        "reviewed": [],
    }


def _status(intraday_review: dict[str, Any], swing_review: dict[str, Any]) -> str:
    statuses = {
        str(intraday_review.get("status") or "UNKNOWN"),
        str(swing_review.get("status") or "UNKNOWN"),
    }
    if statuses == {"OK"}:
        return "OK"
    if "OK" in statuses:
        return "PARTIAL"
    if "ERROR" in statuses:
        return "ERROR"
    if statuses == {"EMPTY"}:
        return "EMPTY"
    return "UNKNOWN"


def _int(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0
