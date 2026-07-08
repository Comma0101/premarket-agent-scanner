from __future__ import annotations

from pathlib import Path
from typing import Any

from app.db import get_lance_outcomes, insert_lance_outcome
from services.lance_market_scan_service import DISCLAIMER


VALID_OUTCOMES = {"worked", "failed", "chop", "reversed", "unknown"}


class LanceOutcomeJournalService:
    def __init__(self, *, db_path: str | Path | None = None) -> None:
        self.db_path = db_path

    def record(
        self,
        *,
        session_id: str,
        ticker: str,
        playbook: str,
        outcome: str,
        notes: str | None = None,
        plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_outcome = outcome.strip().lower()
        if normalized_outcome not in VALID_OUTCOMES:
            valid = ", ".join(sorted(VALID_OUTCOMES))
            return {"error": f"outcome must be one of: {valid}."}
        normalized_ticker = ticker.strip().upper()
        if not session_id or not normalized_ticker or not playbook:
            return {"error": "session_id, ticker, and playbook are required."}

        insert_lance_outcome(
            self.db_path,
            session_id=session_id,
            ticker=normalized_ticker,
            playbook=playbook,
            outcome=normalized_outcome,
            notes=notes,
            plan=plan,
        )
        recent = get_lance_outcomes(self.db_path, ticker=normalized_ticker, limit=5)
        return {
            "agent_name": "lance_intraday",
            "status": "OK",
            "recorded": {
                "session_id": session_id,
                "ticker": normalized_ticker,
                "playbook": playbook,
                "outcome": normalized_outcome,
                "notes": notes,
                "plan_summary": _plan_summary(plan),
            },
            "recent_outcomes": recent,
            "disclaimer": DISCLAIMER,
        }


def _plan_summary(plan: dict[str, Any] | None) -> dict[str, Any]:
    if not plan:
        return {}
    return {
        "action_mode": plan.get("action_mode"),
        "alignment": plan.get("alignment"),
        "primary_timeframe": plan.get("primary_timeframe"),
        "thesis": plan.get("thesis"),
    }
