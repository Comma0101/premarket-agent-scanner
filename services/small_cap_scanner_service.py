from __future__ import annotations

from typing import Protocol

from app.models import (
    ScannerResult,
    SmallCapCandidate,
    SmallCapGrade,
    SmallCapScanOutput,
    make_scan_filters,
    resolve_cap_tier,
)
from services.scanner_preset_service import PresetService
from services.scanner_service import ScannerService
from services.small_cap_evidence_service import SmallCapEvidenceService


UNUSABLE_CONFIDENCE = {
    "ERROR",
    "CONFLICT",
    "STALE_DATA",
    "MISSING_PREVIOUS_CLOSE",
    "MISSING_PREMARKET_PRICE",
}


class SmallCapEvidenceEnricher(Protocol):
    def enrich_candidates(
        self,
        candidates: list[SmallCapCandidate],
    ) -> list[SmallCapCandidate]:
        ...


class SmallCapScannerService:
    def __init__(
        self,
        scanner_service: ScannerService | None = None,
        preset_service: PresetService | None = None,
        evidence_service: SmallCapEvidenceEnricher | None = None,
        market_universe_provider: object | None = None,
    ) -> None:
        self.scanner_service = scanner_service or ScannerService()
        self.preset_service = preset_service or PresetService()
        self.evidence_service = (
            evidence_service
            if evidence_service is not None
            else SmallCapEvidenceService()
        )
        self.market_universe_provider = market_universe_provider

    def scan(
        self,
        *,
        preset_name: str = "sykes_small_cap_v0",
        universe: str | list[str] | None = None,
        watchlist: str | list[str] | None = None,
        tickers: list[str] | str | None = None,
        all_universes: bool = False,
        market: str | None = None,
        market_limit: int | None = None,
        max_workers: int | None = None,
        include_rejected: bool = False,
    ) -> SmallCapScanOutput:
        preset = self.preset_service.get_preset(preset_name)
        run_ids: list[str] = []
        notes = list(preset.notes)
        candidates_by_ticker: dict[str, SmallCapCandidate] = {}
        rejected_by_ticker: dict[str, SmallCapCandidate] = {}
        if market:
            if any([universe, watchlist, tickers, all_universes]):
                raise ValueError("Use market by itself; do not combine it with universe/watchlist/tickers/all.")
            market_universe = self._market_universe_provider().list_symbols(market)
            tickers = market_universe.symbols
            if market_limit is not None:
                limit = max(0, int(market_limit))
                tickers = tickers[:limit]
            notes.insert(
                0,
                (
                    f"Market universe {market} resolved {len(market_universe.symbols)} "
                    f"symbol(s) from {market_universe.source}."
                ),
            )
            notes[1:1] = list(market_universe.notes)
            if market_limit is not None:
                notes.insert(1, f"Limited market universe to {len(tickers)} symbol(s) for testing.")

        min_market_cap, max_market_cap = _union_cap_bounds(preset.cap_tiers)
        filters = make_scan_filters(
            min_market_cap=min_market_cap,
            max_market_cap=max_market_cap,
            min_gap_abs=preset.min_gap_abs,
            direction=preset.direction,
            min_volume=preset.min_volume,
            min_rel_volume=preset.min_rel_volume,
            include_low_confidence=preset.include_low_confidence,
        )
        scan_run = self.scanner_service.scan(
            universe=universe,
            watchlist=watchlist,
            tickers=tickers,
            all_universes=all_universes,
            filters=filters,
            max_workers=max_workers or 1,
        )
        run_ids.append(scan_run.run_id)
        notes.extend(scan_run.notes)

        for result in scan_run.results:
            candidate = grade_small_cap_candidate(
                result,
                missing_fields=list(preset.missing_fields),
            )
            if candidate.grade == "REJECT":
                existing_rejected = rejected_by_ticker.get(candidate.ticker)
                if existing_rejected is None or candidate.score > existing_rejected.score:
                    rejected_by_ticker[candidate.ticker] = candidate
                continue

            existing = candidates_by_ticker.get(candidate.ticker)
            if existing is None or candidate.score > existing.score:
                candidates_by_ticker[candidate.ticker] = candidate

        rejected = sorted(
            rejected_by_ticker.values(),
            key=lambda candidate: (-candidate.score, candidate.ticker),
        )
        candidates = sorted(
            candidates_by_ticker.values(),
            key=lambda candidate: candidate.score,
            reverse=True,
        )
        if candidates:
            candidates = self.evidence_service.enrich_candidates(candidates)
            for candidate in candidates:
                _apply_float_signals(candidate)
                _apply_catalyst_signals(candidate)
            candidates = sorted(
                candidates,
                key=lambda candidate: candidate.score,
                reverse=True,
            )
        zero_result_reason = None
        relax_suggestions: list[str] = []
        if not candidates:
            zero_result_reason, relax_suggestions = _empty_state_guidance(
                scan_results=scan_run.results,
                rejected=rejected,
            )
        return SmallCapScanOutput(
            preset=preset.name,
            run_ids=run_ids,
            candidate_count=len(candidates),
            candidates=candidates,
            notes=notes,
            rejected_count=len(rejected) if include_rejected else 0,
            rejected=rejected if include_rejected else [],
            zero_result_reason=zero_result_reason,
            relax_suggestions=relax_suggestions,
        )

    def _market_universe_provider(self):
        if self.market_universe_provider is not None:
            return self.market_universe_provider
        from providers.market_universe_provider import MarketUniverseProvider

        self.market_universe_provider = MarketUniverseProvider()
        return self.market_universe_provider


def _union_cap_bounds(cap_tiers: list[str]) -> tuple[float, float | None]:
    lows: list[float] = []
    highs: list[float] = []
    for tier in cap_tiers:
        low, high = resolve_cap_tier(tier)
        lows.append(low or 0.0)
        highs.append(float("inf") if high is None else high)

    upper = max(highs)
    return min(lows), (None if upper == float("inf") else upper)


def _empty_state_guidance(
    *,
    scan_results: list[ScannerResult],
    rejected: list[SmallCapCandidate],
) -> tuple[str, list[str]]:
    suggestions = [
        "Review rejected rows with include_rejected=True to see which filter dropped each name.",
        "Check missing_fields before relaxing scanner thresholds.",
    ]
    if not scan_results and not rejected:
        suggestions.append(
            "If the preset is too narrow, lower min_gap_abs or min_rel_volume before re-running."
        )
        return "all_filtered", suggestions

    data_quality_drops = sum(
        1
        for candidate in rejected
        if "unusable_confidence" in candidate.matched_signals
        or any(
            note.startswith("Rejected because confidence is")
            for note in candidate.risk_notes
        )
    )
    if rejected and data_quality_drops >= len(rejected):
        suggestions.append(
            "Run during PRE_MARKET for premarket gap_basis eligibility; "
            "last_trade quotes rarely carry a clean confidence label."
        )
        return "all_failed_data_quality", suggestions

    suggestions.append(
        "If the preset is too narrow, lower min_gap_abs or min_rel_volume before re-running."
    )
    return "all_filtered", suggestions


def grade_small_cap_candidate(
    result: ScannerResult,
    *,
    missing_fields: list[str],
) -> SmallCapCandidate:
    score = 0
    matched: list[str] = []
    risk_notes: list[str] = []
    provided_missing_fields = list(missing_fields)
    has_absolute_volume_floor = False

    if result.halt_status is not None and result.halt_status.is_active:
        matched.append("active_halt")
        code = f" ({result.halt_status.reason_code})" if result.halt_status.reason_code else ""
        risk_notes.append(f"Active trading halt{code}; verify halt/resume status before acting.")
        risk_notes.extend(_missing_field_notes(provided_missing_fields))
        return _candidate(
            result,
            0,
            "REJECT",
            matched,
            provided_missing_fields,
            risk_notes,
        )

    if result.confidence in UNUSABLE_CONFIDENCE:
        matched.append("unusable_confidence")
        risk_notes.append(f"Rejected because confidence is {result.confidence}.")
        risk_notes.extend(_missing_field_notes(provided_missing_fields))
        return _candidate(
            result,
            0,
            "REJECT",
            matched,
            provided_missing_fields,
            risk_notes,
        )

    if result.gap_pct is None or result.gap_pct <= 0:
        matched.append("no_positive_gap")
        risk_notes.append("No positive gap.")
        risk_notes.extend(_missing_field_notes(provided_missing_fields))
        return _candidate(
            result,
            0,
            "REJECT",
            matched,
            provided_missing_fields,
            risk_notes,
        )

    if result.market_cap is None:
        matched.append("missing_market_cap")
        risk_notes.append("Market cap is unknown, so small-cap fit cannot be confirmed.")
    elif result.market_cap <= 2_000_000_000:
        score += 20
        matched.append("small_cap_fit")
    else:
        matched.append("too_large")
        risk_notes.append("Market cap is outside small-cap scope.")
        risk_notes.extend(_missing_field_notes(provided_missing_fields))
        return _candidate(
            result,
            0,
            "REJECT",
            matched,
            provided_missing_fields,
            risk_notes,
        )

    if result.gap_pct >= 10:
        score += 25
        matched.append("strong_gap")
    elif result.gap_pct >= 5:
        score += 15
        matched.append("gap_up")

    if result.gap_basis == "premarket":
        matched.append("premarket_gap_basis")
    elif result.gap_basis == "last_trade":
        matched.append("last_trade_gap_basis")
        risk_notes.append(
            "gap_basis=last_trade; last regular/last trade, not a premarket quote."
        )
    elif result.gap_basis is None:
        risk_notes.append("gap_basis unknown; not a confirmed premarket move.")
    else:
        risk_notes.append(
            f"gap_basis={result.gap_basis}; not a confirmed premarket move."
        )

    if result.rel_volume is not None and result.rel_volume >= 3:
        score += 25
        matched.append("high_rvol")
    elif result.rel_volume is not None and result.rel_volume >= 2:
        score += 15
        matched.append("rvol_confirmed")
    else:
        risk_notes.append("Relative volume is weak or unknown.")

    if result.volume is not None and result.volume >= 1_000_000:
        score += 20
        matched.append("liquid_volume")
        has_absolute_volume_floor = True
    elif result.volume is not None and result.volume >= 500_000:
        score += 10
        matched.append("minimum_volume")
        has_absolute_volume_floor = True
    else:
        risk_notes.append("Volume is below the preferred small-cap scanner floor or unknown.")

    if result.confidence == "OK":
        score += 10
        matched.append("clean_confidence")
    else:
        risk_notes.append(f"Data confidence is {result.confidence}.")

    risk_notes.extend(_missing_field_notes(provided_missing_fields))
    grade = _grade(
        score,
        provided_missing_fields,
        has_absolute_volume_floor=has_absolute_volume_floor,
        gap_basis=result.gap_basis,
    )
    return _candidate(result, score, grade, matched, provided_missing_fields, risk_notes)


def _missing_field_notes(missing_fields: list[str]) -> list[str]:
    return [
        f"{field} is unknown; do not infer it from price or volume."
        for field in missing_fields
    ]


def _grade(
    score: int,
    missing_fields: list[str],
    *,
    has_absolute_volume_floor: bool,
    gap_basis: str | None,
) -> SmallCapGrade:
    if score >= 80 and len(missing_fields) <= 6 and has_absolute_volume_floor:
        if gap_basis is not None and gap_basis != "premarket":
            return "B_WATCH"
        return "A_WATCH"
    if score >= 60:
        return "B_WATCH"
    if score >= 35:
        return "C_WATCH"
    return "REJECT"


def _apply_float_signals(candidate: SmallCapCandidate) -> None:
    evidence = candidate.evidence
    if evidence is None:
        return

    # These are pragmatic scanner weights, not a claim of an exact trader formula.
    if evidence.is_low_float is True:
        _add_signal_score(candidate, "low_float_fit", 10)

    rotation = evidence.float_rotation
    if rotation is not None:
        if rotation >= 1.0:
            _add_signal_score(candidate, "full_float_rotation", 15)
        elif rotation >= 0.5:
            _add_signal_score(candidate, "high_float_rotation", 8)

    candidate.missing_fields = list(evidence.missing_fields)
    candidate.grade = _grade(
        candidate.score,
        candidate.missing_fields,
        has_absolute_volume_floor=_has_absolute_volume_floor(candidate),
        gap_basis=candidate.gap_basis,
    )


def _apply_catalyst_signals(candidate: SmallCapCandidate) -> None:
    evidence = candidate.evidence
    if evidence is None:
        return

    catalysts = list(evidence.catalysts)
    if not catalysts:
        if candidate.grade == "A_WATCH":
            candidate.grade = "B_WATCH"
            _append_unique(
                candidate.risk_notes,
                "No verified catalyst; A_WATCH is capped until catalyst is sourced.",
            )
        return

    for catalyst in catalysts:
        quality = (catalyst.catalyst_quality or "").lower()
        if quality == "hard" and _is_fresh_catalyst(catalyst.recency_minutes):
            _add_signal_score(candidate, "fresh_hard_catalyst", 15)
            break
        if quality == "soft":
            _add_signal_score(candidate, "soft_catalyst", 5)
            break

    candidate.missing_fields = list(evidence.missing_fields)
    candidate.grade = _grade(
        candidate.score,
        candidate.missing_fields,
        has_absolute_volume_floor=_has_absolute_volume_floor(candidate),
        gap_basis=candidate.gap_basis,
    )


def _is_fresh_catalyst(recency_minutes: float | None) -> bool:
    return recency_minutes is None or recency_minutes <= 120


def _add_signal_score(
    candidate: SmallCapCandidate,
    signal: str,
    points: int,
) -> None:
    if signal in candidate.matched_signals:
        return
    candidate.matched_signals.append(signal)
    candidate.score += points


def _has_absolute_volume_floor(candidate: SmallCapCandidate) -> bool:
    return candidate.volume is not None and candidate.volume >= 500_000


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _candidate(
    result: ScannerResult,
    score: int,
    grade: SmallCapGrade,
    matched: list[str],
    missing_fields: list[str],
    risk_notes: list[str],
) -> SmallCapCandidate:
    return SmallCapCandidate(
        ticker=result.ticker,
        name=result.name,
        market_cap=result.market_cap,
        gap_pct=result.gap_pct,
        gap_dollar=result.gap_dollar,
        volume=result.volume,
        rel_volume=result.rel_volume,
        confidence=result.confidence,
        score=score,
        grade=grade,
        gap_basis=result.gap_basis,
        matched_signals=matched,
        missing_fields=missing_fields,
        risk_notes=risk_notes,
        sources=list(result.sources),
        timestamp=result.timestamp,
        halt_status=result.halt_status,
    )
