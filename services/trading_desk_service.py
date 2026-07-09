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
        data_used = _data_used(lance, sykes)
        output = {
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
            "data_used": data_used,
            "next_actions": _next_actions(lance),
            "agents": {
                "lance": lance,
                "tim_sykes": sykes,
            },
            "disclaimer": DISCLAIMER,
        }
        output["operator_brief"] = _operator_brief(output)
        return output


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


def _data_used(lance: dict[str, Any], sykes: dict[str, Any]) -> dict[str, Any]:
    return {
        "lance": lance.get("data_used") if isinstance(lance.get("data_used"), dict) else {},
        "tim_sykes": {
            "scanner": sykes.get("scanner") if isinstance(sykes.get("scanner"), dict) else {},
        },
    }


def _next_actions(lance: dict[str, Any]) -> list[str]:
    commands = lance.get("workflow_commands") if isinstance(lance.get("workflow_commands"), dict) else {}
    return [str(value) for value in commands.values() if value][:4]


def _one_liner(lance: dict[str, Any], sykes: dict[str, Any]) -> str:
    lance_read = lance.get("single_run_read") if isinstance(lance.get("single_run_read"), dict) else {}
    sykes_read = sykes.get("desk_read") if isinstance(sykes.get("desk_read"), dict) else {}
    return f"Lance: {lance_read.get('one_liner', 'unknown')} Tim: {sykes_read.get('one_liner', 'unknown')}"


def _operator_brief(output: dict[str, Any]) -> str:
    lines = [
        "# Trading Desk Operator Brief",
        "",
        f"Status: {_value(output.get('status'))}",
        f"Session: {_value(output.get('session_banner'))}",
        "",
        "## Desk Read",
        _value((output.get("desk_read") or {}).get("one_liner")),
        "",
        "## Top Ideas",
    ]
    top_slices = [row for row in output.get("top_slices") or [] if isinstance(row, dict)]
    if not top_slices:
        lines.append("- none")
    for row in top_slices:
        lines.extend([
            (
                f"- {_value(row.get('ticker'))} | agent={_value(row.get('agent'))} "
                f"| lane={_value(row.get('lane'))} | state={_value(row.get('state'))} "
                f"| setup={_value(row.get('setup'))}"
            ),
            f"  data: {_value(row.get('data'))}",
            f"  why: {_value(row.get('why'))}",
            f"  watch: {_value(row.get('watch'))}",
            f"  invalidates/risk: {_value(row.get('risk'))}",
        ])
    lines.extend(["", "## Data Used"])
    lines.extend(_data_used_lines(output.get("data_used") or {}))
    lines.extend(["", "## Blocked / Stale"])
    blocked = [row for row in output.get("blocked_data") or [] if isinstance(row, dict)]
    if not blocked:
        lines.append("- none")
    for row in blocked:
        lines.append(f"- {_value(row.get('ticker'))} | agent={_value(row.get('agent'))}")
    lines.extend(["", "## Next Actions"])
    next_actions = [str(item) for item in output.get("next_actions") or [] if item]
    if not next_actions:
        lines.append("- none")
    for item in next_actions:
        lines.append(f"- `{item}`")
    lines.extend(["", _value(output.get("disclaimer"))])
    return "\n".join(lines)


def _data_used_lines(data_used: dict[str, Any]) -> list[str]:
    lance = data_used.get("lance") if isinstance(data_used.get("lance"), dict) else {}
    sykes = data_used.get("tim_sykes") if isinstance(data_used.get("tim_sykes"), dict) else {}
    scanner = sykes.get("scanner") if isinstance(sykes.get("scanner"), dict) else {}
    lines = [f"- Lance: {_value(lance.get('summary'))}"]
    for row in (lance.get("candidate_rows") or [])[:5]:
        if isinstance(row, dict):
            lines.append(
                f"  - {_value(row.get('ticker'))}: price={_value(row.get('latest_price'))} "
                f"gap={_value(row.get('gap_pct'))}% rvol={_value(row.get('rel_volume'))}x "
                f"basis={_value(row.get('gap_basis'))} confidence={_value(row.get('confidence'))} "
                f"as_of={_value(row.get('as_of_et') or row.get('as_of'))}"
            )
    lines.append(
        f"- Tim/Sykes scanner: preset={_value(scanner.get('preset'))} "
        f"candidates={_value(scanner.get('candidate_count'))} "
        f"rejected={_value(scanner.get('rejected_count'))} "
        f"live_intraday={_value(scanner.get('live_intraday'))}"
    )
    return lines


def _value(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _status(lance: dict[str, Any], sykes: dict[str, Any]) -> str:
    statuses = {str(lance.get("status") or "UNKNOWN"), str(sykes.get("status") or "UNKNOWN")}
    if statuses == {"OK"}:
        return "OK"
    if "OK" in statuses:
        return "PARTIAL"
    if "ERROR" in statuses:
        return "ERROR"
    return "UNKNOWN"
