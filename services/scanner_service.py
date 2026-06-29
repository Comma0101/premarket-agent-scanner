"""Premarket gap scanner.

Walks a resolved universe/watchlist, builds a snapshot per ticker, computes the
premarket gap versus previous close, applies the requested filters, and persists
the run. The output is a ScanRunOutput the CLI and (later) the agent layer render.

Market cap is resolved cache-first: if the assets table already knows a ticker's
cap we trust it, otherwise we opportunistically learn it from the yfinance
snapshot and write it back so the next run is faster.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.db import (
    complete_scanner_run,
    create_scanner_run,
    get_connection,
    get_latest_assets,
    insert_scanner_result,
    insert_snapshot,
)
from app.models import (
    AssetProfile,
    CombinedSnapshot,
    ScanFilters,
    ScannerResult,
    ScanRunOutput,
    utc_now_iso,
)
from services.profile_service import ProfileService
from services.snapshot_service import SnapshotService
from services.universe_service import UniverseSelection, UniverseService

# Confidence labels that mean "we could not establish a real gap for this name".
_UNUSABLE_CONFIDENCE = {
    "ERROR",
    "MISSING_PREVIOUS_CLOSE",
    "MISSING_PREMARKET_PRICE",
}

# Sentinel so callers can explicitly pass profile_service=None to disable
# profile enrichment (e.g. offline tests) without triggering the default.
_UNSET = object()


def compute_gap_pct(previous_close: float | None, price: float | None) -> float | None:
    if previous_close is None or price is None or previous_close == 0:
        return None
    return round((price - previous_close) / previous_close * 100, 2)


def compute_gap_dollar(previous_close: float | None, price: float | None) -> float | None:
    """Absolute dollar gap: price minus previous close.

    Uses the same effective price as compute_gap_pct (premarket if present,
    otherwise last trade) so the dollar and percent figures always agree.
    """
    if previous_close is None or price is None:
        return None
    return round(price - previous_close, 2)


def compute_rel_volume(volume: float | None, average_volume: float | None) -> float | None:
    """Relative volume (RVOL) = current volume / average daily volume."""
    if volume is None or average_volume is None or average_volume == 0:
        return None
    return round(volume / average_volume, 2)


def compute_float_rotation(volume: float | None, float_shares: float | None) -> float | None:
    """Float rotation = current volume / tradeable float."""
    if volume is None or float_shares is None or float_shares <= 0:
        return None
    return round(volume / float_shares, 4)


def gap_basis_for(snapshot: CombinedSnapshot) -> str | None:
    """Describe what the gap's effective price actually is.

    - ``"premarket"``  — a genuine premarket quote (yfinance's ``preMarketPrice``
      field, which is only populated during a live premarket session). This is
      the case the scanner is built for: gap = premarket price vs prior close.
    - ``"last_trade"`` — the most recent regular/last trade. Off-session this is a
      stale prior-session price, so the gap is a day-over-day move, NOT premarket.
      Always read this together with the confidence label (STALE_DATA off-hours).
    - ``None``         — no usable price.

    Alpaca backfills ``premarket_price`` with its latest IEX *trade*, which is not
    a premarket print, so it is reported as ``last_trade`` rather than premarket.
    """
    if snapshot.premarket_price is not None:
        yf = snapshot.yfinance_data
        if yf is not None and yf.premarket_price is not None:
            return "premarket"
        return "last_trade"
    if snapshot.latest_price is not None:
        return "last_trade"
    return None


class ScannerService:
    def __init__(
        self,
        universe_service: UniverseService | None = None,
        snapshot_service: SnapshotService | None = None,
        profile_service: Any = _UNSET,
        db_path: str | None = None,
        *,
        persist: bool = True,
    ) -> None:
        self.universe_service = universe_service or UniverseService()
        # Default builds an Alpaca cross-check when keys are present; stays
        # yfinance-only otherwise, so the no-key path is unchanged.
        self.snapshot_service = snapshot_service or SnapshotService.with_configured_providers(db_path)
        self.db_path = db_path
        self.persist = persist
        if profile_service is _UNSET:
            # Profile enrichment only runs on the persisted (online) path so the
            # default no-persist path stays network-free and side-effect-free.
            self.profile_service = ProfileService(db_path=db_path) if persist else None
        else:
            self.profile_service = profile_service

    def scan(
        self,
        *,
        universe: str | list[str] | None = None,
        watchlist: str | list[str] | None = None,
        tickers: list[str] | str | None = None,
        all_universes: bool = False,
        filters: ScanFilters | None = None,
    ) -> ScanRunOutput:
        filters = filters or ScanFilters()
        selection = self.universe_service.resolve_selection(
            universe=universe,
            watchlist=watchlist,
            tickers=tickers,
            all_universes=all_universes,
        )

        run_id = uuid.uuid4().hex[:12]
        started_at = utc_now_iso()
        run_notes: list[str] = []

        if not selection.tickers:
            return ScanRunOutput(
                run_id=run_id,
                universe=selection.label,
                started_at=started_at,
                completed_at=utc_now_iso(),
                status="EMPTY",
                results=[],
                notes=["No tickers resolved for the requested selection."],
            )

        cached_assets = self._load_cached_assets(selection.tickers)
        results: list[ScannerResult] = []

        for ticker in selection.tickers:
            try:
                result = self._scan_ticker(ticker, selection, cached_assets, filters)
            except Exception as exc:  # one bad ticker must not kill the run
                run_notes.append(f"{ticker}: scan error: {exc}")
                continue
            if result is not None:
                results.append(result)

        results.sort(key=_gap_sort_key, reverse=True)

        completed_at = utc_now_iso()
        if self.persist:
            self._persist_run(run_id, selection, filters, started_at, completed_at, results)

        return ScanRunOutput(
            run_id=run_id,
            universe=selection.label,
            started_at=started_at,
            completed_at=completed_at,
            status="OK",
            results=results,
            notes=run_notes,
        )

    def _scan_ticker(
        self,
        ticker: str,
        selection: UniverseSelection,
        cached_assets: dict[str, dict[str, Any]],
        filters: ScanFilters,
    ) -> ScannerResult | None:
        snapshot = self.snapshot_service.build_snapshot(ticker)

        if self.persist:
            self._safe_insert_snapshot(snapshot)

        cached = cached_assets.get(ticker, {})
        name = cached.get("name")
        market_cap = cached.get("market_cap")
        if market_cap is None and snapshot.market_cap is not None:
            market_cap = snapshot.market_cap
            self._learn_market_cap(snapshot)

        # The snapshot carries prices, not company names. Resolve a name (and
        # any still-missing cap) from the profile cache/providers so the result
        # is human-readable; without this the Name column is blank.
        if (name is None or market_cap is None) and self.profile_service is not None:
            profile = self._get_profile(ticker)
            if profile is not None:
                if name is None:
                    name = profile.name
                if market_cap is None:
                    market_cap = profile.market_cap

        price = (
            snapshot.premarket_price
            if snapshot.premarket_price is not None
            else snapshot.latest_price
        )
        gap_pct = compute_gap_pct(snapshot.previous_close, price)
        gap_dollar = compute_gap_dollar(snapshot.previous_close, price)
        gap_basis = gap_basis_for(snapshot)

        membership = selection.memberships.get(ticker, [])
        confidence = snapshot.confidence
        if market_cap is None and confidence == "OK":
            confidence = "MISSING_MARKET_CAP"

        rel_volume = compute_rel_volume(snapshot.volume, snapshot.average_volume)

        result = ScannerResult(
            ticker=ticker,
            name=name,
            universe=",".join(membership) if membership else None,
            market_cap=market_cap,
            previous_close=snapshot.previous_close,
            premarket_price=snapshot.premarket_price,
            latest_price=snapshot.latest_price,
            gap_pct=gap_pct,
            gap_dollar=gap_dollar,
            volume=snapshot.volume,
            confidence=confidence,
            notes="; ".join(snapshot.notes) if snapshot.notes else None,
            rel_volume=rel_volume,
            gap_basis=gap_basis,
            sources=snapshot.sources,
            timestamp=snapshot.timestamp,
        )

        if self._passes_filters(result, filters):
            return result
        return None

    def _passes_filters(self, result: ScannerResult, filters: ScanFilters) -> bool:
        if result.confidence in _UNUSABLE_CONFIDENCE:
            return False
        if not filters.include_low_confidence and result.confidence != "OK":
            return False

        # Market-cap filters. A missing cap only excludes when a bound is set.
        if filters.min_market_cap:
            if result.market_cap is None or result.market_cap < filters.min_market_cap:
                return False
        if filters.max_market_cap is not None:
            if result.market_cap is None or result.market_cap > filters.max_market_cap:
                return False

        if result.gap_pct is None:
            return False
        if filters.direction == "up" and result.gap_pct <= 0:
            return False
        if filters.direction == "down" and result.gap_pct >= 0:
            return False
        if filters.min_gap_abs and abs(result.gap_pct) < filters.min_gap_abs:
            return False

        # Volume filters. A missing value only excludes when the bound is set.
        if filters.min_volume:
            if result.volume is None or result.volume < filters.min_volume:
                return False
        if filters.min_rel_volume:
            if result.rel_volume is None or result.rel_volume < filters.min_rel_volume:
                return False

        return True

    def _load_cached_assets(self, tickers: list[str]) -> dict[str, dict[str, Any]]:
        if not self.persist:
            return {}
        try:
            with get_connection(self.db_path) as conn:
                return get_latest_assets(conn, tickers)
        except Exception:
            return {}

    def _get_profile(self, ticker: str) -> AssetProfile | None:
        if self.profile_service is None:
            return None
        try:
            return self.profile_service.get_profile(ticker)
        except Exception:
            return None

    def _learn_market_cap(self, snapshot: CombinedSnapshot) -> None:
        if not self.persist or snapshot.market_cap is None:
            return
        profile = AssetProfile(
            ticker=snapshot.ticker,
            market_cap=snapshot.market_cap,
            source="yfinance",
            profile_updated_at=utc_now_iso(),
        )
        try:
            from app.db import upsert_asset

            with get_connection(self.db_path) as conn:
                upsert_asset(conn, profile)
        except Exception:
            pass

    def _safe_insert_snapshot(self, snapshot: CombinedSnapshot) -> None:
        try:
            with get_connection(self.db_path) as conn:
                insert_snapshot(conn, snapshot)
        except Exception:
            pass

    def _persist_run(
        self,
        run_id: str,
        selection: UniverseSelection,
        filters: ScanFilters,
        started_at: str,
        completed_at: str,
        results: list[ScannerResult],
    ) -> None:
        try:
            with get_connection(self.db_path) as conn:
                create_scanner_run(
                    conn,
                    run_id=run_id,
                    universe=selection.label,
                    min_market_cap=filters.min_market_cap,
                    max_market_cap=filters.max_market_cap,
                    min_gap_abs=filters.min_gap_abs,
                    direction=filters.direction,
                    started_at=started_at,
                )
                for result in results:
                    insert_scanner_result(conn, run_id, result)
                complete_scanner_run(
                    conn,
                    run_id=run_id,
                    status="OK",
                    completed_at=completed_at,
                )
        except Exception:
            pass


def _gap_sort_key(result: ScannerResult) -> float:
    if result.gap_pct is None:
        return float("-inf")
    return abs(result.gap_pct)
