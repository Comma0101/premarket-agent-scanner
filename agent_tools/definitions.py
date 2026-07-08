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
                "include_rejected": {
                    "type": "boolean",
                    "description": (
                        "When true, include rejected candidates (with score=0, grade=REJECT, "
                        "and the original risk_notes) in the result under 'rejected'. "
                        "Off by default so existing callers see the same surface. "
                        "Use this to surface why nothing made the A/B/C buckets."
                    ),
                },
                "live_intraday": {
                    "type": "boolean",
                    "description": (
                        "Opt-in live discovery mode for regular-session small/spec movers. "
                        "Keeps rows when market cap, volume, or RVOL need enrichment; "
                        "do not treat those rows as confirmed Sykes candidates."
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
            "Run the Lance Breitstein phase-1 scan over a selected universe, "
            "watchlist, explicit tickers, or market source."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "preset_name": {"type": "string"},
                "universe": {"type": "string"},
                "watchlist": {"type": "string"},
                "tickers": {"type": "string"},
                "all_universes": {"type": "boolean"},
                "market": {"type": "string", "enum": ["us-listed"]},
                "market_limit": {"type": "integer", "minimum": 0},
                "max_workers": {"type": "integer", "minimum": 1},
            },
            "required": [],
        },
    },
    {
        "name": "run_trading_desk",
        "description": (
            "Run the one-call trading desk brief. Composes Lance large/mid-cap "
            "context and Tim Sykes small-cap context into one read with top "
            "slices and blocked data. Use this when the user asks for the desk, "
            "one run, the market right now, or all agents together."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": ["array", "string"],
                    "items": {"type": "string"},
                    "description": "Explicit tickers, comma-separated or array.",
                },
                "universe": {
                    "type": ["array", "string"],
                    "items": {"type": "string"},
                    "description": "Universe name(s).",
                },
                "watchlist": {
                    "type": ["array", "string"],
                    "items": {"type": "string"},
                    "description": "Watchlist name(s).",
                },
                "market": {
                    "type": "string",
                    "enum": ["us-listed"],
                    "description": "Whole-market source. Defaults to us-listed.",
                },
                "market_limit": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Optional cap for smoke tests; omit for full market.",
                },
                "max_workers": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Bounded worker count for broad market scans.",
                },
                "summary_limit": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Maximum combined top slices to return.",
                },
                "persist": {
                    "type": "boolean",
                    "description": "Persist Lance session state. Defaults false for quick desk reads.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "run_sykes_live",
        "description": (
            "Run the Tim Sykes-style small-cap live/swing watch package. This "
            "uses the Sykes small-cap scanner, keeps output read-only, and "
            "returns intraday watch rows, next-session swing watch rows, blocked "
            "rows, and auto slices. Use this when the user asks what Tim/Sykes "
            "thinks of the live small-cap market or tomorrow swing watch."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": ["array", "string"],
                    "items": {"type": "string"},
                    "description": "Explicit tickers, comma-separated or array.",
                },
                "universe": {
                    "type": ["array", "string"],
                    "items": {"type": "string"},
                    "description": "Universe name(s).",
                },
                "watchlist": {
                    "type": ["array", "string"],
                    "items": {"type": "string"},
                    "description": "Watchlist name(s).",
                },
                "market": {
                    "type": "string",
                    "enum": ["us-listed"],
                    "description": "Whole-market source. Defaults to us-listed.",
                },
                "market_limit": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Optional cap for smoke tests; omit for full market.",
                },
                "max_workers": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Bounded worker count for broad market scans.",
                },
                "include_rejected": {
                    "type": "boolean",
                    "description": "Include rejected rows under blocked when useful.",
                },
                "live_intraday": {
                    "type": "boolean",
                    "description": "Defaults true; keep regular-session discovery rows caveated.",
                },
                "summary_limit": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Maximum rows per watch block.",
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
    {
        "name": "scan_breitstein_intraday",
        "description": (
            "Run Phase 2 intraday analysis on Breitstein candidates. Requires "
            "Alpaca API keys for 2-minute bar data. Fetches bars, computes VWAP, "
            "prior bar levels, 2x volume confirmation, and detects entry signals "
            "with stops and targets. Call this after scan_breitstein identifies "
            "Phase 1 candidates. Every number comes from the bar data layer — "
            "never invent prices, stops, or targets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tickers to analyze (typically from Phase 1 scan_breitstein output).",
                },
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "build_lance_intraday_plan",
        "description": (
            "Build a grounded Lance Breitstein-style intraday plan card for one "
            "ticker. Returns data quality, setup state, pass/fail/unknown "
            "conditions, trigger/risk/target reference levels computed from the "
            "snapshot and 2-minute bars, and explicit missing fields. This is "
            "not trade advice; reference levels must not be presented as orders."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Ticker to analyze, e.g. IBM.",
                }
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "build_lance_swing_plan",
        "description": (
            "Build Lance Breitstein-style daily/swing watch plans for one or "
            "more tickers. Returns daily structure, relative strength versus "
            "QQQ/SPY, swing state, playbook fit, waiting_for, invalidates_if, "
            "manual review questions, and data-quality caveats. This is a "
            "read-only planning tool, not order execution or trade advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": ["array", "string"],
                    "items": {"type": "string"},
                    "description": "Ticker list or comma-separated tickers to analyze.",
                },
                "universe": {
                    "type": ["array", "string", "null"],
                    "items": {"type": "string"},
                    "description": "Optional universe name(s) from data/universes.yaml.",
                },
                "watchlist": {
                    "type": ["array", "string", "null"],
                    "items": {"type": "string"},
                    "description": "Optional watchlist name(s) from data/watchlists.yaml.",
                },
                "all_universes": {
                    "type": "boolean",
                    "description": "When true, include every configured universe.",
                    "default": False,
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "Daily bars to request for structure and relative-strength context.",
                    "default": 60,
                },
            },
            "required": [],
        },
    },
    {
        "name": "build_lance_unified_plan",
        "description": (
            "Build Lance's unified daily-plus-intraday plan for one or more "
            "tickers. Composes the swing planner and intraday planner, then "
            "labels alignment, conflicts, action_mode, waiting_for, and "
            "invalidates_if. This is a read-only co-pilot surface, not order "
            "execution or trade advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": ["array", "string"],
                    "items": {"type": "string"},
                    "description": "Ticker list or comma-separated tickers to analyze.",
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "Daily bars to request for the swing side of the plan.",
                    "default": 60,
                },
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "run_lance_swing_cycle",
        "description": (
            "Run Lance's swing desk cycle across tickers, universes, and/or watchlists. "
            "Groups continuation and swing mean-reversion watches, preserves data-quality "
            "fields, and can persist the swing watchlist for later review. Read-only; not "
            "trade advice or order execution."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": ["array", "string", "null"],
                    "items": {"type": "string"},
                    "description": "Optional ticker list or comma-separated tickers.",
                },
                "universe": {
                    "type": ["array", "string", "null"],
                    "items": {"type": "string"},
                    "description": "Optional universe name(s) from data/universes.yaml.",
                },
                "watchlist": {
                    "type": ["array", "string", "null"],
                    "items": {"type": "string"},
                    "description": "Optional watchlist name(s) from data/watchlists.yaml.",
                },
                "all_universes": {
                    "type": "boolean",
                    "description": "When true, include every configured universe.",
                    "default": False,
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "Daily bars to request for structure and relative-strength context.",
                    "default": 60,
                },
                "persist": {
                    "type": "boolean",
                    "description": "Persist swing watchlist rows/events for session review.",
                    "default": False,
                },
                "session_id": {
                    "type": ["string", "null"],
                    "description": "Optional session id to write/reuse.",
                },
                "summary_limit": {
                    "type": "integer",
                    "description": "Maximum top rows to return.",
                    "default": 10,
                },
            },
            "required": [],
        },
    },
    {
        "name": "run_lance_full_cycle",
        "description": (
            "Run Lance's full desk cycle by composing the intraday desk cycle and the "
            "daily/swing cycle. Returns separate intraday and swing sessions, summaries, "
            "top rows, and a combined ticker view showing which names appear in both lanes. "
            "Read-only; not trade advice or order execution."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": ["array", "string", "null"],
                    "items": {"type": "string"},
                    "description": "Optional ticker list or comma-separated tickers.",
                },
                "universe": {
                    "type": ["array", "string", "null"],
                    "items": {"type": "string"},
                    "description": "Optional universe name(s) from data/universes.yaml.",
                },
                "watchlist": {
                    "type": ["array", "string", "null"],
                    "items": {"type": "string"},
                    "description": "Optional watchlist name(s) from data/watchlists.yaml.",
                },
                "all_universes": {
                    "type": "boolean",
                    "description": "When true, include every configured universe.",
                    "default": False,
                },
                "market": {
                    "type": ["string", "null"],
                    "description": "Optional full-market source, e.g. us-listed. Use by itself.",
                },
                "market_limit": {
                    "type": ["integer", "null"],
                    "description": "Optional cap on market symbols for bounded testing.",
                },
                "min_gap_abs": {
                    "type": "number",
                    "description": "Minimum absolute move percentage for intraday Phase 1 discovery.",
                    "default": 3.0,
                },
                "max_candidates": {
                    "type": "integer",
                    "description": "Maximum intraday candidates to analyze.",
                    "default": 20,
                },
                "persist": {
                    "type": "boolean",
                    "description": "Persist intraday and swing watchlist rows/events.",
                    "default": True,
                },
                "session_id": {
                    "type": ["string", "null"],
                    "description": "Optional intraday session id.",
                },
                "swing_session_id": {
                    "type": ["string", "null"],
                    "description": "Optional swing session id. If omitted, swing cycle uses its default date-lance-swing id.",
                },
                "max_workers": {
                    "type": "integer",
                    "description": "Snapshot scanner worker count for intraday discovery.",
                    "default": 6,
                },
                "include_caveated_context": {
                    "type": ["boolean", "null"],
                    "description": (
                        "When true, allow STALE_DATA, CONFLICT, or LOW_CONFIDENCE rows "
                        "as caveated context. Lance data gates still block them from "
                        "A_WATCH/live execution context. If null, full-universe runs may "
                        "enable this automatically for after-hours review."
                    ),
                    "default": None,
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "Daily bars to request for the swing cycle.",
                    "default": 60,
                },
                "update_limit": {
                    "type": "integer",
                    "description": "Maximum persisted intraday rows to update.",
                    "default": 50,
                },
                "review_limit": {
                    "type": "integer",
                    "description": "Maximum timeline/review rows to inspect.",
                    "default": 500,
                },
                "target_session_date": {
                    "type": ["string", "null"],
                    "description": "Optional target date for carryover prep.",
                },
                "summary_limit": {
                    "type": "integer",
                    "description": "Rows per summary section.",
                    "default": 5,
                },
            },
            "required": [],
        },
    },
    {
        "name": "track_lance_session_changes",
        "description": (
            "Compare two run_lance_full_cycle payloads and return Lance workflow changes: "
            "new, upgraded, downgraded, unchanged, removed, and data caveats. This is a "
            "deterministic watchlist diff only; it does not infer trade outcomes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "previous": {
                    "type": ["object", "null"],
                    "description": "Previous run_lance_full_cycle payload. Use null for the first cycle.",
                },
                "current": {
                    "type": "object",
                    "description": "Current run_lance_full_cycle payload.",
                },
            },
            "required": ["previous", "current"],
        },
    },
    {
        "name": "run_lance_command_center",
        "description": (
            "Run Lance's single command-center workflow: full-cycle scan, optional session "
            "change tracking, signal-quality posture, tomorrow prep, and outcome-review "
            "commands. This composes existing Lance services and returns read-only "
            "references, not trade advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": ["array", "string", "null"],
                    "items": {"type": "string"},
                    "description": "Optional ticker list or comma-separated tickers.",
                },
                "universe": {
                    "type": ["array", "string", "null"],
                    "items": {"type": "string"},
                    "description": "Optional universe name(s) from data/universes.yaml.",
                },
                "watchlist": {
                    "type": ["array", "string", "null"],
                    "items": {"type": "string"},
                    "description": "Optional watchlist name(s) from data/watchlists.yaml.",
                },
                "all_universes": {
                    "type": "boolean",
                    "description": "When true, include every configured universe.",
                    "default": False,
                },
                "market": {
                    "type": ["string", "null"],
                    "description": "Optional full-market source, e.g. us-listed. Use by itself.",
                },
                "market_limit": {
                    "type": ["integer", "null"],
                    "description": "Optional cap on market symbols for bounded testing.",
                },
                "min_gap_abs": {
                    "type": "number",
                    "description": "Minimum absolute move percentage for intraday Phase 1 discovery.",
                    "default": 3.0,
                },
                "max_candidates": {
                    "type": "integer",
                    "description": "Maximum intraday candidates to analyze.",
                    "default": 20,
                },
                "persist": {
                    "type": "boolean",
                    "description": "Persist Lance session state for review/journaling.",
                    "default": True,
                },
                "session_id": {
                    "type": ["string", "null"],
                    "description": "Optional intraday session id.",
                },
                "swing_session_id": {
                    "type": ["string", "null"],
                    "description": "Optional swing session id.",
                },
                "max_workers": {
                    "type": "integer",
                    "description": "Snapshot scanner worker count.",
                    "default": 6,
                },
                "include_caveated_context": {
                    "type": ["boolean", "null"],
                    "description": "Whether to include stale/conflict/low-confidence names as blocked context.",
                    "default": None,
                },
                "lookback_days": {
                    "type": "integer",
                    "description": "Daily bars to request for the swing cycle.",
                    "default": 60,
                },
                "update_limit": {
                    "type": "integer",
                    "description": "Maximum persisted intraday rows to update.",
                    "default": 50,
                },
                "review_limit": {
                    "type": "integer",
                    "description": "Maximum timeline/review rows to inspect.",
                    "default": 500,
                },
                "target_session_date": {
                    "type": ["string", "null"],
                    "description": "Optional target date for carryover prep.",
                },
                "summary_limit": {
                    "type": "integer",
                    "description": "Rows per summary section.",
                    "default": 5,
                },
                "previous": {
                    "type": ["object", "null"],
                    "description": "Optional previous run_lance_full_cycle or command-center payload.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "explain_lance_ticker",
        "description": (
            "Explain one ticker from a Lance command-center payload or saved "
            "latest_command_center.json artifact. Returns the exact data Lance used, "
            "intraday/swing state, waiting/invalidation context, omitted reason when "
            "applicable, and data-quality caveats. Read-only; no trade advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Ticker to explain.",
                },
                "payload": {
                    "type": ["object", "null"],
                    "description": "Optional command-center payload. If omitted, payload_path is read.",
                },
                "payload_path": {
                    "type": ["string", "null"],
                    "description": "Path to a saved latest_command_center.json artifact.",
                    "default": "data/live_sessions/latest_command_center.json",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "run_lance_data_doctor",
        "description": (
            "Diagnose why Lance can or cannot evaluate ticker data. Groups snapshot and "
            "validation blockers into provider failure, missing price, stale/off-session, "
            "halted, confidence, or unknown root causes. Read-only; no market numbers are "
            "invented."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": ["array", "string"],
                    "items": {"type": "string"},
                    "description": "Ticker list or comma-separated tickers to diagnose.",
                },
                "max_candidates": {
                    "type": "integer",
                    "description": "Maximum Lance rows to request during validation.",
                    "default": 5,
                },
                "persist": {
                    "type": "boolean",
                    "description": "When true, persist the validation Lance cycle.",
                    "default": False,
                },
                "summary_limit": {
                    "type": ["integer", "null"],
                    "description": "Optional rows per Lance summary section.",
                    "default": None,
                },
                "review_limit": {
                    "type": "integer",
                    "description": "Maximum review rows during validation.",
                    "default": 10,
                },
                "max_workers": {
                    "type": "integer",
                    "description": "Snapshot worker count.",
                    "default": 1,
                },
                "now": {
                    "type": ["string", "null"],
                    "description": "Optional ISO timestamp override for session-mode diagnostics.",
                },
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "review_lance_full_cycle",
        "description": (
            "Build one EOD review queue for Lance's full cycle by combining the "
            "intraday session review and the swing session review. Returns journal "
            "arguments with outcome='unknown' and never infers whether a setup worked."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "intraday_session_id": {
                    "type": ["string", "null"],
                    "description": "Optional intraday session id. Defaults to latest non-swing Lance session.",
                },
                "swing_session_id": {
                    "type": ["string", "null"],
                    "description": "Optional swing session id. Defaults to latest *-lance-swing session.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum timeline events to inspect per lane.",
                    "default": 500,
                },
            },
            "required": [],
        },
    },
    {
        "name": "journal_lance_full_cycle_outcome",
        "description": (
            "Journal one manually reviewed Lance full-cycle outcome for either the "
            "intraday or swing lane. Valid outcomes are worked, failed, chop, "
            "reversed, or unknown. This records observed review labels only; it "
            "does not infer results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lane": {
                    "type": "string",
                    "enum": ["intraday", "swing"],
                    "description": "Which full-cycle lane the outcome belongs to.",
                },
                "session_id": {
                    "type": ["string", "null"],
                    "description": "Optional session id. Defaults to latest session for the lane.",
                },
                "ticker": {
                    "type": "string",
                    "description": "Ticker to journal.",
                },
                "playbook": {
                    "type": "string",
                    "description": "Playbook name being reviewed.",
                },
                "outcome": {
                    "type": "string",
                    "enum": ["worked", "failed", "chop", "reversed", "unknown"],
                    "description": "Observed outcome after manual review.",
                },
                "notes": {
                    "type": ["string", "null"],
                    "description": "Optional manual review notes.",
                },
                "plan": {
                    "type": ["object", "null"],
                    "description": "Optional plan payload to attach.",
                },
            },
            "required": ["lane", "ticker", "playbook", "outcome"],
        },
    },
    {
        "name": "get_lance_session_dashboard",
        "description": (
            "Build Lance's full-cycle session dashboard from persisted intraday and swing sessions. "
            "Combines the review queue, carryover buckets, and journaled market memory into one "
            "read-only desk workflow. Does not infer outcomes or create trade advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "intraday_session_id": {
                    "type": ["string", "null"],
                    "description": "Optional intraday Lance session id. Defaults to latest non-swing session.",
                },
                "swing_session_id": {
                    "type": ["string", "null"],
                    "description": "Optional swing Lance session id. Defaults to latest *-lance-swing session.",
                },
                "target_session_date": {
                    "type": ["string", "null"],
                    "description": "Optional next-session date label for carryover prep.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum timeline/carryover rows to inspect.",
                    "default": 500,
                },
                "memory_limit": {
                    "type": "integer",
                    "description": "Maximum journaled outcome rows to summarize.",
                    "default": 100,
                },
            },
            "required": [],
        },
    },
    {
        "name": "build_lance_tomorrow_prep",
        "description": (
            "Build Lance's next-session prep from the full-cycle dashboard. Returns a carryover "
            "watchlist, fresh-scan checklist, and memory context. Carryover rows are alerts only; "
            "fresh data and 2-minute structure are required before any upgrade."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "intraday_session_id": {
                    "type": ["string", "null"],
                    "description": "Optional intraday Lance session id. Defaults to latest non-swing session.",
                },
                "swing_session_id": {
                    "type": ["string", "null"],
                    "description": "Optional swing Lance session id. Defaults to latest *-lance-swing session.",
                },
                "target_session_date": {
                    "type": ["string", "null"],
                    "description": "Optional next-session date label.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum timeline/carryover rows to inspect.",
                    "default": 500,
                },
                "memory_limit": {
                    "type": "integer",
                    "description": "Maximum journaled outcome rows to summarize.",
                    "default": 100,
                },
            },
            "required": [],
        },
    },
    {
        "name": "run_lance_market_scan",
        "description": (
            "Run Lance Breitstein's intraday market workflow: broad scan first, "
            "then build a Lance plan for each matched ticker, rank by abnormal "
            "move, RVOL participation, prior-bar break, 2x volume, pressure, "
            "and chop, and optionally persist the watchlist for desk-mode "
            "session tracking. Every market number comes from the scanner and "
            "Lance plan services; this returns references, not trade advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": ["array", "string", "null"],
                    "items": {"type": "string"},
                    "description": "Optional ticker list or comma-separated tickers. If omitted, the tool scans all configured universes.",
                },
                "universe": {
                    "type": ["string", "array", "null"],
                    "items": {"type": "string"},
                    "description": "Optional universe name(s) from data/universes.yaml.",
                },
                "watchlist": {
                    "type": ["string", "array", "null"],
                    "items": {"type": "string"},
                    "description": "Optional watchlist name(s) from data/watchlists.yaml.",
                },
                "all_universes": {
                    "type": "boolean",
                    "description": "When true, scan all configured universes.",
                    "default": False,
                },
                "market": {
                    "type": ["string", "null"],
                    "description": "Optional full-market source, e.g. us-listed. Use by itself.",
                },
                "market_limit": {
                    "type": ["integer", "null"],
                    "description": "Optional cap on market symbols for bounded testing.",
                },
                "min_gap_abs": {
                    "type": "number",
                    "description": "Minimum absolute move percentage for Phase 1 discovery.",
                    "default": 3.0,
                },
                "max_candidates": {
                    "type": "integer",
                    "description": "Maximum ranked Lance watchlist rows to return.",
                    "default": 20,
                },
                "persist": {
                    "type": "boolean",
                    "description": "When true, save the ranked watchlist to the Lance session journal.",
                    "default": False,
                },
                "session_id": {
                    "type": ["string", "null"],
                    "description": "Optional explicit session id for persisted Lance watchlist rows.",
                },
                "max_workers": {
                    "type": "integer",
                    "description": "Snapshot scanner worker count.",
                    "default": 1,
                },
                "include_caveated_context": {
                    "type": "boolean",
                    "description": (
                        "When true, include STALE_DATA, CONFLICT, or LOW_CONFIDENCE rows "
                        "as caveated context. Lance data gates still block them from "
                        "A_WATCH/live execution context."
                    ),
                    "default": False,
                },
            },
        },
    },
    {
        "name": "update_lance_watchlist",
        "description": (
            "Refresh a persisted Lance intraday watchlist through the session. "
            "Loads the latest Lance session by default, rebuilds each ticker's "
            "current Lance plan, reports state/score/RVOL/move changes, and "
            "optionally persists the refreshed rows. Use after run_lance_market_scan "
            "when the user asks what changed since Lance flagged the names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": ["string", "null"],
                    "description": "Optional Lance session id. If omitted, the latest persisted Lance session is used.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum persisted watchlist rows to refresh.",
                    "default": 50,
                },
                "persist": {
                    "type": "boolean",
                    "description": "When true, write refreshed Lance state back to the session watchlist.",
                    "default": True,
                },
            },
        },
    },
    {
        "name": "run_advanced_lance_scan",
        "description": (
            "Run the Advanced Lance intraday co-pilot workflow. It starts with "
            "run_lance_market_scan, then adds relative strength/weakness versus "
            "SPY/QQQ, configured theme rotation, cached catalyst classification, "
            "opening-range regime, playbook fit, and market-memory hooks. All "
            "numbers come from scanner/snapshot/tool data; no orders or advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": ["array", "string", "null"],
                    "items": {"type": "string"},
                    "description": "Optional ticker list or comma-separated tickers. If omitted, all configured universes are scanned.",
                },
                "universe": {
                    "type": ["string", "array", "null"],
                    "items": {"type": "string"},
                    "description": "Optional universe name(s) from data/universes.yaml.",
                },
                "watchlist": {
                    "type": ["string", "array", "null"],
                    "items": {"type": "string"},
                    "description": "Optional watchlist name(s) from data/watchlists.yaml.",
                },
                "all_universes": {
                    "type": "boolean",
                    "description": "When true, scan all configured universes.",
                    "default": False,
                },
                "market": {
                    "type": ["string", "null"],
                    "description": "Optional full-market source, e.g. us-listed. Use by itself.",
                },
                "market_limit": {
                    "type": ["integer", "null"],
                    "description": "Optional cap on market symbols for bounded testing.",
                },
                "min_gap_abs": {
                    "type": "number",
                    "description": "Minimum absolute move percentage for Phase 1 discovery.",
                    "default": 3.0,
                },
                "max_candidates": {
                    "type": "integer",
                    "description": "Maximum ranked Advanced Lance rows to return.",
                    "default": 20,
                },
                "persist": {
                    "type": "boolean",
                    "description": "When true, save the underlying Lance watchlist rows.",
                    "default": False,
                },
                "session_id": {
                    "type": ["string", "null"],
                    "description": "Optional explicit session id for persisted Lance watchlist rows.",
                },
                "max_workers": {
                    "type": "integer",
                    "description": "Snapshot scanner worker count.",
                    "default": 1,
                },
                "include_caveated_context": {
                    "type": "boolean",
                    "description": (
                        "When true, include STALE_DATA, CONFLICT, or LOW_CONFIDENCE rows "
                        "as caveated context. Lance data gates still block them from "
                        "A_WATCH/live execution context."
                    ),
                    "default": False,
                },
            },
        },
    },
    {
        "name": "journal_lance_outcome",
        "description": (
            "Record the observed outcome for a Lance watchlist/playbook idea: "
            "worked, failed, chop, reversed, or unknown. This is the market-memory "
            "journal used later to learn which setups worked without inventing "
            "results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Lance session id, e.g. 2026-07-01-lance-intraday.",
                },
                "ticker": {
                    "type": "string",
                    "description": "Ticker whose setup outcome is being recorded.",
                },
                "playbook": {
                    "type": "string",
                    "description": "Playbook name, e.g. mean_reversion_after_capitulation.",
                },
                "outcome": {
                    "type": "string",
                    "enum": ["worked", "failed", "chop", "reversed", "unknown"],
                    "description": "Observed outcome label. Do not guess; record unknown when not reviewed.",
                },
                "notes": {
                    "type": ["string", "null"],
                    "description": "Optional human notes about the observed behavior.",
                },
                "plan": {
                    "type": ["object", "null"],
                    "description": "Optional Lance plan payload captured with the outcome.",
                },
            },
            "required": ["session_id", "ticker", "playbook", "outcome"],
        },
    },
    {
        "name": "get_lance_session_timeline",
        "description": (
            "Read Lance's append-only watchlist event timeline for a session. "
            "Use this when the user asks what happened since Lance flagged a "
            "ticker or wants to review how the watchlist evolved through the "
            "day. Returns observed scan/update events only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Lance session id, e.g. 2026-07-01-lance-intraday.",
                },
                "ticker": {
                    "type": ["string", "null"],
                    "description": "Optional ticker filter.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum timeline events to read.",
                    "default": 500,
                },
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "review_lance_session",
        "description": (
            "Build a Lance end-of-session review queue from timeline events and "
            "existing outcome journal rows. It identifies which tickers still "
            "need human review and returns safe journal_lance_outcome arguments "
            "with outcome='unknown'. It never infers whether a setup worked."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": ["string", "null"],
                    "description": "Optional Lance session id. If omitted, the latest persisted Lance session is used.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum timeline events to review.",
                    "default": 500,
                },
            },
        },
    },
    {
        "name": "build_lance_carryover_plan",
        "description": (
            "Build Lance's next-session carryover watch plan from the persisted "
            "session review queue. It groups unresolved names into strength, "
            "weakness, and context-only carryovers, returns a confirmation "
            "checklist, and requires a fresh scan before any live decision. It "
            "does not infer outcomes or produce buy/sell advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": ["string", "null"],
                    "description": "Optional Lance source session id. If omitted, the latest persisted Lance session is used.",
                },
                "target_session_date": {
                    "type": ["string", "null"],
                    "description": "Optional next-session date label, e.g. 2026-07-02.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum timeline events to inspect.",
                    "default": 500,
                },
            },
        },
    },
    {
        "name": "run_lance_desk_cycle",
        "description": (
            "Run Lance's full desk-mode cycle in one call: Advanced Lance scan, "
            "unified daily-plus-intraday Lance plans, persisted watchlist "
            "refresh, session timeline, review queue, and carryover prep. Use "
            "this when the user wants Lance to operate like a desk co-pilot "
            "instead of manually chaining tools. It reports tool-provided "
            "references only and does not place orders or give buy/sell advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": ["array", "string", "null"],
                    "items": {"type": "string"},
                    "description": "Optional ticker list or comma-separated tickers. If omitted, all configured universes are scanned.",
                },
                "universe": {
                    "type": ["string", "array", "null"],
                    "items": {"type": "string"},
                    "description": "Optional universe name(s) from data/universes.yaml.",
                },
                "watchlist": {
                    "type": ["string", "array", "null"],
                    "items": {"type": "string"},
                    "description": "Optional watchlist name(s) from data/watchlists.yaml.",
                },
                "all_universes": {
                    "type": "boolean",
                    "description": "When true, scan all configured universes.",
                    "default": False,
                },
                "market": {
                    "type": ["string", "null"],
                    "description": "Optional full-market source, e.g. us-listed. Use by itself.",
                },
                "market_limit": {
                    "type": ["integer", "null"],
                    "description": "Optional cap on market symbols for bounded testing.",
                },
                "min_gap_abs": {
                    "type": "number",
                    "description": "Minimum absolute move percentage for Phase 1 discovery.",
                    "default": 3.0,
                },
                "max_candidates": {
                    "type": "integer",
                    "description": "Maximum ranked Lance rows to return from the scan.",
                    "default": 20,
                },
                "persist": {
                    "type": "boolean",
                    "description": "When true, save scan/update rows to Lance's session journal.",
                    "default": True,
                },
                "session_id": {
                    "type": ["string", "null"],
                    "description": "Optional explicit Lance session id.",
                },
                "max_workers": {
                    "type": "integer",
                    "description": "Snapshot scanner worker count.",
                    "default": 1,
                },
                "include_caveated_context": {
                    "type": "boolean",
                    "description": (
                        "When true, include STALE_DATA, CONFLICT, or LOW_CONFIDENCE rows "
                        "as caveated context. Lance data gates still block them from "
                        "A_WATCH/live execution context."
                    ),
                    "default": False,
                },
                "update_limit": {
                    "type": "integer",
                    "description": "Maximum persisted watchlist rows to refresh.",
                    "default": 50,
                },
                "review_limit": {
                    "type": "integer",
                    "description": "Maximum timeline events to inspect for review/carryover.",
                    "default": 500,
                },
                "target_session_date": {
                    "type": ["string", "null"],
                    "description": "Optional next-session date label for carryover prep.",
                },
                "summary_limit": {
                    "type": "integer",
                    "description": "Maximum rows to include in top_watchlist, top_updates, and pending_reviews summaries.",
                    "default": 5,
                },
            },
        },
    },
    {
        "name": "validate_live_market_readiness",
        "description": (
            "Run a bounded live-market readiness check before using Lance during "
            "regular hours. It snapshots the requested tickers, reports "
            "previous_close/effective price/gap_basis/confidence/data_status/"
            "provider failures, then runs a non-persisted Lance desk cycle. Use "
            "this before market close to verify the data layer is usable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": ["array", "string"],
                    "items": {"type": "string"},
                    "description": "Ticker list or comma-separated tickers to validate.",
                },
                "max_candidates": {
                    "type": "integer",
                    "description": "Maximum Lance rows to return.",
                    "default": 5,
                },
                "persist": {
                    "type": "boolean",
                    "description": "When true, persist the underlying Lance desk cycle.",
                    "default": False,
                },
                "summary_limit": {
                    "type": "integer",
                    "description": "Rows to include in Lance summary sections.",
                    "default": 5,
                },
                "review_limit": {
                    "type": "integer",
                    "description": "Timeline rows to inspect in the Lance cycle.",
                    "default": 10,
                },
                "max_workers": {
                    "type": "integer",
                    "description": "Snapshot scanner worker count for the Lance cycle.",
                    "default": 1,
                },
                "now": {
                    "type": ["string", "null"],
                    "description": "Optional ISO timestamp override for offline/session tests.",
                },
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "summarize_lance_memory",
        "description": (
            "Summarize Lance's journaled outcome memory by playbook and ticker. "
            "Uses recorded worked/failed/chop/reversed/unknown labels only; it "
            "does not infer P&L, performance, entries, exits, or advice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": ["string", "null"],
                    "description": "Optional Lance session id filter.",
                },
                "ticker": {
                    "type": ["string", "null"],
                    "description": "Optional ticker filter.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum journaled outcome rows to summarize.",
                    "default": 100,
                },
            },
        },
    },
    {
        "name": "run_lance_replay",
        "description": (
            "Replay Lance's saved session workflow from a scratch SQLite copy. "
            "Use this when the market is closed or stale and the user wants to "
            "test Lance review, memory, and carryover behavior using today's "
            "persisted session data. Synthetic outcomes are written only to the "
            "scratch copy; the source database is not modified."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_db_path": {
                    "type": ["string", "null"],
                    "description": "Optional source SQLite path. Defaults to the configured project database.",
                },
                "scratch_db_path": {
                    "type": ["string", "null"],
                    "description": "Optional scratch SQLite path. Must differ from source_db_path.",
                },
                "scenario_name": {
                    "type": ["string", "null"],
                    "description": (
                        "Optional named replay scenario from data/lance_replay_scenarios.yaml. "
                        "Use this for repeatable closed-market Lance tests."
                    ),
                },
                "scenarios_path": {
                    "type": ["string", "null"],
                    "description": "Optional replay scenario YAML path override.",
                },
                "session_id": {
                    "type": ["string", "null"],
                    "description": "Optional Lance session id. If omitted, the latest Lance session in the copied database is used.",
                },
                "target_session_date": {
                    "type": ["string", "null"],
                    "description": "Optional next-session date label for carryover prep, e.g. 2026-07-02.",
                },
                "outcomes": {
                    "type": "array",
                    "description": (
                        "Optional synthetic replay outcome labels. Use only for workflow testing "
                        "unless the human has manually reviewed the chart/session."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "ticker": {
                                "type": "string",
                                "description": "Ticker to label in the scratch replay.",
                            },
                            "outcome": {
                                "type": "string",
                                "enum": ["worked", "failed", "chop", "reversed", "unknown"],
                                "description": "Replay label for the setup outcome.",
                            },
                            "playbook": {
                                "type": ["string", "null"],
                                "description": "Optional playbook override. Defaults to the session review playbook.",
                            },
                            "notes": {
                                "type": ["string", "null"],
                                "description": "Optional replay note.",
                            },
                        },
                        "required": ["ticker", "outcome"],
                    },
                    "default": [],
                },
                "check_assertions": {
                    "type": "boolean",
                    "description": (
                        "When true, compare replay output against the scenario's expected counts "
                        "and return PASS/FAIL assertion details."
                    ),
                    "default": False,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum review/memory/carryover rows to inspect.",
                    "default": 500,
                },
            },
        },
    },
    {
        "name": "run_lance_replay_suite",
        "description": (
            "Run every named Lance replay scenario as a closed-market regression "
            "suite. Each scenario uses its own scratch SQLite copy and evaluates "
            "expected counts. Use this when agents need a one-call PASS/FAIL "
            "check that Lance review, memory, and carryover still behave."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_db_path": {
                    "type": ["string", "null"],
                    "description": "Optional source SQLite path. Defaults to the configured project database.",
                },
                "scenarios_path": {
                    "type": ["string", "null"],
                    "description": "Optional replay scenario YAML path override.",
                },
                "scratch_dir": {
                    "type": ["string", "null"],
                    "description": "Optional directory for scratch scenario DB copies.",
                },
            },
        },
    },
    {
        "name": "run_lance_system_check",
        "description": (
            "Run Lance's closed-market replay suite and source-database safety "
            "checks in one call. Use before live desk testing to verify replay "
            "scenarios pass and the real Lance outcome journal is not mutated."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_db_path": {
                    "type": ["string", "null"],
                    "description": "Optional source SQLite path. Defaults to the configured project database.",
                },
                "scenarios_path": {
                    "type": ["string", "null"],
                    "description": "Optional replay scenario YAML path override.",
                },
                "scratch_dir": {
                    "type": ["string", "null"],
                    "description": "Optional directory for scratch scenario DB copies.",
                },
            },
        },
    },
    {
        "name": "scan_temiz_first_red_day",
        "description": "Scans a list of tickers for Alex Temiz's First Red Day entry signals (3+ green days, breaking below prior close, below VWAP).",
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tickers to scan.",
                }
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "scan_grittani_morning_panic",
        "description": "Scans a list of tickers for Tim Grittani's Morning Panic Dip Buy setups (100% run-up, 30% drop, high volume, before 10:00 AM).",
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tickers to scan.",
                }
            },
            "required": ["tickers"],
        },
    },
]

_DISPATCH: dict[str, Callable[..., dict[str, Any]]] = {
    "scan_premarket": tools.scan_premarket,
    "scan_small_caps": tools.scan_small_caps,
    "scan_breitstein": tools.scan_breitstein,
    "list_universes": tools.list_universes,
    "get_ticker_snapshot": tools.get_ticker_snapshot,
    "scan_breitstein_intraday": tools.scan_breitstein_intraday,
    "build_lance_intraday_plan": tools.build_lance_intraday_plan,
    "run_trading_desk": tools.run_trading_desk,
    "run_sykes_live": tools.run_sykes_live,
    "build_lance_swing_plan": tools.build_lance_swing_plan,
    "run_lance_swing_cycle": tools.run_lance_swing_cycle,
    "run_lance_full_cycle": tools.run_lance_full_cycle,
    "track_lance_session_changes": tools.track_lance_session_changes,
    "run_lance_command_center": tools.run_lance_command_center,
    "explain_lance_ticker": tools.explain_lance_ticker,
    "run_lance_data_doctor": tools.run_lance_data_doctor,
    "review_lance_full_cycle": tools.review_lance_full_cycle,
    "journal_lance_full_cycle_outcome": tools.journal_lance_full_cycle_outcome,
    "get_lance_session_dashboard": tools.get_lance_session_dashboard,
    "build_lance_tomorrow_prep": tools.build_lance_tomorrow_prep,
    "build_lance_unified_plan": tools.build_lance_unified_plan,
    "run_lance_market_scan": tools.run_lance_market_scan,
    "update_lance_watchlist": tools.update_lance_watchlist,
    "run_advanced_lance_scan": tools.run_advanced_lance_scan,
    "journal_lance_outcome": tools.journal_lance_outcome,
    "get_lance_session_timeline": tools.get_lance_session_timeline,
    "review_lance_session": tools.review_lance_session,
    "build_lance_carryover_plan": tools.build_lance_carryover_plan,
    "run_lance_desk_cycle": tools.run_lance_desk_cycle,
    "validate_live_market_readiness": tools.validate_live_market_readiness,
    "summarize_lance_memory": tools.summarize_lance_memory,
    "run_lance_replay": tools.run_lance_replay,
    "run_lance_replay_suite": tools.run_lance_replay_suite,
    "run_lance_system_check": tools.run_lance_system_check,
    "scan_temiz_first_red_day": tools.scan_temiz_first_red_day,
    "scan_grittani_morning_panic": tools.scan_grittani_morning_panic,
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
