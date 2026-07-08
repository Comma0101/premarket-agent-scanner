from __future__ import annotations

from typing import Any

from services.lance_command_center_service import LanceCommandCenterService
from services.sykes_live_plan_service import DISCLAIMER, SykesLivePlanService


class TradingDeskService:
    """One-run wrapper for the current desk agents."""

    def __init__(
        self,
        *,
        lance_service: Any | None = None,
        sykes_service: Any | None = None,
    ) -> None:
        self.lance_service = lance_service or LanceCommandCenterService()
        self.sykes_service = sykes_service or SykesLivePlanService()

    def run(
        self,
        *,
        tickers: list[str] | str | None = None,
        universe: str | list[str] | None = None,
        watchlist: str | list[str] | None = None,
        market: str | None = "us-listed",
        market_limit: int | None = None,
        max_workers: int = 6,
        summary_limit: int = 8,
        persist: bool = False,
    ) -> dict[str, Any]:
        if any([tickers, universe, watchlist]):
            market = None

        lance = self.lance_service.run(
            tickers=tickers,
            universe=universe,
            watchlist=watchlist,
            market=market,
            market_limit=market_limit,
            max_workers=max_workers,
            summary_limit=summary_limit,
            persist=persist,
        )
        sykes = self.sykes_service.run(
            tickers=tickers,
            universe=universe,
            watchlist=watchlist,
            market=market,
            market_limit=market_limit,
            max_workers=max_workers,
            summary_limit=summary_limit,
            live_intraday=True,
        )
        top_slices = [
            *_agent_slices("lance", (lance.get("decision_brief") or {}).get("ticker_slices")),
            *_agent_slices("tim_sykes", sykes.get("auto_slices")),
        ][: max(0, int(summary_limit))]
        blocked_data = [
            *_blocked("lance", (lance.get("decision_brief") or {}).get("blocked")),
            *_blocked("tim_sykes", sykes.get("blocked")),
        ]
        return {
            "agent_name": "trading_desk",
            "mode": "one_run",
            "status": _status(lance, sykes),
            "session_banner": lance.get("session_banner") or sykes.get("session_banner"),
            "market_status": {
                "lance_session_banner": lance.get("session_banner"),
                "sykes_session_banner": sykes.get("session_banner"),
            },
            "desk_read": {"one_liner": _one_liner(lance, sykes)},
            "top_slices": top_slices,
            "blocked_data": blocked_data,
            "agents": {
                "lance": lance,
                "tim_sykes": sykes,
            },
            "disclaimer": DISCLAIMER,
        }


def _agent_slices(agent: str, rows: Any) -> list[dict[str, Any]]:
    output = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        output.append({
            "agent": agent,
            "ticker": row.get("ticker"),
            "lane": row.get("lane"),
            "state": row.get("state"),
            "setup": row.get("setup") or row.get("playbook"),
            "data": row.get("data"),
            "why": row.get("why"),
            "watch": row.get("watch"),
            "risk": row.get("risk"),
        })
    return output


def _blocked(agent: str, rows: Any) -> list[dict[str, Any]]:
    return [
        {"agent": agent, "ticker": row.get("ticker")}
        for row in rows or []
        if isinstance(row, dict) and row.get("ticker")
    ]


def _one_liner(lance: dict[str, Any], sykes: dict[str, Any]) -> str:
    lance_read = lance.get("single_run_read") if isinstance(lance.get("single_run_read"), dict) else {}
    sykes_read = sykes.get("desk_read") if isinstance(sykes.get("desk_read"), dict) else {}
    return f"Lance: {lance_read.get('one_liner', 'unknown')} Tim: {sykes_read.get('one_liner', 'unknown')}"


def _status(lance: dict[str, Any], sykes: dict[str, Any]) -> str:
    statuses = {str(lance.get("status") or "UNKNOWN"), str(sykes.get("status") or "UNKNOWN")}
    if statuses == {"OK"}:
        return "OK"
    if "OK" in statuses:
        return "PARTIAL"
    if "ERROR" in statuses:
        return "ERROR"
    return "UNKNOWN"
