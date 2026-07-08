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
    BreitsteinEntrySignal,
    CatalystEvent,
    FilingEvent,
    FormerRunnerEvent,
    IntradayBar,
    ScannerResult,
    SmallCapEvidence,
    make_scan_filters,
    model_to_dict,
    utc_now_iso,
)
from services.scanner_service import ScannerService
from services.session_time_service import (
    data_caveat_for,
    format_et,
    session_banner_for,
    session_mode_for,
)
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
        "rel_volume_basis": result.rel_volume_basis,
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
    timestamp = getattr(candidate, "timestamp", None)
    as_of_et = format_et(timestamp)
    session_mode = session_mode_for(timestamp)
    return {
        "ticker": candidate.ticker,
        "name": candidate.name,
        "market_cap": candidate.market_cap,
        "gap_pct": candidate.gap_pct,
        "gap_dollar": candidate.gap_dollar,
        "gap_basis": candidate.gap_basis,
        "volume": candidate.volume,
        "rel_volume": candidate.rel_volume,
        "rel_volume_basis": getattr(candidate, "rel_volume_basis", None),
        "confidence": candidate.confidence,
        "score": candidate.score,
        "grade": candidate.grade,
        "matched_signals": candidate.matched_signals,
        "missing_fields": missing_fields,
        "risk_notes": candidate.risk_notes,
        "sources": candidate.sources,
        "evidence": _small_cap_evidence_to_dict(candidate.evidence),
        "timestamp": timestamp,
        # Human-readable NY time + raw UTC (never replace `timestamp`).
        "as_of_et": as_of_et,
        "as_of_utc": timestamp,
        "session_mode": session_mode,
        "data_caveat": data_caveat_for(
            timestamp,
            gap_basis=getattr(candidate, "gap_basis", None),
            confidence=getattr(candidate, "confidence", None),
        ),
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
    max_workers: int | None = None,
    include_rejected: bool = False,
    live_intraday: bool = False,
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
            max_workers=max_workers,
            include_rejected=include_rejected,
            live_intraday=live_intraday,
        )
    except KeyError as exc:
        return {"error": str(exc)}

    # Pick the most recent timestamp across all candidates (kept + rejected) so
    # the session banner reflects when this scan was actually computed. Falls
    # back to "now" when the underlying scan produced no timestamps at all.
    banner_timestamp = _latest_timestamp(output.candidates, output.rejected)

    response: dict[str, Any] = {
        "preset": output.preset,
        "run_ids": output.run_ids,
        "candidate_count": output.candidate_count,
        "candidates": [
            _small_cap_candidate_to_dict(candidate) for candidate in output.candidates
        ],
        "notes": output.notes,
        "session_banner": session_banner_for(banner_timestamp),
    }
    if include_rejected:
        response["rejected_count"] = output.rejected_count
        response["rejected"] = [
            _small_cap_candidate_to_dict(candidate) for candidate in output.rejected
        ]
    if output.zero_result_reason is not None:
        response["zero_result_reason"] = output.zero_result_reason
        response["relax_suggestions"] = list(output.relax_suggestions)
    return response


def _latest_timestamp(*groups: list[Any]) -> str | None:
    """Pick the most recent ISO timestamp across candidate groups.

    Used to anchor the session banner. Returns None when no timestamp is
    available so the banner falls back to its own "unknown time" wording.
    """
    latest: str | None = None
    for group in groups:
        for item in group:
            ts = getattr(item, "timestamp", None)
            if not ts:
                continue
            if latest is None or ts > latest:
                latest = ts
    return latest


def _breitstein_candidate_to_dict(candidate: Any) -> dict[str, Any]:
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
        "cap_tier": candidate.cap_tier,
        "abnormal_move": candidate.abnormal_move,
        "consecutive_days_direction": candidate.consecutive_days_direction,
        "has_catalyst": candidate.has_catalyst,
        "score": candidate.score,
        "grade": candidate.grade,
        "matched_signals": candidate.matched_signals,
        "missing_fields": missing_fields,
        "risk_notes": candidate.risk_notes,
        "sources": candidate.sources,
        "evidence": _small_cap_evidence_to_dict(candidate.evidence),
        "timestamp": candidate.timestamp,
    }


def scan_breitstein(
    *,
    preset_name: str = "breitstein_intraday_v0",
    universe: str | None = None,
    watchlist: str | None = None,
    tickers: str | None = None,
    all_universes: bool = False,
    market: str | None = None,
    market_limit: int | None = None,
    max_workers: int | None = None,
    service: Any | None = None,
) -> dict[str, Any]:
    if not any([universe, watchlist, tickers, all_universes, market]):
        return {
            "error": "Provide at least one of: universe, watchlist, tickers, market, or all_universes."
        }

    scanner = service
    if scanner is None:
        from services.breitstein_scanner_service import BreitsteinScannerService

        scanner = BreitsteinScannerService()

    try:
        output = scanner.scan(
            preset_name=preset_name,
            universe=universe,
            watchlist=watchlist,
            tickers=tickers,
            all_universes=all_universes,
            market=market,
            market_limit=market_limit,
            max_workers=max_workers,
        )
    except KeyError as exc:
        return {"error": str(exc)}

    return {
        "preset": output.preset,
        "phase": output.phase,
        "run_ids": output.run_ids,
        "candidate_count": output.candidate_count,
        "candidates": [
            _breitstein_candidate_to_dict(candidate) for candidate in output.candidates
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
        rel_volume_basis_for,
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
        "rel_volume_basis": rel_volume_basis_for(snap.volume, snap.average_volume),
        "confidence": snap.confidence,
        "data_status": snap.data_status,
        "provider_failures": dict(snap.provider_failures),
        "halt_status": model_to_dict(snap.halt_status) if snap.halt_status else None,
        "sources": snap.sources,
        "timestamp": snap.timestamp,
        "notes": snap.notes,
    }


def _intraday_bar_to_dict(bar: IntradayBar) -> dict[str, Any]:
    return {
        "ticker": bar.ticker,
        "timestamp": bar.timestamp,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "timeframe": bar.timeframe,
    }


def _breitstein_entry_signal_to_dict(signal: BreitsteinEntrySignal) -> dict[str, Any]:
    return {
        "ticker": signal.ticker,
        "direction": signal.direction,
        "entry_price": signal.entry_price,
        "stop_price": signal.stop_price,
        "target_price": signal.target_price,
        "prior_bar_high": signal.prior_bar_high,
        "prior_bar_low": signal.prior_bar_low,
        "vwap": signal.vwap,
        "vwap_filter_passed": signal.vwap_filter_passed,
        "volume_2x_confirmed": signal.volume_2x_confirmed,
        "consecutive_bars": signal.consecutive_bars,
        "rate_of_change": signal.rate_of_change,
        "bollinger_width": signal.bollinger_width,
        "timestamp": signal.timestamp,
        "confidence": signal.confidence,
        "missing_fields": list(signal.missing_fields),
    }


def scan_breitstein_intraday(
    *,
    tickers: list[str],
    service: Any | None = None,
) -> dict[str, Any]:
    if not tickers:
        return {"error": "tickers is required and must be non-empty."}

    if service is None:
        from services.intraday_analysis_service import IntradayAnalysisService

        service = IntradayAnalysisService()

    signals = []
    for ticker in tickers:
        try:
            series = service.fetch_bars(ticker)
            vwap = service.compute_vwap(series)
            signal = service.detect_entry_signal(series, vwap)
            if signal is not None:
                signals.append(signal)
        except Exception:
            signals.append(BreitsteinEntrySignal(
                ticker=ticker,
                direction="unknown",
                entry_price=None,
                stop_price=None,
                target_price=None,
                prior_bar_high=None,
                prior_bar_low=None,
                vwap=None,
                vwap_filter_passed=None,
                volume_2x_confirmed=None,
                consecutive_bars=None,
                rate_of_change=None,
                bollinger_width=None,
                timestamp=utc_now_iso(),
                confidence="ERROR",
                missing_fields=["bar_data"],
            ))

    return {
        "ticker_count": len(tickers),
        "signal_count": len(signals),
        "signals": [_breitstein_entry_signal_to_dict(s) for s in signals],
    }


def build_lance_intraday_plan(
    *,
    ticker: str,
    service: Any | None = None,
) -> dict[str, Any]:
    if not ticker or not ticker.strip():
        return {"error": "ticker is required."}

    if service is None:
        from services.lance_intraday_plan_service import LanceIntradayPlanService

        service = LanceIntradayPlanService()

    try:
        return service.build_plan(ticker.strip().upper())
    except ValueError as exc:
        return {"error": str(exc)}


def build_lance_swing_plan(
    *,
    tickers: list[str] | str | None = None,
    universe: str | list[str] | None = None,
    watchlist: str | list[str] | None = None,
    all_universes: bool = False,
    lookback_days: int = 60,
    service: Any | None = None,
    universe_service: Any | None = None,
) -> dict[str, Any]:
    if not any([tickers, universe, watchlist, all_universes]):
        return {"error": "at least one ticker is required."}

    if service is None:
        from services.lance_swing_plan_service import LanceSwingPlanService

        service = LanceSwingPlanService()

    resolved_tickers = tickers
    selection_label = None
    if any([universe, watchlist, all_universes]):
        if universe_service is None:
            from services.universe_service import UniverseService

            universe_service = UniverseService()
        selection = universe_service.resolve_selection(
            tickers=tickers,
            universe=universe,
            watchlist=watchlist,
            all_universes=all_universes,
        )
        resolved_tickers = selection.tickers
        selection_label = selection.label
        if not resolved_tickers:
            return {"error": "no tickers resolved for Lance swing plan."}

    try:
        output = service.build(
            tickers=resolved_tickers,
            lookback_days=lookback_days,
        )
        if selection_label is not None:
            output["selection"] = selection_label
            output["selection_count"] = len(resolved_tickers)
        return output
    except ValueError as exc:
        return {"error": str(exc)}


def run_lance_swing_cycle(
    *,
    tickers: list[str] | str | None = None,
    universe: str | list[str] | None = None,
    watchlist: str | list[str] | None = None,
    all_universes: bool = False,
    lookback_days: int = 60,
    persist: bool = False,
    session_id: str | None = None,
    summary_limit: int = 10,
    service: Any | None = None,
) -> dict[str, Any]:
    if not any([tickers, universe, watchlist, all_universes]):
        all_universes = True

    if service is None:
        from app.config import get_config
        from services.lance_swing_cycle_service import LanceSwingCycleService

        service = LanceSwingCycleService(db_path=get_config().database_path)

    return service.run(
        tickers=tickers,
        universe=universe,
        watchlist=watchlist,
        all_universes=all_universes,
        lookback_days=lookback_days,
        persist=persist,
        session_id=session_id,
        summary_limit=summary_limit,
    )


def run_lance_full_cycle(
    *,
    tickers: list[str] | str | None = None,
    universe: str | list[str] | None = None,
    watchlist: str | list[str] | None = None,
    all_universes: bool = False,
    market: str | None = None,
    market_limit: int | None = None,
    min_gap_abs: float = 3.0,
    max_candidates: int = 20,
    persist: bool = True,
    session_id: str | None = None,
    swing_session_id: str | None = None,
    max_workers: int = 6,
    include_caveated_context: bool | None = None,
    lookback_days: int = 60,
    update_limit: int = 50,
    review_limit: int = 500,
    target_session_date: str | None = None,
    summary_limit: int = 5,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from app.config import get_config
        from services.lance_full_cycle_service import LanceFullCycleService

        service = LanceFullCycleService(db_path=get_config().database_path)

    return service.run(
        tickers=tickers,
        universe=universe,
        watchlist=watchlist,
        all_universes=all_universes,
        market=market,
        market_limit=market_limit,
        min_gap_abs=min_gap_abs,
        max_candidates=max_candidates,
        persist=persist,
        session_id=session_id,
        swing_session_id=swing_session_id,
        max_workers=max_workers,
        include_caveated_context=include_caveated_context,
        lookback_days=lookback_days,
        update_limit=update_limit,
        review_limit=review_limit,
        target_session_date=target_session_date,
        summary_limit=summary_limit,
    )


def run_sykes_live(
    *,
    tickers: list[str] | str | None = None,
    universe: str | list[str] | None = None,
    watchlist: str | list[str] | None = None,
    market: str | None = "us-listed",
    market_limit: int | None = None,
    max_workers: int | None = 6,
    include_rejected: bool = False,
    live_intraday: bool = True,
    summary_limit: int = 10,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from services.sykes_live_plan_service import SykesLivePlanService

        service = SykesLivePlanService()

    return service.run(
        tickers=tickers,
        universe=universe,
        watchlist=watchlist,
        market=market,
        market_limit=market_limit,
        max_workers=max_workers,
        include_rejected=include_rejected,
        live_intraday=live_intraday,
        summary_limit=summary_limit,
    )


def run_trading_desk(
    *,
    tickers: list[str] | str | None = None,
    universe: str | list[str] | None = None,
    watchlist: str | list[str] | None = None,
    market: str | None = "us-listed",
    market_limit: int | None = None,
    max_workers: int = 6,
    summary_limit: int = 8,
    persist: bool = False,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from services.trading_desk_service import TradingDeskService

        service = TradingDeskService()

    return service.run(
        tickers=tickers,
        universe=universe,
        watchlist=watchlist,
        market=market,
        market_limit=market_limit,
        max_workers=max_workers,
        summary_limit=summary_limit,
        persist=persist,
    )


def track_lance_session_changes(
    *,
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from services.lance_session_tracker_service import LanceSessionTrackerService

        service = LanceSessionTrackerService()

    return service.diff(previous=previous, current=current)


def run_lance_command_center(
    *,
    tickers: list[str] | str | None = None,
    universe: str | list[str] | None = None,
    watchlist: str | list[str] | None = None,
    all_universes: bool = False,
    market: str | None = None,
    market_limit: int | None = None,
    min_gap_abs: float = 3.0,
    max_candidates: int = 20,
    persist: bool = True,
    session_id: str | None = None,
    swing_session_id: str | None = None,
    max_workers: int = 6,
    include_caveated_context: bool | None = None,
    lookback_days: int = 60,
    update_limit: int = 50,
    review_limit: int = 500,
    target_session_date: str | None = None,
    summary_limit: int = 5,
    previous: dict[str, Any] | None = None,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from app.config import get_config
        from services.lance_command_center_service import LanceCommandCenterService

        service = LanceCommandCenterService(db_path=get_config().database_path)

    return service.run(
        tickers=tickers,
        universe=universe,
        watchlist=watchlist,
        all_universes=all_universes,
        market=market,
        market_limit=market_limit,
        min_gap_abs=min_gap_abs,
        max_candidates=max_candidates,
        persist=persist,
        session_id=session_id,
        swing_session_id=swing_session_id,
        max_workers=max_workers,
        include_caveated_context=include_caveated_context,
        lookback_days=lookback_days,
        update_limit=update_limit,
        review_limit=review_limit,
        target_session_date=target_session_date,
        summary_limit=summary_limit,
        previous=previous,
    )


def explain_lance_ticker(
    *,
    ticker: str,
    payload: dict[str, Any] | None = None,
    payload_path: str | None = "data/live_sessions/latest_command_center.json",
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from services.lance_ticker_explain_service import LanceTickerExplainService

        service = LanceTickerExplainService()

    return service.explain(
        ticker=ticker,
        payload=payload,
        payload_path=payload_path,
    )


def run_lance_data_doctor(
    *,
    tickers: list[str] | str,
    max_candidates: int = 5,
    persist: bool = False,
    summary_limit: int | None = None,
    review_limit: int = 10,
    max_workers: int = 1,
    now: str | None = None,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from services.lance_data_doctor_service import LanceDataDoctorService

        service = LanceDataDoctorService()

    return service.diagnose(
        tickers=tickers,
        max_candidates=max_candidates,
        persist=persist,
        summary_limit=summary_limit,
        review_limit=review_limit,
        max_workers=max_workers,
        now=now,
    )


def review_lance_full_cycle(
    *,
    intraday_session_id: str | None = None,
    swing_session_id: str | None = None,
    limit: int = 500,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from app.config import get_config
        from services.lance_full_cycle_review_service import LanceFullCycleReviewService

        service = LanceFullCycleReviewService(db_path=get_config().database_path)

    return service.review(
        intraday_session_id=intraday_session_id,
        swing_session_id=swing_session_id,
        limit=limit,
    )


def journal_lance_full_cycle_outcome(
    *,
    lane: str,
    session_id: str | None = None,
    ticker: str,
    playbook: str,
    outcome: str,
    notes: str | None = None,
    plan: dict[str, Any] | None = None,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from app.config import get_config
        from services.lance_full_cycle_review_service import LanceFullCycleReviewService

        service = LanceFullCycleReviewService(db_path=get_config().database_path)

    return service.record_outcome(
        lane=lane,
        session_id=session_id,
        ticker=ticker,
        playbook=playbook,
        outcome=outcome,
        notes=notes,
        plan=plan,
    )


def get_lance_session_dashboard(
    *,
    intraday_session_id: str | None = None,
    swing_session_id: str | None = None,
    target_session_date: str | None = None,
    limit: int = 500,
    memory_limit: int = 100,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from app.config import get_config
        from services.lance_session_dashboard_service import LanceSessionDashboardService

        service = LanceSessionDashboardService(db_path=get_config().database_path)

    return service.dashboard(
        intraday_session_id=intraday_session_id,
        swing_session_id=swing_session_id,
        target_session_date=target_session_date,
        limit=limit,
        memory_limit=memory_limit,
    )


def build_lance_tomorrow_prep(
    *,
    intraday_session_id: str | None = None,
    swing_session_id: str | None = None,
    target_session_date: str | None = None,
    limit: int = 500,
    memory_limit: int = 100,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from app.config import get_config
        from services.lance_session_dashboard_service import LanceSessionDashboardService

        service = LanceSessionDashboardService(db_path=get_config().database_path)

    return service.tomorrow_prep(
        intraday_session_id=intraday_session_id,
        swing_session_id=swing_session_id,
        target_session_date=target_session_date,
        limit=limit,
        memory_limit=memory_limit,
    )


def build_lance_unified_plan(
    *,
    tickers: list[str] | str,
    lookback_days: int = 60,
    service: Any | None = None,
) -> dict[str, Any]:
    if not tickers:
        return {"error": "at least one ticker is required."}

    if service is None:
        from app.config import get_config
        from services.lance_unified_plan_service import LanceUnifiedPlanService

        service = LanceUnifiedPlanService(db_path=get_config().database_path)

    try:
        return service.build(
            tickers=tickers,
            lookback_days=lookback_days,
        )
    except ValueError as exc:
        return {"error": str(exc)}


def run_lance_market_scan(
    *,
    tickers: list[str] | str | None = None,
    universe: str | list[str] | None = None,
    watchlist: str | list[str] | None = None,
    all_universes: bool = False,
    market: str | None = None,
    market_limit: int | None = None,
    min_gap_abs: float = 3.0,
    max_candidates: int = 20,
    include_caveated_context: bool = False,
    persist: bool = False,
    session_id: str | None = None,
    max_workers: int = 1,
    service: Any | None = None,
) -> dict[str, Any]:
    if not any([tickers, universe, watchlist, all_universes, market]):
        all_universes = True

    if service is None:
        from services.lance_market_scan_service import LanceMarketScanService

        service = LanceMarketScanService()

    return service.scan(
        tickers=tickers,
        universe=universe,
        watchlist=watchlist,
        all_universes=all_universes,
        market=market,
        market_limit=market_limit,
        min_gap_abs=min_gap_abs,
        max_candidates=max_candidates,
        include_caveated_context=include_caveated_context,
        persist=persist,
        session_id=session_id,
        max_workers=max_workers,
    )


def update_lance_watchlist(
    *,
    session_id: str | None = None,
    limit: int = 50,
    persist: bool = True,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from services.lance_desk_update_service import LanceDeskUpdateService

        service = LanceDeskUpdateService()

    return service.update(
        session_id=session_id,
        limit=limit,
        persist=persist,
    )


def run_advanced_lance_scan(
    *,
    tickers: list[str] | str | None = None,
    universe: str | list[str] | None = None,
    watchlist: str | list[str] | None = None,
    all_universes: bool = False,
    market: str | None = None,
    market_limit: int | None = None,
    min_gap_abs: float = 3.0,
    max_candidates: int = 20,
    include_caveated_context: bool = False,
    persist: bool = False,
    session_id: str | None = None,
    max_workers: int = 1,
    service: Any | None = None,
) -> dict[str, Any]:
    if not any([tickers, universe, watchlist, all_universes, market]):
        all_universes = True

    if service is None:
        from services.lance_advanced_context_service import LanceAdvancedContextService

        service = LanceAdvancedContextService()

    return service.scan(
        tickers=tickers,
        universe=universe,
        watchlist=watchlist,
        all_universes=all_universes,
        market=market,
        market_limit=market_limit,
        min_gap_abs=min_gap_abs,
        max_candidates=max_candidates,
        include_caveated_context=include_caveated_context,
        persist=persist,
        session_id=session_id,
        max_workers=max_workers,
    )


def journal_lance_outcome(
    *,
    session_id: str,
    ticker: str,
    playbook: str,
    outcome: str,
    notes: str | None = None,
    plan: dict[str, Any] | None = None,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from services.lance_outcome_journal_service import LanceOutcomeJournalService

        service = LanceOutcomeJournalService()

    return service.record(
        session_id=session_id,
        ticker=ticker,
        playbook=playbook,
        outcome=outcome,
        notes=notes,
        plan=plan,
    )


def get_lance_session_timeline(
    *,
    session_id: str,
    ticker: str | None = None,
    limit: int = 500,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from services.lance_session_timeline_service import LanceSessionTimelineService

        service = LanceSessionTimelineService()

    return service.timeline(
        session_id=session_id,
        ticker=ticker,
        limit=limit,
    )


def review_lance_session(
    *,
    session_id: str | None = None,
    limit: int = 500,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from services.lance_session_review_service import LanceSessionReviewService

        service = LanceSessionReviewService()

    return service.review(
        session_id=session_id,
        limit=limit,
    )


def build_lance_carryover_plan(
    *,
    session_id: str | None = None,
    target_session_date: str | None = None,
    limit: int = 500,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from services.lance_carryover_plan_service import LanceCarryoverPlanService

        service = LanceCarryoverPlanService()

    return service.build(
        session_id=session_id,
        target_session_date=target_session_date,
        limit=limit,
    )


def run_lance_desk_cycle(
    *,
    tickers: list[str] | str | None = None,
    universe: str | list[str] | None = None,
    watchlist: str | list[str] | None = None,
    all_universes: bool = False,
    market: str | None = None,
    market_limit: int | None = None,
    min_gap_abs: float = 3.0,
    max_candidates: int = 20,
    persist: bool = True,
    session_id: str | None = None,
    max_workers: int = 1,
    include_caveated_context: bool = False,
    update_limit: int = 50,
    review_limit: int = 500,
    target_session_date: str | None = None,
    summary_limit: int = 5,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from services.lance_desk_cycle_service import LanceDeskCycleService

        service = LanceDeskCycleService()

    return service.run(
        tickers=tickers,
        universe=universe,
        watchlist=watchlist,
        all_universes=all_universes,
        market=market,
        market_limit=market_limit,
        min_gap_abs=min_gap_abs,
        max_candidates=max_candidates,
        persist=persist,
        session_id=session_id,
        max_workers=max_workers,
        include_caveated_context=include_caveated_context,
        update_limit=update_limit,
        review_limit=review_limit,
        target_session_date=target_session_date,
        summary_limit=summary_limit,
    )


def validate_live_market_readiness(
    *,
    tickers: list[str] | str,
    max_candidates: int = 5,
    persist: bool = False,
    summary_limit: int = 5,
    review_limit: int = 10,
    max_workers: int = 1,
    now: str | None = None,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from services.live_market_validation_service import LiveMarketValidationService

        service = LiveMarketValidationService()

    return service.run(
        tickers=tickers,
        max_candidates=max_candidates,
        persist=persist,
        summary_limit=summary_limit,
        review_limit=review_limit,
        max_workers=max_workers,
        now=now,
    )


def summarize_lance_memory(
    *,
    session_id: str | None = None,
    ticker: str | None = None,
    limit: int = 100,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from services.lance_memory_report_service import LanceMemoryReportService

        service = LanceMemoryReportService()

    return service.summarize(
        session_id=session_id,
        ticker=ticker,
        limit=limit,
    )


def run_lance_replay(
    *,
    source_db_path: str | None = None,
    scratch_db_path: str | None = None,
    scenario_name: str | None = None,
    scenarios_path: str | None = None,
    session_id: str | None = None,
    target_session_date: str | None = None,
    outcomes: list[dict[str, Any]] | None = None,
    limit: int = 500,
    check_assertions: bool = False,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from app.config import get_config
        from services.lance_replay_service import LanceReplayService

        source_db_path = source_db_path or str(get_config().database_path)
        service = LanceReplayService()

    return service.replay(
        source_db_path=source_db_path,
        scratch_db_path=scratch_db_path,
        scenario_name=scenario_name,
        scenarios_path=scenarios_path,
        session_id=session_id,
        target_session_date=target_session_date,
        outcomes=outcomes or [],
        limit=limit,
        check_assertions=check_assertions,
    )


def run_lance_replay_suite(
    *,
    source_db_path: str | None = None,
    scenarios_path: str | None = None,
    scratch_dir: str | None = None,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from app.config import get_config
        from services.lance_replay_suite_service import LanceReplaySuiteService

        source_db_path = source_db_path or str(get_config().database_path)
        service = LanceReplaySuiteService()

    return service.run(
        source_db_path=source_db_path,
        scenarios_path=scenarios_path,
        scratch_dir=scratch_dir,
    )


def run_lance_system_check(
    *,
    source_db_path: str | None = None,
    scenarios_path: str | None = None,
    scratch_dir: str | None = None,
    service: Any | None = None,
) -> dict[str, Any]:
    if service is None:
        from app.config import get_config
        from services.lance_system_check_service import LanceSystemCheckService

        source_db_path = source_db_path or str(get_config().database_path)
        service = LanceSystemCheckService()

    return service.run(
        source_db_path=source_db_path,
        scenarios_path=scenarios_path,
        scratch_dir=scratch_dir,
    )


def scan_temiz_first_red_day(tickers: list[str], service: Any = None) -> dict[str, Any]:
    from providers.alpaca_provider import AlpacaProvider
    from services.temiz_analysis_service import TemizAnalysisService
    from app.models import model_to_dict
    import logging

    if not tickers:
        return {"error": "Must provide at least one ticker."}

    if service is None:
        service = TemizAnalysisService(provider=AlpacaProvider())

    signals = []
    for ticker in tickers:
        try:
            signal = service.detect_first_red_day(ticker)
            if signal is not None:
                signals.append(signal)
        except Exception as exc:
            logging.warning(f"Temiz scan failed for {ticker}: {exc}")

    return {
        "ticker_count": len(tickers),
        "signal_count": len(signals),
        "signals": [model_to_dict(s) for s in signals],
    }


def scan_grittani_morning_panic(tickers: list[str], service: Any = None) -> dict[str, Any]:
    from providers.alpaca_provider import AlpacaProvider
    from services.grittani_analysis_service import GrittaniAnalysisService
    from app.models import model_to_dict
    import logging

    if not tickers:
        return {"error": "Must provide at least one ticker."}

    if service is None:
        service = GrittaniAnalysisService(provider=AlpacaProvider())

    signals = []
    for ticker in tickers:
        try:
            signal = service.detect_morning_panic(ticker)
            if signal is not None:
                signals.append(signal)
        except Exception as exc:
            logging.warning(f"Grittani scan failed for {ticker}: {exc}")

    return {
        "ticker_count": len(tickers),
        "signal_count": len(signals),
        "signals": [model_to_dict(s) for s in signals],
    }
