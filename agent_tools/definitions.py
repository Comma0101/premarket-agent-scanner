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

from contextlib import closing
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
                "max_workers": {
                    "type": "integer",
                    "minimum": 1,
                    "description": (
                        "Optional bounded worker count for broad market scans. "
                        "Use a modest value to improve live scan latency without changing data rules."
                    ),
                },
                "refresh_catalysts": {
                    "type": "boolean",
                    "description": (
                        "Opt in to live RSS catalyst lookup for candidates before "
                        "evidence scoring. Defaults to false; missing catalysts "
                        "remain unknown."
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
        "name": "scan_breitstein",
        "description": (
            "Run the Lance Breitstein-style Phase 1 underlying scanner over a "
            "watchlist, universe, explicit tickers, or market universe. It "
            "surfaces abnormal move / high-RVOL mean-reversion candidates only; "
            "Phase 1 does not produce entries, exits, targets, sizing, or advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "preset_name": {
                    "type": "string",
                    "description": (
                        "Breitstein scanner preset name. Defaults to "
                        "breitstein_mean_reversion_v0."
                    ),
                },
                "universe": {
                    "type": "string",
                    "description": "Universe name(s), comma-separated.",
                },
                "watchlist": {
                    "type": "string",
                    "description": (
                        "Watchlist name(s), comma-separated. Defaults to "
                        "HOT_ACTIVE when no selection is provided."
                    ),
                },
                "tickers": {
                    "type": "string",
                    "description": "Explicit tickers, comma-separated.",
                },
                "market": {
                    "type": "string",
                    "enum": ["us-listed"],
                    "description": (
                        "Whole-market source to scan before Breitstein filters. "
                        "Use 'us-listed' for the filtered US-listed common-stock "
                        "universe."
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
                "max_workers": {
                    "type": "integer",
                    "minimum": 1,
                    "description": (
                        "Optional bounded worker count for broad market scans. "
                        "Use a modest value to improve live scan latency without "
                        "changing data rules."
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
        "name": "explain_breitstein_ticker",
        "description": (
            "Return a grounded, moment-wise Lance Breitstein Desk explanation "
            "for one ticker. Use this when the user asks what Lance thinks of a "
            "specific stock or why a ticker did/did not qualify. The output "
            "includes data quality, setup stack, missing fields, and next-needed "
            "checks; it is not buy/sell advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The ticker symbol, e.g. 'MRVL'.",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "scan_breitstein_intraday",
        "description": (
            "Run Lance Breitstein-style Phase 2 intraday bar analysis over "
            "explicit tickers and return rule-derived reference levels from "
            "the 2-minute bar data. These are scanner facts for review, not "
            "buy/sell advice, price targets, sizing, or order instructions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": (
                        "Ticker symbols to analyze with the intraday bar rules, "
                        "e.g. ['MRVL', 'HOOD']."
                    ),
                },
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "scan_temiz_first_red_day",
        "description": (
            "Run Alex Temiz-style first-red-day analysis over explicit tickers. "
            "It checks a 3+ day green run, prior-day-close breakdown, VWAP filter, "
            "and high-of-day risk reference from bar data. Returned levels are "
            "rule-derived scanner references, not buy/sell advice, price targets, "
            "sizing, or order instructions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": (
                        "Ticker symbols to analyze with first-red-day rules, "
                        "e.g. ['HOT', 'MOMO']."
                    ),
                },
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "scan_grittani_morning_panic",
        "description": (
            "Run Tim Grittani-style morning panic analysis over explicit tickers. "
            "It checks a large multi-day run, RVOL from an upstream data-layer "
            "scan, a 9:30-10:00 ET panic drop, and first-green-bar confirmation. "
            "Returned levels are rule-derived scanner references, not buy/sell "
            "advice, price targets, sizing, or order instructions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "description": (
                        "Ticker symbols to analyze with morning panic rules, "
                        "e.g. ['HOT', 'MOMO']."
                    ),
                },
                "rvol_by_ticker": {
                    "type": "object",
                    "additionalProperties": {"type": "number"},
                    "description": (
                        "Optional grounded RVOL map keyed by ticker. A ticker "
                        "without RVOL cannot pass the Grittani service-level "
                        "volume gate."
                    ),
                },
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "get_trader_context",
        "description": (
            "Build the shared read-only trader context packet for one ticker. "
            "Use this before asking a trader profile to reason about a name. "
            "The packet carries snapshot data, evidence/news/filings/float, "
            "optional intraday EMA/VWAP, optional daily pivots, sources, "
            "timestamps, confidence, and missing fields. It is not advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Ticker symbol, e.g. 'MRVL'.",
                },
                "trader_profile": {
                    "type": "string",
                    "description": (
                        "Trader profile key for context labeling, e.g. "
                        "'timothy_sykes', 'lance_breitstein', or 'alex_temiz'."
                    ),
                },
                "include_intraday": {
                    "type": "boolean",
                    "description": (
                        "Include intraday bar-derived VWAP and EMA context when "
                        "bar data is available. Defaults to false."
                    ),
                },
                "include_daily": {
                    "type": "boolean",
                    "description": (
                        "Include daily bar-derived support/resistance pivots when "
                        "bar data is available. Defaults to false."
                    ),
                },
                "refresh_catalysts": {
                    "type": "boolean",
                    "description": (
                        "Opt in to live RSS catalyst lookup during evidence "
                        "enrichment. Defaults to false."
                    ),
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "explain_ticker_as_trader",
        "description": (
            "Build the shared read-only trader context packet for one ticker and "
            "format it into a moment-wise Desk explanation for a requested trader "
            "profile. Use this when the user asks what a distilled trader thinks "
            "of one ticker. It is not buy/sell advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Ticker symbol, e.g. 'MRVL'.",
                },
                "trader_profile": {
                    "type": "string",
                    "description": (
                        "Trader profile key, e.g. 'timothy_sykes', "
                        "'lance_breitstein', 'alex_temiz', or 'tim_grittani'."
                    ),
                },
                "include_intraday": {
                    "type": "boolean",
                    "description": (
                        "Include intraday bar-derived context when available. "
                        "Defaults to false."
                    ),
                },
                "include_daily": {
                    "type": "boolean",
                    "description": (
                        "Include daily bar-derived context when available. "
                        "Defaults to false."
                    ),
                },
                "refresh_catalysts": {
                    "type": "boolean",
                    "description": (
                        "Opt in to live RSS catalyst lookup during evidence "
                        "enrichment. Defaults to false."
                    ),
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "run_desk",
        "description": (
            "Run a grounded Desk packet across explicit tickers and trader "
            "profiles. Use this when the user wants the desk view for multiple "
            "names. The output contains data quality, missing fields, errors, "
            "and profile explanations; it is not buy/sell advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "oneOf": [
                        {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        },
                        {"type": "string"},
                    ],
                    "description": (
                        "Ticker symbols as an array or comma-separated string, "
                        "e.g. ['MRVL', 'HOOD'] or 'MRVL,HOOD'."
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
                "all_universes": {
                    "type": "boolean",
                    "description": "Use every defined universe. Defaults to false.",
                },
                "market": {
                    "type": "string",
                    "enum": ["us-listed"],
                    "description": (
                        "Whole-market source to scan before building Desk views. "
                        "Use 'us-listed' for filtered US-listed common stocks."
                    ),
                },
                "market_limit": {
                    "type": "integer",
                    "minimum": 1,
                    "description": (
                        "Optional cap for market scan smoke tests. Omit for full market."
                    ),
                },
                "max_workers": {
                    "type": "integer",
                    "minimum": 1,
                    "description": (
                        "Optional bounded worker count for broad market scans."
                    ),
                },
                "scan_preset_name": {
                    "type": "string",
                    "description": (
                        "Small-cap scan preset to use when market is provided. "
                        "Defaults to sykes_small_cap_v0."
                    ),
                },
                "trader_profiles": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Trader profile keys to run. Defaults to all active "
                        "profiles: timothy_sykes, lance_breitstein, alex_temiz, "
                        "and tim_grittani."
                    ),
                },
                "include_intraday": {
                    "type": "boolean",
                    "description": (
                        "Include intraday bar-derived context when available. "
                        "Defaults to false."
                    ),
                },
                "include_daily": {
                    "type": "boolean",
                    "description": (
                        "Include daily bar-derived context when available. "
                        "Defaults to false."
                    ),
                },
                "refresh_catalysts": {
                    "type": "boolean",
                    "description": (
                        "Opt in to live RSS catalyst lookup during evidence "
                        "enrichment. Defaults to false."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "run_morning_brief",
        "description": (
            "Run the premarket Desk morning brief. This wraps the grounded Desk "
            "run, ranks candidates into watch buckets, builds data caveats and "
            "why narratives, and optionally writes a JSON session journal. It "
            "is not buy/sell advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "string",
                    "description": (
                        "Ranking/narrative profile. Defaults to default; examples "
                        "include tim_grittani, alex_temiz, lance_breitstein, "
                        "and timothy_sykes."
                    ),
                },
                "tickers": {
                    "oneOf": [
                        {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        },
                        {"type": "string"},
                    ],
                    "description": "Ticker symbols as an array or comma-separated string.",
                },
                "universe": {
                    "type": "string",
                    "description": "Universe name(s), comma-separated.",
                },
                "watchlist": {
                    "type": "string",
                    "description": "Watchlist name(s), comma-separated.",
                },
                "all_universes": {
                    "type": "boolean",
                    "description": "Use every defined universe. Defaults to false.",
                },
                "market": {
                    "type": "string",
                    "enum": ["us-listed"],
                    "description": (
                        "Whole-market source to scan before building the brief. "
                        "Use 'us-listed' for filtered US-listed common stocks."
                    ),
                },
                "market_limit": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Optional cap for market scan smoke tests.",
                },
                "max_workers": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Optional bounded worker count for broad scans.",
                },
                "scan_preset_name": {
                    "type": "string",
                    "description": (
                        "Small-cap scan preset to use when market is provided. "
                        "Defaults to sykes_small_cap_v0."
                    ),
                },
                "include_intraday": {
                    "type": "boolean",
                    "description": "Include intraday bar context when available.",
                },
                "include_daily": {
                    "type": "boolean",
                    "description": "Include daily bar context when available.",
                },
                "refresh_catalysts": {
                    "type": "boolean",
                    "description": "Opt in to live RSS catalyst lookup.",
                },
                "save_journal": {
                    "type": "boolean",
                    "description": (
                        "Write the JSON session journal under data/sessions. "
                        "Defaults to true."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "deep_dive_ticker",
        "description": (
            "Run a single-ticker Desk deep dive in one call. It returns the "
            "grounded snapshot, evidence, technical context, support/resistance "
            "levels, every mechanical scanner result, and reference levels where "
            "a scanner triggered. It is not buy/sell advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Ticker symbol to inspect, e.g. 'MRVL'.",
                },
                "trader_profile": {
                    "type": "string",
                    "description": (
                        "Profile lens for selecting the preferred reference "
                        "context. Defaults to default; examples include "
                        "lance_breitstein, alex_temiz, tim_grittani, and "
                        "timothy_sykes."
                    ),
                },
                "include_intraday": {
                    "type": "boolean",
                    "description": (
                        "Include intraday technical context and intraday scanner "
                        "checks when bar data is available. Defaults to true."
                    ),
                },
                "include_daily": {
                    "type": "boolean",
                    "description": (
                        "Include daily pivots/context and daily-dependent scanner "
                        "checks when bar data is available. Defaults to true."
                    ),
                },
                "refresh_catalysts": {
                    "type": "boolean",
                    "description": "Opt in to live RSS catalyst lookup.",
                },
            },
            "required": ["ticker"],
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
    "scan_breitstein": tools.scan_breitstein,
    "explain_breitstein_ticker": tools.explain_breitstein_ticker,
    "scan_breitstein_intraday": tools.scan_breitstein_intraday,
    "scan_temiz_first_red_day": tools.scan_temiz_first_red_day,
    "scan_grittani_morning_panic": tools.scan_grittani_morning_panic,
    "get_trader_context": tools.get_trader_context,
    "explain_ticker_as_trader": tools.explain_ticker_as_trader,
    "run_desk": tools.run_desk,
    "run_morning_brief": tools.run_morning_brief,
    "deep_dive_ticker": tools.deep_dive_ticker,
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
        with closing(get_connection(db_path)) as conn:
            log_agent_query(
                conn,
                user_query=user_query,
                tool_name=name,
                tool_args=tool_input,
                result_summary=str(summary)[:500],
            )
    except Exception:
        pass
