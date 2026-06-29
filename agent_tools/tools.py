"""JSON tool functions the agent layer calls.

Each function takes JSON-friendly keyword arguments and returns a
JSON-serializable dict drawn entirely from the data layer. No number is
invented here: prices, gaps, market caps, volume, and confidence labels all
come from ScannerService / SnapshotService, which in turn come from the
providers. The agent must read these as ground truth, not guess.

The ``service`` / ``snapshot_service`` parameters are internal injection points
for tests; they are never part of the tool's JSON schema.
"""

from __future__ import annotations

from typing import Any

from app.models import (
    CatalystEvent,
    FilingEvent,
    FormerRunnerEvent,
    ScannerResult,
    SmallCapEvidence,
    make_scan_filters,
)
from services.scanner_service import ScannerService
from services.snapshot_service import SnapshotService
from services.universe_service import UniverseService


def _result_to_dict(result: ScannerResult) -> dict[str, Any]:
    return {
        "ticker": result.ticker,
        "name": result.name,
        "membership": result.universe,
        "market_cap": result.market_cap,
        "previous_close": result.previous_close,
        "premarket_price": result.premarket_price,
        "latest_price": result.latest_price,
        "gap_pct": result.gap_pct,
        "gap_dollar": result.gap_dollar,
        "gap_basis": result.gap_basis,
        "volume": result.volume,
        "rel_volume": result.rel_volume,
        "confidence": result.confidence,
        "notes": result.notes,
        "sources": result.sources,
        "timestamp": result.timestamp,
    }


def _filing_event_to_dict(filing: FilingEvent) -> dict[str, Any]:
    return {
        "ticker": filing.ticker,
        "form_type": filing.form_type,
        "filed_at": filing.filed_at,
        "accession_number": filing.accession_number,
        "description": filing.description,
        "source_url": filing.source_url,
        "risk_tags": list(filing.risk_tags),
    }


def _catalyst_event_to_dict(catalyst: CatalystEvent) -> dict[str, Any]:
    return {
        "ticker": catalyst.ticker,
        "headline": catalyst.headline,
        "published_at": catalyst.published_at,
        "source": catalyst.source,
        "url": catalyst.url,
        "summary": catalyst.summary,
        "confidence": catalyst.confidence,
        "catalyst_quality": catalyst.catalyst_quality,
        "recency_minutes": catalyst.recency_minutes,
    }


def _former_runner_event_to_dict(event: FormerRunnerEvent) -> dict[str, Any]:
    return {
        "ticker": event.ticker,
        "event_date": event.event_date,
        "max_gap_pct": event.max_gap_pct,
        "max_volume": event.max_volume,
        "source_run_id": event.source_run_id,
        "notes": list(event.notes),
    }


def _small_cap_evidence_to_dict(
    evidence: SmallCapEvidence | None,
) -> dict[str, Any] | None:
    if evidence is None:
        return None

    return {
        "ticker": evidence.ticker,
        "float_shares": evidence.float_shares,
        "shares_outstanding": evidence.shares_outstanding,
        "float_source": evidence.float_source,
        "exchange": evidence.exchange,
        "is_low_float": evidence.is_low_float,
        "float_rotation": evidence.float_rotation,
        "filings": [_filing_event_to_dict(filing) for filing in evidence.filings],
        "catalysts": [
            _catalyst_event_to_dict(catalyst) for catalyst in evidence.catalysts
        ],
        "former_runner": (
            _former_runner_event_to_dict(evidence.former_runner)
            if evidence.former_runner is not None
            else None
        ),
        "missing_fields": list(evidence.missing_fields),
        "risk_notes": list(evidence.risk_notes),
        "sources": list(evidence.sources),
        "updated_at": evidence.updated_at,
    }


def _small_cap_candidate_to_dict(candidate: Any) -> dict[str, Any]:
    missing_fields = (
        candidate.evidence.missing_fields
        if candidate.evidence is not None
        else candidate.missing_fields
    )
    return {
        "ticker": candidate.ticker,
        "name": candidate.name,
        "market_cap": candidate.market_cap,
        "gap_pct": candidate.gap_pct,
        "gap_dollar": candidate.gap_dollar,
        "gap_basis": candidate.gap_basis,
        "volume": candidate.volume,
        "rel_volume": candidate.rel_volume,
        "confidence": candidate.confidence,
        "score": candidate.score,
        "grade": candidate.grade,
        "matched_signals": candidate.matched_signals,
        "missing_fields": missing_fields,
        "risk_notes": candidate.risk_notes,
        "sources": candidate.sources,
        "evidence": _small_cap_evidence_to_dict(candidate.evidence),
        "timestamp": candidate.timestamp,
    }


def scan_premarket(
    *,
    universe: str | None = None,
    watchlist: str | None = None,
    tickers: str | None = None,
    all_universes: bool = False,
    cap_tier: str | None = None,
    min_market_cap: float = 0,
    max_market_cap: float | None = None,
    min_gap_abs: float = 0,
    min_volume: float | None = None,
    min_rel_volume: float | None = None,
    direction: str = "both",
    only_confident: bool = False,
    service: ScannerService | None = None,
) -> dict[str, Any]:
    """Run a premarket gap scan and return matching tickers as a dict."""
    if direction not in {"up", "down", "both"}:
        return {"error": f"direction must be up, down, or both (got {direction!r})."}
    if not any([universe, watchlist, tickers, all_universes]):
        return {
            "error": "Provide at least one of: universe, watchlist, tickers, or all_universes."
        }

    try:
        filters = make_scan_filters(
            cap_tier=cap_tier,
            min_market_cap=min_market_cap or 0,
            max_market_cap=max_market_cap,
            min_gap_abs=min_gap_abs or 0,
            direction=direction,  # type: ignore[arg-type]
            min_volume=min_volume,
            min_rel_volume=min_rel_volume,
            include_low_confidence=not only_confident,
        )
    except ValueError as exc:
        return {"error": str(exc)}
    scanner = service or ScannerService()
    output = scanner.scan(
        universe=universe,
        watchlist=watchlist,
        tickers=tickers,
        all_universes=all_universes,
        filters=filters,
    )
    return {
        "run_id": output.run_id,
        "selection": output.universe,
        "status": output.status,
        "result_count": len(output.results),
        "results": [_result_to_dict(r) for r in output.results],
        "notes": output.notes,
    }


def scan_small_caps(
    *,
    preset_name: str = "sykes_small_cap_v0",
    universe: str | None = None,
    watchlist: str | None = None,
    tickers: str | None = None,
    all_universes: bool = False,
    market: str | None = None,
    market_limit: int | None = None,
    service: Any | None = None,
) -> dict[str, Any]:
    """Run the small-cap scanner and return JSON-safe candidates."""
    if not any([universe, watchlist, tickers, all_universes, market]):
        return {
            "error": "Provide at least one of: universe, watchlist, tickers, market, or all_universes."
        }

    scanner = service
    if scanner is None:
        from services.small_cap_scanner_service import SmallCapScannerService

        scanner = SmallCapScannerService()

    try:
        output = scanner.scan(
            preset_name=preset_name,
            universe=universe,
            watchlist=watchlist,
            tickers=tickers,
            all_universes=all_universes,
            market=market,
            market_limit=market_limit,
        )
    except KeyError as exc:
        return {"error": str(exc)}

    return {
        "preset": output.preset,
        "run_ids": output.run_ids,
        "candidate_count": output.candidate_count,
        "candidates": [
            _small_cap_candidate_to_dict(candidate) for candidate in output.candidates
        ],
        "notes": output.notes,
    }


def list_universes(*, service: UniverseService | None = None) -> dict[str, Any]:
    """List defined universes and watchlists with their tickers."""
    svc = service or UniverseService()
    universes = svc.list_universes()
    watchlists = svc.list_watchlists()
    return {
        "universes": {
            name: {"count": len(tickers), "tickers": tickers}
            for name, tickers in universes.items()
        },
        "watchlists": {
            name: {"count": len(tickers), "tickers": tickers}
            for name, tickers in watchlists.items()
        },
    }


def get_ticker_snapshot(
    *,
    ticker: str,
    snapshot_service: SnapshotService | None = None,
) -> dict[str, Any]:
    """Return the current combined snapshot and computed gap for one ticker."""
    if not ticker or not ticker.strip():
        return {"error": "ticker is required."}

    from services.scanner_service import (
        compute_gap_dollar,
        compute_gap_pct,
        compute_rel_volume,
        gap_basis_for,
    )

    # Use the same provider construction as the scan path so a single-ticker
    # lookup and a scan agree on the number. A bare SnapshotService() is
    # yfinance-only and would drop Alpaca's premarket price, yielding a
    # different gap for the same ticker.
    svc = snapshot_service or SnapshotService.with_configured_providers()
    snap = svc.build_snapshot(ticker)
    price = snap.premarket_price if snap.premarket_price is not None else snap.latest_price
    return {
        "ticker": snap.ticker,
        "previous_close": snap.previous_close,
        "premarket_price": snap.premarket_price,
        "latest_price": snap.latest_price,
        "gap_pct": compute_gap_pct(snap.previous_close, price),
        "gap_dollar": compute_gap_dollar(snap.previous_close, price),
        "gap_basis": gap_basis_for(snap),
        "market_cap": snap.market_cap,
        "volume": snap.volume,
        "rel_volume": compute_rel_volume(snap.volume, snap.average_volume),
        "confidence": snap.confidence,
        "sources": snap.sources,
        "timestamp": snap.timestamp,
        "notes": snap.notes,
    }
