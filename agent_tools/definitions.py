"""Anthropic tool-use schema definitions and the dispatcher.

TOOLS is the list passed to ``client.messages.create(tools=...)``. Each entry is
a standard tool definition: name, description, and a JSON Schema input_schema.
Descriptions are prescriptive about *when* to call the tool — recent Claude
models reach for tools more deliberately, so the trigger condition matters.

``dispatch`` maps a tool name + parsed input to the matching function in
tools.py, logs the call to the agent_queries table, and returns the JSON result.
"""

from __future__ import annotations

from typing import Any, Callable

from agent_tools import tools

TOOLS: list[dict[str, Any]] = [
    {
        "name": "scan_premarket",
        "description": (
            "Run a premarket gap scan over a universe, watchlist, or explicit "
            "tickers and return the names that match the filters. Call this when "
            "the user asks which stocks are gapping up/down premarket, or to "
            "filter a universe by gap size, market cap, or direction. Every number "
            "in the result comes from the data layer — never invent prices or gaps."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "universe": {
                    "type": "string",
                    "description": "Universe name(s), comma-separated (e.g. 'MAG7' or 'AI_WAVE_1_COMPUTE').",
                },
                "watchlist": {
                    "type": "string",
                    "description": "Watchlist name(s), comma-separated (e.g. 'PERSONAL_ACTIVE').",
                },
                "tickers": {
                    "type": "string",
                    "description": "Explicit tickers, comma-separated (e.g. 'NVDA,AMD').",
                },
                "all_universes": {
                    "type": "boolean",
                    "description": "Scan every defined universe. Defaults to false.",
                },
                "min_market_cap": {
                    "type": "number",
                    "description": "Minimum market cap in USD (e.g. 10000000000 for $10B).",
                },
                "max_market_cap": {
                    "type": "number",
                    "description": "Maximum market cap in USD.",
                },
                "min_gap_abs": {
                    "type": "number",
                    "description": "Minimum absolute gap percent (e.g. 5 means at least 5% move either way).",
                },
                "direction": {
                    "type": "string",
                    "enum": ["up", "down", "both"],
                    "description": "Filter to gap ups, gap downs, or both. Defaults to both.",
                },
                "only_confident": {
                    "type": "boolean",
                    "description": "Drop rows that are not full-confidence (OK). Defaults to false.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "list_universes",
        "description": (
            "List the defined universes and watchlists with their member tickers. "
            "Call this when the user asks what universes/watchlists exist, or when "
            "you need a valid universe/watchlist name before running a scan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_ticker_snapshot",
        "description": (
            "Get the current premarket snapshot for a single ticker: previous "
            "close, premarket/last price, computed gap, market cap, volume, and a "
            "data-confidence label. Call this when the user asks about one specific "
            "stock rather than scanning a group."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The ticker symbol, e.g. 'NVDA'.",
                },
            },
            "required": ["ticker"],
        },
    },
]

_DISPATCH: dict[str, Callable[..., dict[str, Any]]] = {
    "scan_premarket": tools.scan_premarket,
    "list_universes": tools.list_universes,
    "get_ticker_snapshot": tools.get_ticker_snapshot,
}


def dispatch(
    name: str,
    tool_input: dict[str, Any],
    *,
    user_query: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Execute a tool by name with the given JSON input; log the call."""
    func = _DISPATCH.get(name)
    if func is None:
        return {"error": f"Unknown tool: {name}"}

    try:
        result = func(**tool_input)
    except TypeError as exc:
        result = {"error": f"Bad arguments for {name}: {exc}"}
    except Exception as exc:  # surface tool failures as data, not crashes
        result = {"error": f"{name} failed: {exc}"}

    if user_query is not None:
        _log(name, tool_input, result, user_query, db_path)
    return result


def _log(
    name: str,
    tool_input: dict[str, Any],
    result: dict[str, Any],
    user_query: str,
    db_path: str | None,
) -> None:
    try:
        from app.db import get_connection, log_agent_query

        summary = result.get("error") or f"{result.get('result_count', '')} result(s)".strip()
        with get_connection(db_path) as conn:
            log_agent_query(
                conn,
                user_query=user_query,
                tool_name=name,
                tool_args=tool_input,
                result_summary=str(summary)[:500],
            )
    except Exception:
        pass
