from __future__ import annotations

import uuid
from pathlib import Path

from app.db import complete_scanner_run, create_scanner_run, get_connection, insert_scanner_result
from app.models import ScanFilters, ScanRunOutput, ScannerResult, utc_now_iso
from services.asset_service import AssetService, profile_is_stale
from services.confidence import calculate_gap_pct, determine_confidence, session_note
from services.snapshot_service import SnapshotService
from services.universe_service import UniverseService

LOW = {"LOW_CONFIDENCE", "CONFLICT", "MISSING_PREMARKET_PRICE", "MISSING_PREVIOUS_CLOSE", "MISSING_MARKET_CAP", "STALE_DATA", "ERROR"}


def passes_filters(result: ScannerResult, filters: ScanFilters) -> bool:
    if result.market_cap is None:
        if filters.min_market_cap or filters.max_market_cap:
            return False
    else:
        if filters.min_market_cap is not None and result.market_cap < filters.min_market_cap:
            return False
        if filters.max_market_cap is not None and result.market_cap > filters.max_market_cap:
            return False
    if result.gap_pct is None:
        return False if filters.min_gap_abs else True
    if filters.min_gap_abs is not None and abs(result.gap_pct) < filters.min_gap_abs:
        return False
    if filters.direction == "up" and result.gap_pct <= 0:
        return False
    if filters.direction == "down" and result.gap_pct >= 0:
        return False
    if not filters.include_low_confidence and result.confidence != "OK":
        return False
    return True


class GapScanner:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path
        self.universes = UniverseService()
        self.assets = AssetService(db_path=db_path)
        self.snapshots = SnapshotService(db_path=db_path)

    def scan(self, *, universe=None, watchlist=None, tickers=None, filters: ScanFilters | None = None, limit: int | None = None, sort: str = "gap_pct_abs") -> ScanRunOutput:
        filters = filters or ScanFilters()
        selection = self.universes.resolve_selection(universe=universe, watchlist=watchlist, tickers=tickers, all_universes=(universe == "all"))
        run_id = str(uuid.uuid4())
        started = utc_now_iso()
        with get_connection(self.db_path) as conn:
            create_scanner_run(conn, run_id=run_id, universe=selection.label, min_market_cap=filters.min_market_cap, max_market_cap=filters.max_market_cap, min_gap_abs=filters.min_gap_abs, direction=filters.direction, started_at=started)
        results: list[ScannerResult] = []
        notes = []
        note = session_note()
        if note:
            notes.append(note)
        try:
            for ticker in selection.tickers:
                try:
                    profile = self.assets.get_or_refresh_profile(ticker)
                    snap = self.snapshots.get_snapshot(ticker)
                    market_cap = profile.market_cap if profile else None
                    snap.confidence = determine_confidence(snapshot=snap, market_cap=market_cap, profile_is_stale=profile_is_stale(profile.__dict__ if profile else None))
                    self.snapshots.save_snapshot(snap)
                    gap = calculate_gap_pct(snap.premarket_price, snap.previous_close)
                    result = ScannerResult(ticker=ticker, name=profile.name if profile else None, universe=",".join(selection.memberships.get(ticker, [])) or selection.label, market_cap=market_cap, previous_close=snap.previous_close, premarket_price=snap.premarket_price, latest_price=snap.latest_price, gap_pct=gap, volume=snap.volume, confidence=snap.confidence, notes="; ".join([*notes, *snap.notes]) or None, sources=snap.sources, timestamp=snap.timestamp)
                except Exception as exc:
                    result = ScannerResult(ticker=ticker, name=None, universe=",".join(selection.memberships.get(ticker, [])) or selection.label, market_cap=None, previous_close=None, premarket_price=None, latest_price=None, gap_pct=None, volume=None, confidence="ERROR", notes=str(exc), sources=[])
                if passes_filters(result, filters):
                    results.append(result)
                    with get_connection(self.db_path) as conn:
                        insert_scanner_result(conn, run_id, result)
            results = _sort(results, sort)
            if limit:
                results = results[:limit]
            completed = utc_now_iso()
            with get_connection(self.db_path) as conn:
                complete_scanner_run(conn, run_id=run_id, status="COMPLETED", completed_at=completed)
            return ScanRunOutput(run_id=run_id, universe=selection.label, started_at=started, completed_at=completed, status="COMPLETED", results=results, notes=notes)
        except Exception as exc:
            completed = utc_now_iso()
            with get_connection(self.db_path) as conn:
                complete_scanner_run(conn, run_id=run_id, status="ERROR", completed_at=completed, error_message=str(exc))
            return ScanRunOutput(run_id=run_id, universe=selection.label, started_at=started, completed_at=completed, status="ERROR", results=results, notes=[*notes, str(exc)])


def _sort(results: list[ScannerResult], sort: str) -> list[ScannerResult]:
    if sort == "ticker":
        return sorted(results, key=lambda r: r.ticker)
    if sort == "market_cap":
        return sorted(results, key=lambda r: r.market_cap or -1, reverse=True)
    if sort == "gap_pct":
        return sorted(results, key=lambda r: r.gap_pct or 0, reverse=True)
    return sorted(results, key=lambda r: abs(r.gap_pct or 0), reverse=True)
