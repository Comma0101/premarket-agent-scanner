from __future__ import annotations

from app.models import ScanFilters
from services.confidence import calculate_gap_pct
from services.gap_scanner import GapScanner
from services.universe_service import UniverseService
from app.db import get_connection, get_latest_scanner_result, log_agent_query
from agent_tools.schemas import *


def scan_premarket_gaps(args: dict | ScanPremarketGapsInput) -> list[dict]:
    inp = args if isinstance(args, ScanPremarketGapsInput) else ScanPremarketGapsInput.model_validate(args)
    out = GapScanner().scan(universe=inp.universe, watchlist=inp.watchlist, tickers=inp.tickers, filters=ScanFilters(inp.min_market_cap, inp.max_market_cap, inp.min_gap_abs, inp.direction, inp.include_low_confidence), limit=inp.limit)
    results = [PremarketGapResult(**r.__dict__).model_dump() for r in out.results]
    with get_connection() as conn:
        log_agent_query(conn, user_query="", tool_name="scan_premarket_gaps", tool_args=inp.model_dump(), result_summary=f"{len(results)} results")
    return results


def explain_premarket_mover(args: dict | ExplainPremarketMoverInput) -> dict:
    inp = args if isinstance(args, ExplainPremarketMoverInput) else ExplainPremarketMoverInput.model_validate(args)
    with get_connection() as conn:
        latest = get_latest_scanner_result(conn, inp.ticker)
    memberships = UniverseService().memberships_for_ticker(inp.ticker)
    if latest:
        output = ExplainPremarketMoverOutput(ticker=inp.ticker.upper(), name=latest.get("name"), market_cap=latest.get("market_cap"), previous_close=latest.get("previous_close"), premarket_price=latest.get("premarket_price"), gap_pct=latest.get("gap_pct"), confidence=latest.get("confidence") or "ERROR", theme_memberships=memberships, notes=[latest.get("notes") or "Latest scanner result from cache."])
    else:
        rows = scan_premarket_gaps({"tickers": [inp.ticker], "include_low_confidence": True})
        row = rows[0] if rows else {}
        output = ExplainPremarketMoverOutput(ticker=inp.ticker.upper(), name=row.get("name"), market_cap=row.get("market_cap"), previous_close=row.get("previous_close"), premarket_price=row.get("premarket_price"), gap_pct=row.get("gap_pct"), confidence=row.get("confidence", "ERROR"), theme_memberships=memberships, notes=[row.get("notes") or "No scanner data available."])
    return output.model_dump()


def compare_universe_gaps(args: dict | CompareUniverseGapsInput) -> list[dict]:
    inp = args if isinstance(args, CompareUniverseGapsInput) else CompareUniverseGapsInput.model_validate(args)
    summaries = []
    for universe in inp.universes:
        rows = scan_premarket_gaps({"universe": universe, "min_market_cap": inp.min_market_cap, "include_low_confidence": True, "limit": 1000})
        gaps = [r for r in rows if r.get("gap_pct") is not None]
        ups = [r for r in gaps if r["gap_pct"] > 0]
        downs = [r for r in gaps if r["gap_pct"] < 0]
        max_up = max(ups, key=lambda r: r["gap_pct"], default=None)
        max_down = min(downs, key=lambda r: r["gap_pct"], default=None)
        summaries.append(UniverseGapSummary(universe=universe, count_total=len(rows), count_gap_up=len(ups), count_gap_down=len(downs), avg_gap_pct=(sum(r["gap_pct"] for r in gaps) / len(gaps) if gaps else None), max_gap_up_ticker=max_up.get("ticker") if max_up else None, max_gap_up_pct=max_up.get("gap_pct") if max_up else None, max_gap_down_ticker=max_down.get("ticker") if max_down else None, max_gap_down_pct=max_down.get("gap_pct") if max_down else None).model_dump())
    return summaries
