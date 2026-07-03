from __future__ import annotations

from pathlib import Path
from typing import Any

from services.lance_market_scan_service import DISCLAIMER
from services.lance_session_review_service import LanceSessionReviewService


CONFIRMATION_CHECKLIST = [
    "Run a fresh Advanced Lance scan before the next session.",
    "Require OK confidence and current as-of timestamps.",
    "Require RVOL >= 3.0 before treating it as in play.",
    "Use build_lance_intraday_plan after 2-minute bars exist.",
    "Stand down if the state remains not_in_play.",
]


class LanceCarryoverPlanService:
    def __init__(self, *, db_path: str | Path | None = None) -> None:
        self.review_service = LanceSessionReviewService(db_path=db_path)

    def build(
        self,
        *,
        session_id: str | None = None,
        target_session_date: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        review = self.review_service.review(session_id=session_id, limit=limit)
        if review["status"] == "EMPTY":
            return {
                "agent_name": "lance_intraday",
                "strategy": "Lance carryover plan",
                "source_session_id": review.get("session_id"),
                "target_session_date": target_session_date,
                "status": "EMPTY",
                "carryover_count": 0,
                "fresh_scan_required": True,
                "groups": _empty_groups(),
                "excluded_reviewed": [],
                "notes": list(review.get("notes", [])),
                "disclaimer": DISCLAIMER,
            }

        groups = _empty_groups()
        for pending in review["pending_reviews"]:
            row = _carryover_row(pending)
            groups[_group_for(row)].append(row)

        for rows in groups.values():
            rows.sort(
                key=lambda row: (
                    abs(row["gap_pct"] or 0),
                    row["rel_volume"] or 0,
                    row["score_delta"] or 0,
                ),
                reverse=True,
            )

        return {
            "agent_name": "lance_intraday",
            "strategy": "Lance carryover plan",
            "source_session_id": review["session_id"],
            "target_session_date": target_session_date,
            "status": "OK",
            "carryover_count": sum(len(rows) for rows in groups.values()),
            "fresh_scan_required": True,
            "what_lance_would_do_now": (
                "Prepare alerts and wait; no active setup is carried without fresh volume and "
                "2-minute structure."
            ),
            "groups": groups,
            "excluded_reviewed": [
                {
                    "ticker": row["ticker"],
                    "latest_state": row["latest_state"],
                    "outcomes": row["outcomes"],
                }
                for row in review.get("reviewed", [])
            ],
            "notes": [
                "This is a carryover watch plan, not a trade signal.",
                "Outcomes are not inferred; journal reviewed names separately.",
            ],
            "disclaimer": DISCLAIMER,
        }


def _empty_groups() -> dict[str, list[dict[str, Any]]]:
    return {
        "swing_mean_reversion_carryover": [],
        "swing_continuation_carryover": [],
        "strength_carryover": [],
        "weakness_carryover": [],
        "context_only": [],
    }


def _carryover_row(pending: dict[str, Any]) -> dict[str, Any]:
    data_quality = pending.get("latest_data_quality") or {}
    journal_args = pending.get("journal_args") or {}
    playbook = str(journal_args.get("playbook") or "watchlist_context")
    row = {
        "ticker": pending["ticker"],
        "latest_state": pending.get("latest_state"),
        "latest_event_type": pending.get("latest_event_type"),
        "playbook": playbook,
        "gap_pct": data_quality.get("gap_pct"),
        "rel_volume": data_quality.get("rel_volume"),
        "confidence": data_quality.get("confidence"),
        "gap_basis": data_quality.get("gap_basis"),
        "as_of_et": data_quality.get("as_of_et"),
        "sources": list(data_quality.get("sources") or []),
        "score_delta": pending.get("score_delta"),
        "review_focus": list(pending.get("review_focus") or []),
        "journal_args": pending.get("journal_args"),
        "confirmation_checklist": _confirmation_checklist(playbook),
    }
    return row


def _group_for(row: dict[str, Any]) -> str:
    playbook = str(row.get("playbook") or "")
    if playbook == "swing_mean_reversion_reclaim":
        return "swing_mean_reversion_carryover"
    if playbook.startswith("swing_"):
        return "swing_continuation_carryover"
    gap_pct = row.get("gap_pct")
    if isinstance(gap_pct, int | float):
        if gap_pct >= 5:
            return "strength_carryover"
        if gap_pct <= -5:
            return "weakness_carryover"
    return "context_only"


def _confirmation_checklist(playbook: str) -> list[str]:
    checklist = list(CONFIRMATION_CHECKLIST)
    if playbook.startswith("swing_"):
        checklist.append("Require daily reclaim/hold before upgrading the swing idea.")
    return checklist
