from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from services.lance_market_scan_service import DISCLAIMER
from services.session_time_service import format_et, session_mode_for


class LiveMarketValidationService:
    """Validate that live data plumbing is ready before running a real session."""

    def __init__(
        self,
        *,
        snapshot_tool: Any | None = None,
        lance_cycle_tool: Any | None = None,
    ) -> None:
        if snapshot_tool is None or lance_cycle_tool is None:
            from agent_tools import tools

            snapshot_tool = snapshot_tool or tools.get_ticker_snapshot
            lance_cycle_tool = lance_cycle_tool or tools.run_lance_desk_cycle
        self.snapshot_tool = snapshot_tool
        self.lance_cycle_tool = lance_cycle_tool

    def run(
        self,
        *,
        tickers: list[str] | str,
        max_candidates: int = 5,
        persist: bool = False,
        summary_limit: int | None = None,
        review_limit: int = 10,
        max_workers: int = 1,
        now: str | datetime | None = None,
    ) -> dict[str, Any]:
        ticker_list = _parse_tickers(tickers)
        observed_now = _validation_now(now)
        if not ticker_list:
            return {
                "agent_name": "market_validation",
                "status": "blocked",
                "session_mode": session_mode_for(observed_now),
                "session_time_et": format_et(observed_now),
                "ticker_count": 0,
                "ready_count": 0,
                "blocked_count": 0,
                "snapshot_checks": [],
                "lance_cycle": {},
                "notes": ["No tickers supplied."],
                "disclaimer": DISCLAIMER,
            }

        checks = [_snapshot_check(self.snapshot_tool(ticker=ticker)) for ticker in ticker_list]
        ready_count = sum(1 for check in checks if check["readiness"] == "ready")
        blocked_count = sum(1 for check in checks if check["readiness"] == "blocked")
        mode = session_mode_for(observed_now)

        lance_cycle = self.lance_cycle_tool(
            tickers=ticker_list,
            max_candidates=max_candidates,
            persist=persist,
            summary_limit=summary_limit if summary_limit is not None else max_candidates,
            review_limit=review_limit,
            max_workers=max_workers,
        )

        status = _overall_status(
            session_mode=mode,
            ready_count=ready_count,
            blocked_count=blocked_count,
        )
        notes = []
        if mode != "MARKET_OPEN":
            notes.append("Market is not open; this validates plumbing, not live readiness.")

        return {
            "agent_name": "market_validation",
            "status": status,
            "session_mode": mode,
            "session_time_et": format_et(observed_now),
            "ticker_count": len(ticker_list),
            "ready_count": ready_count,
            "blocked_count": blocked_count,
            "snapshot_checks": checks,
            "lance_cycle": lance_cycle,
            "notes": notes,
            "disclaimer": DISCLAIMER,
        }


def _snapshot_check(snapshot: dict[str, Any]) -> dict[str, Any]:
    blockers = _blockers(snapshot)
    return {
        "ticker": snapshot.get("ticker"),
        "readiness": "blocked" if blockers else "ready",
        "previous_close": snapshot.get("previous_close"),
        "latest_price": snapshot.get("latest_price"),
        "premarket_price": snapshot.get("premarket_price"),
        "gap_pct": snapshot.get("gap_pct"),
        "gap_dollar": snapshot.get("gap_dollar"),
        "gap_basis": snapshot.get("gap_basis"),
        "confidence": snapshot.get("confidence"),
        "data_status": snapshot.get("data_status"),
        "provider_failures": dict(snapshot.get("provider_failures") or {}),
        "halt_status": snapshot.get("halt_status"),
        "sources": list(snapshot.get("sources") or []),
        "timestamp": snapshot.get("timestamp"),
        "as_of_et": format_et(snapshot.get("timestamp")),
        "blockers": blockers,
    }


def _blockers(snapshot: dict[str, Any]) -> list[str]:
    blockers = []
    if snapshot.get("previous_close") is None:
        blockers.append("missing previous_close")
    if snapshot.get("latest_price") is None and snapshot.get("premarket_price") is None:
        blockers.append("missing effective price")
    if snapshot.get("gap_basis") is None:
        blockers.append("missing gap_basis")
    data_status = snapshot.get("data_status")
    if data_status not in {"live"}:
        blockers.append(f"data_status={data_status or 'unknown'}")
    confidence = snapshot.get("confidence")
    if confidence != "OK":
        blockers.append(f"confidence={confidence or 'unknown'}")
    if snapshot.get("provider_failures"):
        blockers.append("provider_failures present")
    halt_status = snapshot.get("halt_status") or {}
    if isinstance(halt_status, dict) and halt_status.get("status") == "HALTED":
        blockers.append("halt_status=HALTED")
    return blockers


def _overall_status(*, session_mode: str, ready_count: int, blocked_count: int) -> str:
    if blocked_count:
        return "blocked"
    if session_mode != "MARKET_OPEN":
        return "watch_only"
    if ready_count:
        return "ready"
    return "blocked"


def _parse_tickers(tickers: list[str] | str) -> list[str]:
    if isinstance(tickers, str):
        raw = tickers.split(",")
    else:
        raw = tickers
    return [ticker.strip().upper() for ticker in raw if ticker and ticker.strip()]


def _validation_now(now: str | datetime | None) -> str | datetime:
    return now if now is not None else datetime.now(timezone.utc).replace(microsecond=0)
