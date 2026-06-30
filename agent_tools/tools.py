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
    FirstRedDaySignal,
    FormerRunnerEvent,
    GrittaniPanicSignal,
    IntradayBar,
    ScannerResult,
    SmallCapEvidence,
    make_scan_filters,
    utc_now_iso,
)
from services.scanner_service import ScannerService
from services.session_time_service import (
    data_caveat_for,
    format_et,
    parse_iso_utc,
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
        "as_of_et": format_et(timestamp),
        "as_of_utc": timestamp,
        "session_mode": session_mode_for(timestamp),
        "data_caveat": data_caveat_for(
            timestamp,
            gap_basis=candidate.gap_basis,
            confidence=candidate.confidence,
        ),
    }


def _latest_candidate_timestamp(candidates: list[Any]) -> str | None:
    latest_raw: str | None = None
    latest_dt = None
    for candidate in candidates:
        raw = getattr(candidate, "timestamp", None)
        parsed = parse_iso_utc(raw)
        if parsed is None:
            continue
        if latest_dt is None or parsed > latest_dt:
            latest_dt = parsed
            latest_raw = raw
    return latest_raw


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


def _first_red_day_signal_to_dict(signal: FirstRedDaySignal) -> dict[str, Any]:
    return {
        "ticker": signal.ticker,
        "consecutive_green_days": signal.consecutive_green_days,
        "breakdown_reference_price": signal.breakdown_reference_price,
        "risk_reference_price": signal.risk_reference_price,
        "prior_day_close": signal.prior_day_close,
        "hod_before_breakdown": signal.hod_before_breakdown,
        "breakdown_bar_low": signal.breakdown_bar_low,
        "vwap": signal.vwap,
        "vwap_filter_passed": signal.vwap_filter_passed,
        "timestamp": signal.timestamp,
        "source": signal.source,
        "fetched_at": signal.fetched_at,
        "confidence": signal.confidence,
        "missing_fields": list(signal.missing_fields),
        "notes": list(signal.notes),
    }


def _grittani_panic_signal_to_dict(signal: GrittaniPanicSignal) -> dict[str, Any]:
    return {
        "ticker": signal.ticker,
        "multi_day_run_pct": signal.multi_day_run_pct,
        "intraday_drop_pct": signal.intraday_drop_pct,
        "panic_high": signal.panic_high,
        "panic_low": signal.panic_low,
        "bounce_reference_price": signal.bounce_reference_price,
        "risk_reference_price": signal.risk_reference_price,
        "prior_day_close": signal.prior_day_close,
        "vwap": signal.vwap,
        "rvol": signal.rvol,
        "timestamp": signal.timestamp,
        "source": signal.source,
        "fetched_at": signal.fetched_at,
        "confidence": signal.confidence,
        "missing_fields": list(signal.missing_fields),
        "notes": list(signal.notes),
    }


def _first_red_day_error_to_dict(ticker: str, exc: Exception) -> dict[str, Any]:
    return {
        "ticker": ticker.upper(),
        "confidence": "ERROR",
        "missing_fields": ["bar_data"],
        "error": str(exc),
        "timestamp": utc_now_iso(),
        "notes": [
            "First red day scan failed for this ticker; no signal was inferred."
        ],
    }


def _grittani_panic_error_to_dict(ticker: str, exc: Exception) -> dict[str, Any]:
    return {
        "ticker": ticker.upper(),
        "confidence": "ERROR",
        "missing_fields": ["bar_data"],
        "error": str(exc),
        "timestamp": utc_now_iso(),
        "notes": [
            "Morning panic scan failed for this ticker; no signal was inferred."
        ],
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
    refresh_catalysts: bool = False,
    include_rejected: bool = False,
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

        if refresh_catalysts:
            from providers.news_provider import RSSNewsProvider
            from services.small_cap_evidence_service import SmallCapEvidenceService

            scanner = SmallCapScannerService(
                evidence_service=SmallCapEvidenceService(
                    news_provider=RSSNewsProvider(),
                )
            )
        else:
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
        )
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}

    notes = list(output.notes)
    if refresh_catalysts and service is None:
        notes.insert(
            0,
            (
                "Live catalyst RSS refresh enabled for candidate enrichment; "
                "missing catalysts remain unknown."
            ),
        )

    candidates = list(output.candidates)
    rejected = list(getattr(output, "rejected", []))
    response = {
        "preset": output.preset,
        "run_ids": output.run_ids,
        "candidate_count": output.candidate_count,
        "candidates": [
            _small_cap_candidate_to_dict(candidate) for candidate in candidates
        ],
        "session_banner": session_banner_for(
            _latest_candidate_timestamp(candidates + rejected)
        ),
        "notes": notes,
    }
    if include_rejected:
        response["rejected_count"] = getattr(output, "rejected_count", len(rejected))
        response["rejected"] = [
            _small_cap_candidate_to_dict(candidate) for candidate in rejected
        ]
    if getattr(output, "zero_result_reason", None):
        response["zero_result_reason"] = output.zero_result_reason
        response["relax_suggestions"] = list(output.relax_suggestions)
    return response


def scan_breitstein(
    *,
    preset_name: str = "breitstein_mean_reversion_v0",
    universe: str | list[str] | None = None,
    watchlist: str | list[str] | None = None,
    tickers: list[str] | str | None = None,
    all_universes: bool = False,
    market: str | None = None,
    market_limit: int | None = None,
    max_workers: int | None = None,
    service: Any | None = None,
) -> dict[str, Any]:
    """Run the Lance Breitstein Phase 1 underlying scanner."""
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
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}

    return {
        "preset": output.preset,
        "run_ids": output.run_ids,
        "phase": output.phase,
        "candidate_count": output.candidate_count,
        "candidates": [
            _breitstein_candidate_to_dict(candidate)
            for candidate in output.candidates
        ],
        "notes": output.notes,
    }


def explain_breitstein_ticker(
    *,
    ticker: str,
    snapshot_service: SnapshotService | None = None,
    service: Any | None = None,
) -> dict[str, Any]:
    """Return a moment-wise Lance Desk explanation for one ticker."""
    if not ticker or not ticker.strip():
        return {"error": "ticker is required."}

    snapshot = get_ticker_snapshot(
        ticker=ticker,
        snapshot_service=snapshot_service,
    )
    if "error" in snapshot:
        return snapshot

    scan_output = scan_breitstein(
        tickers=ticker.strip().upper(),
        service=service,
    )
    if "error" in scan_output:
        return scan_output

    from services.desk_explainer import build_breitstein_ticker_explanation

    return build_breitstein_ticker_explanation(
        snapshot=snapshot,
        scan_output=scan_output,
    )


def scan_breitstein_intraday(
    *,
    tickers: list[str],
    service: Any | None = None,
) -> dict[str, Any]:
    """Run Lance Phase 2 intraday bar analysis over explicit tickers."""
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
            signals.append(
                BreitsteinEntrySignal(
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
                )
            )

    return {
        "ticker_count": len(tickers),
        "signal_count": len(signals),
        "signals": [_breitstein_entry_signal_to_dict(signal) for signal in signals],
        "notes": [
            "Intraday levels are rule-derived scanner references, not execution advice."
        ],
    }


def scan_temiz_first_red_day(
    *,
    tickers: list[str],
    service: Any | None = None,
) -> dict[str, Any]:
    """Run Alex Temiz first-red-day analysis over explicit tickers."""
    if not tickers:
        return {"error": "tickers is required and must be non-empty."}

    if service is None:
        from providers.alpaca_provider import AlpacaProvider
        from services.temiz_analysis_service import TemizAnalysisService

        service = TemizAnalysisService(provider=AlpacaProvider())

    signals = []
    errors = []
    for ticker in tickers:
        try:
            signal = service.detect_first_red_day(ticker)
            if signal is not None:
                signals.append(_first_red_day_signal_to_dict(signal))
        except Exception as exc:
            errors.append(_first_red_day_error_to_dict(ticker, exc))

    return {
        "ticker_count": len(tickers),
        "signal_count": len(signals),
        "signals": signals,
        "error_count": len(errors),
        "errors": errors,
        "notes": [
            "First red day levels are rule-derived scanner references, not execution advice."
        ],
    }


def scan_grittani_morning_panic(
    *,
    tickers: list[str],
    rvol_by_ticker: dict[str, float] | None = None,
    service: Any | None = None,
) -> dict[str, Any]:
    """Run Tim Grittani-style morning panic analysis over explicit tickers."""
    if not tickers:
        return {"error": "tickers is required and must be non-empty."}

    if service is None:
        from providers.alpaca_provider import AlpacaProvider
        from services.grittani_analysis_service import GrittaniAnalysisService

        service = GrittaniAnalysisService(provider=AlpacaProvider())

    rvol_by_ticker = rvol_by_ticker or {}
    signals = []
    errors = []
    for ticker in tickers:
        normalized = ticker.upper()
        try:
            signal = service.detect_morning_panic(
                normalized,
                rvol=rvol_by_ticker.get(normalized),
            )
            if signal is not None:
                signals.append(_grittani_panic_signal_to_dict(signal))
        except Exception as exc:
            errors.append(_grittani_panic_error_to_dict(normalized, exc))

    return {
        "ticker_count": len(tickers),
        "signal_count": len(signals),
        "signals": signals,
        "error_count": len(errors),
        "errors": errors,
        "notes": [
            "Morning panic levels are rule-derived scanner references, not execution advice.",
            "RVOL must come from an upstream data-layer scan; missing RVOL produces no signal.",
        ],
    }


def get_trader_context(
    *,
    ticker: str,
    trader_profile: str = "default",
    include_intraday: bool = False,
    include_daily: bool = False,
    refresh_catalysts: bool = False,
    service: Any | None = None,
) -> dict[str, Any]:
    """Return the shared data packet trader profiles should reason from."""
    if not ticker or not ticker.strip():
        return {"error": "ticker is required."}

    if service is None:
        bar_provider = None
        if include_intraday or include_daily:
            from providers.alpaca_provider import AlpacaProvider

            bar_provider = AlpacaProvider()

        from services.trader_context_service import TraderContextService

        service = TraderContextService(bar_provider=bar_provider)

    try:
        return service.build_context(
            ticker=ticker.strip().upper(),
            trader_profile=trader_profile,
            include_intraday=include_intraday,
            include_daily=include_daily,
            refresh_catalysts=refresh_catalysts,
        )
    except ValueError as exc:
        return {"error": str(exc)}


def explain_ticker_as_trader(
    *,
    ticker: str,
    trader_profile: str = "default",
    include_intraday: bool = False,
    include_daily: bool = False,
    refresh_catalysts: bool = False,
    service: Any | None = None,
) -> dict[str, Any]:
    """Build and format one ticker's context through a trader profile lens."""
    if not ticker or not ticker.strip():
        return {"error": "ticker is required."}

    if service is None:
        bar_provider = None
        if include_intraday or include_daily:
            from providers.alpaca_provider import AlpacaProvider

            bar_provider = AlpacaProvider()

        from services.trader_context_service import TraderContextService

        service = TraderContextService(bar_provider=bar_provider)

    try:
        context = service.build_context(
            ticker=ticker.strip().upper(),
            trader_profile=trader_profile,
            include_intraday=include_intraday,
            include_daily=include_daily,
            refresh_catalysts=refresh_catalysts,
        )
    except ValueError as exc:
        return {"error": str(exc)}

    from services.desk_explainer import build_trader_context_explanation

    return build_trader_context_explanation(context)


def run_desk(
    *,
    tickers: list[str] | str | None = None,
    universe: str | list[str] | None = None,
    watchlist: str | list[str] | None = None,
    all_universes: bool = False,
    market: str | None = None,
    market_limit: int | None = None,
    max_workers: int | None = None,
    scan_preset_name: str = "sykes_small_cap_v0",
    trader_profiles: list[str] | None = None,
    include_intraday: bool = False,
    include_daily: bool = False,
    refresh_catalysts: bool = False,
    service: Any | None = None,
) -> dict[str, Any]:
    """Run one grounded Desk packet across tickers and trader profiles."""
    normalized_tickers = _normalize_ticker_list(tickers)
    if not any([normalized_tickers, universe, watchlist, all_universes, market]):
        return {
            "error": "Provide at least one selection: tickers, universe, watchlist, market, or all_universes."
        }

    if service is None:
        from services.desk_run_service import DeskRunService

        service = DeskRunService()

    try:
        return service.run(
            tickers=normalized_tickers,
            universe=universe,
            watchlist=watchlist,
            all_universes=all_universes,
            market=market,
            market_limit=market_limit,
            max_workers=max_workers,
            scan_preset_name=scan_preset_name,
            trader_profiles=trader_profiles,
            include_intraday=include_intraday,
            include_daily=include_daily,
            refresh_catalysts=refresh_catalysts,
        )
    except ValueError as exc:
        return {"error": str(exc)}


def run_morning_brief(
    *,
    profile: str = "default",
    tickers: list[str] | str | None = None,
    universe: str | list[str] | None = None,
    watchlist: str | list[str] | None = None,
    all_universes: bool = False,
    market: str | None = None,
    market_limit: int | None = None,
    max_workers: int | None = None,
    scan_preset_name: str = "sykes_small_cap_v0",
    include_intraday: bool = False,
    include_daily: bool = False,
    refresh_catalysts: bool = False,
    save_journal: bool = True,
    service: Any | None = None,
) -> dict[str, Any]:
    """Run the morning brief orchestrator and return a grounded brief packet."""
    normalized_tickers = _normalize_ticker_list(tickers)
    if not any([normalized_tickers, universe, watchlist, all_universes, market]):
        return {
            "error": "Provide at least one selection: tickers, universe, watchlist, market, or all_universes."
        }

    if service is None:
        from services.morning_brief_service import MorningBriefService

        service = MorningBriefService()

    try:
        return service.run(
            profile=profile,
            tickers=normalized_tickers,
            universe=universe,
            watchlist=watchlist,
            all_universes=all_universes,
            market=market,
            market_limit=market_limit,
            max_workers=max_workers,
            scan_preset_name=scan_preset_name,
            include_intraday=include_intraday,
            include_daily=include_daily,
            refresh_catalysts=refresh_catalysts,
            save_journal=save_journal,
        )
    except ValueError as exc:
        return {"error": str(exc)}


def deep_dive_ticker(
    *,
    ticker: str,
    trader_profile: str = "default",
    include_intraday: bool = True,
    include_daily: bool = True,
    refresh_catalysts: bool = False,
    service: Any | None = None,
) -> dict[str, Any]:
    """Run the single-ticker deep dive orchestrator."""
    if not ticker or not ticker.strip():
        return {"error": "ticker is required."}

    if service is None:
        bar_provider = None
        if include_intraday or include_daily:
            from providers.alpaca_provider import AlpacaProvider

            bar_provider = AlpacaProvider()

        from services.deep_dive_service import DeepDiveService

        service = DeepDiveService(bar_provider=bar_provider)

    try:
        return service.run(
            ticker=ticker.strip().upper(),
            trader_profile=trader_profile,
            include_intraday=include_intraday,
            include_daily=include_daily,
            refresh_catalysts=refresh_catalysts,
        )
    except ValueError as exc:
        return {"error": str(exc)}


def _normalize_ticker_list(tickers: list[str] | str | None) -> list[str] | None:
    if tickers is None:
        return None
    if isinstance(tickers, str):
        raw = tickers.split(",")
    else:
        raw = tickers
    normalized: list[str] = []
    seen = set()
    for ticker in raw:
        value = str(ticker).strip().upper()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


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
        "data_status": snap.data_status,
        "provider_failures": dict(snap.provider_failures),
        "sources": snap.sources,
        "timestamp": snap.timestamp,
        "notes": snap.notes,
    }
