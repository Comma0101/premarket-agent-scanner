"""Tool-use schema definitions and the dispatcher.

TOOLS is the list of tool definitions (name, description, JSON-Schema
input_schema) handed to whichever LLM drives the agent. The shape is the
standard function-calling format used by Claude, OpenAI, Gemini, etc.
Descriptions are prescriptive about *when* to call the tool — recent models
reach for tools more deliberately, so the trigger condition matters.

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
                "cap_tier": {
                    "type": "string",
                    "enum": ["nano", "micro", "small", "mid", "large", "mega"],
                    "description": (
                        "Market-cap tier shortcut that sets the cap bounds: small (~$300M-$2B), "
                        "mid ($2B-$10B), large ($10B-$200B), mega (>$200B), etc. Use this for "
                        "'small cap gappers' or 'large cap gappers' instead of raw cap numbers."
                    ),
                },
                "min_market_cap": {
                    "type": "number",
                    "description": "Minimum market cap in USD (e.g. 10000000000 for $10B). Overrides cap_tier's lower bound.",
                },
                "max_market_cap": {
                    "type": "number",
                    "description": "Maximum market cap in USD. Overrides cap_tier's upper bound.",
                },
                "min_gap_abs": {
                    "type": "number",
                    "description": "Minimum absolute gap percent (e.g. 5 means at least 5% move either way).",
                },
                "min_volume": {
                    "type": "number",
                    "description": "Minimum traded volume in shares.",
                },
                "min_rel_volume": {
                    "type": "number",
                    "description": (
                        "Minimum relative volume (RVOL = current volume / average daily volume). "
                        "E.g. 2 means at least twice normal volume — a key small-cap gapper signal."
                    ),
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
        "name": "scan_small_caps",
        "description": (
            "Run the small-cap watchlist scanner over a universe, watchlist, or "
            "explicit tickers and return grounded candidate data. This is a "
            "small-cap watchlist scanner, not a trade recommendation engine; do "
            "not present candidates as execution advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "preset_name": {
                    "type": "string",
                    "description": (
                        "Small-cap scanner preset name. Defaults to sykes_small_cap_v0."
                    ),
                },
                "universe": {
                    "type": "string",
                    "description": "Universe name(s), comma-separated.",
                },
                "watchlist": {
                    "type": "string",
                    "description": "Watchlist name(s), comma-separated.",
                },
                "tickers": {
                    "type": "string",
                    "description": "Explicit tickers, comma-separated.",
                },
                "market": {
                    "type": "string",
                    "enum": ["us-listed"],
                    "description": (
                        "Whole-market source to scan before small-cap filters. "
                        "Use 'us-listed' for the filtered US-listed common-stock universe."
                    ),
                },
                "market_limit": {
                    "type": "integer",
                    "minimum": 1,
                    "description": (
                        "Optional cap on the number of market symbols to scan. "
                        "Use only for smoke tests; omit for the full market."
                    ),
                },
                "all_universes": {
                    "type": "boolean",
                    "description": "Scan every defined universe. Defaults to false.",
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
    "scan_small_caps": tools.scan_small_caps,
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

        count = result.get("result_count", result.get("candidate_count", ""))
        summary = result.get("error") or f"{count} result(s)".strip()
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
