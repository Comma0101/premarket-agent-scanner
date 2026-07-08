from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.db import get_lance_outcomes
from services.lance_market_scan_service import DISCLAIMER


OUTCOMES = ["worked", "failed", "chop", "reversed", "unknown"]


class LanceMemoryReportService:
    """Summarize journaled Lance outcomes without inferring performance."""

    def __init__(self, *, db_path: str | Path | None = None) -> None:
        self.db_path = db_path

    def summarize(
        self,
        *,
        session_id: str | None = None,
        ticker: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        rows = get_lance_outcomes(
            self.db_path,
            session_id=session_id,
            ticker=ticker,
            limit=limit,
        )
        status = "OK" if rows else "EMPTY"
        return {
            "agent_name": "lance_intraday",
            "strategy": "Lance market memory report",
            "status": status,
            "outcome_count": len(rows),
            "filters": {
                "session_id": session_id,
                "ticker": ticker.upper() if ticker else None,
                "limit": limit,
            },
            "by_playbook": _group(rows, "playbook", "playbook"),
            "by_ticker": _group(rows, "ticker", "ticker"),
            "by_action_mode": _group_plan_field(rows, "action_mode", "action_mode"),
            "by_alignment": _group_plan_field(rows, "alignment", "alignment"),
            "by_primary_timeframe": _group_plan_field(
                rows,
                "primary_timeframe",
                "primary_timeframe",
            ),
            "recent_outcomes": rows,
            "notes": [
                "Outcome counts are journaled labels, not performance, P&L, or trade advice."
            ],
            "disclaimer": DISCLAIMER,
        }


def _group(rows: list[dict[str, Any]], field: str, label: str) -> list[dict[str, Any]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = str(row.get(field) or "unknown")
        outcome = str(row.get("outcome") or "unknown")
        counters[key][outcome] += 1

    output = []
    for key, counter in counters.items():
        total = sum(counter.values())
        outcomes = {outcome: int(counter.get(outcome, 0)) for outcome in OUTCOMES}
        output.append({
            label: key,
            "total": total,
            "outcomes": outcomes,
            "worked_rate": _worked_rate(outcomes),
        })
    output.sort(key=lambda row: (row["total"], str(row[label])), reverse=True)
    return output


def _group_plan_field(rows: list[dict[str, Any]], field: str, label: str) -> list[dict[str, Any]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        plan = row.get("plan") if isinstance(row.get("plan"), dict) else {}
        key = plan.get(field)
        if not key:
            continue
        outcome = str(row.get("outcome") or "unknown")
        counters[str(key)][outcome] += 1

    output = []
    for key, counter in counters.items():
        total = sum(counter.values())
        outcomes = {outcome: int(counter.get(outcome, 0)) for outcome in OUTCOMES}
        output.append({
            label: key,
            "total": total,
            "outcomes": outcomes,
            "worked_rate": _worked_rate(outcomes),
        })
    output.sort(key=lambda row: (row["total"], str(row[label])), reverse=True)
    return output


def _worked_rate(outcomes: dict[str, int]) -> float | None:
    decided = outcomes["worked"] + outcomes["failed"] + outcomes["chop"] + outcomes["reversed"]
    if decided == 0:
        return None
    return round(outcomes["worked"] / decided, 2)
