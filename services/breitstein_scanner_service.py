from __future__ import annotations

from typing import Protocol

from app.models import (
    BreitsteinCandidate,
    BreitsteinGrade,
    BreitsteinScanOutput,
    CAP_TIERS,
    ScannerResult,
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
    "MISSING_MARKET_CAP",
}

PREFERRED_CAP_TIERS = {"mid", "large", "mega"}
DEFAULT_WATCHLIST = "HOT_ACTIVE"


class BreitsteinEvidenceEnricher(Protocol):
    def enrich_candidates(
        self,
        candidates: list[BreitsteinCandidate],
    ) -> list[BreitsteinCandidate]:
        ...


class BreitsteinScannerService:
    def __init__(
        self,
        scanner_service: ScannerService | None = None,
        preset_service: PresetService | None = None,
        evidence_service: BreitsteinEvidenceEnricher | None = None,
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
        preset_name: str = "breitstein_mean_reversion_v0",
        universe: str | list[str] | None = None,
        watchlist: str | list[str] | None = None,
        tickers: list[str] | str | None = None,
        all_universes: bool = False,
        market: str | None = None,
        market_limit: int | None = None,
        max_workers: int | None = None,
    ) -> BreitsteinScanOutput:
        preset = self.preset_service.get_preset(preset_name)
        run_ids: list[str] = []
        notes = list(preset.notes)

        if not any([universe, watchlist, tickers, all_universes, market]):
            watchlist = DEFAULT_WATCHLIST

        if market:
            if any([universe, watchlist, tickers, all_universes]):
                raise ValueError(
                    "Use market by itself; do not combine it with "
                    "universe/watchlist/tickers/all."
                )
            market_universe = self._market_universe_provider().list_symbols(market)
            tickers = market_universe.symbols
            if market_limit is not None:
                limit = max(0, int(market_limit))
                tickers = tickers[:limit]
            notes.insert(
                0,
                (
                    f"Market universe {market} resolved "
                    f"{len(market_universe.symbols)} symbol(s) from "
                    f"{market_universe.source}."
                ),
            )
            notes[1:1] = list(market_universe.notes)
            if market_limit is not None:
                notes.insert(
                    1,
                    f"Limited market universe to {len(tickers)} symbol(s) for testing.",
                )

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

        candidates = [
            grade_breitstein_candidate(
                result,
                missing_fields=list(preset.missing_fields),
            )
            for result in scan_run.results
        ]
        candidates = [
            candidate for candidate in candidates if candidate.grade != "REJECT"
        ]

        if candidates:
            candidates = self.evidence_service.enrich_candidates(candidates)
            for candidate in candidates:
                _apply_evidence_signals(candidate)
            candidates = sorted(
                candidates,
                key=lambda candidate: candidate.score,
                reverse=True,
            )

        return BreitsteinScanOutput(
            preset=preset.name,
            run_ids=run_ids,
            candidate_count=len(candidates),
            candidates=candidates,
            notes=notes,
        )

    def _market_universe_provider(self):
        if self.market_universe_provider is not None:
            return self.market_universe_provider
        from providers.market_universe_provider import MarketUniverseProvider

        self.market_universe_provider = MarketUniverseProvider()
        return self.market_universe_provider


def grade_breitstein_candidate(
    result: ScannerResult,
    *,
    missing_fields: list[str],
    has_catalyst: bool | None = False,
    consecutive_days_direction: int | None = None,
) -> BreitsteinCandidate:
    score = 0
    matched: list[str] = []
    risk_notes: list[str] = []
    provided_missing_fields = list(missing_fields)
    cap_tier = _cap_tier_for_market_cap(result.market_cap)
    abnormal_move = _is_abnormal_move(result.gap_pct, cap_tier)
    abs_gap = abs(result.gap_pct) if result.gap_pct is not None else None

    if result.confidence in UNUSABLE_CONFIDENCE:
        matched.append("unusable_confidence")
        risk_notes.append(f"Rejected because confidence is {result.confidence}.")
        risk_notes.extend(_missing_field_notes(provided_missing_fields))
        return _candidate(
            result,
            0,
            "REJECT",
            cap_tier,
            abnormal_move,
            consecutive_days_direction,
            has_catalyst,
            matched,
            provided_missing_fields,
            risk_notes,
        )

    if abs_gap is None:
        matched.append("missing_gap")
        risk_notes.append("Gap is unknown; mean-reversion dislocation cannot be scored.")
        risk_notes.extend(_missing_field_notes(provided_missing_fields))
        return _candidate(
            result,
            0,
            "REJECT",
            cap_tier,
            abnormal_move,
            consecutive_days_direction,
            has_catalyst,
            matched,
            provided_missing_fields,
            risk_notes,
        )

    if abs_gap < 3 and (result.rel_volume is None or result.rel_volume < 2):
        matched.append("no_dislocation")
        risk_notes.append("Gap and relative volume are below Lance Phase 1 floors.")
        risk_notes.extend(_missing_field_notes(provided_missing_fields))
        return _candidate(
            result,
            0,
            "REJECT",
            cap_tier,
            abnormal_move,
            consecutive_days_direction,
            has_catalyst,
            matched,
            provided_missing_fields,
            risk_notes,
        )

    if abnormal_move:
        score += 25
        matched.append("abnormal_move")
    else:
        risk_notes.append(
            "Abnormal move is not confirmed by the Phase 1 gap proxy."
        )

    if result.rel_volume is not None and result.rel_volume >= 3:
        score += 20
        matched.append("high_rvol")
    else:
        risk_notes.append("Relative volume is weak or unknown.")

    score += 10
    matched.append("both_directions_enabled")

    if cap_tier in PREFERRED_CAP_TIERS:
        score += 15
        matched.append(f"{cap_tier}_cap_fit")
    else:
        risk_notes.append(
            "Market cap tier is outside preferred mid/large/mega Lance scope."
        )

    if result.confidence == "OK":
        score += 10
        matched.append("clean_confidence")
    else:
        risk_notes.append(f"Data confidence is {result.confidence}.")

    if has_catalyst:
        score += 10
        matched.append("fresh_catalyst_context")
    else:
        risk_notes.append(
            "Catalyst context is unknown; do not infer emotional dislocation."
        )

    if result.gap_pct < 0:
        score += 10
        matched.append("gap_down_flush")

    if result.gap_basis == "premarket":
        matched.append("premarket_gap_basis")
    elif result.gap_basis == "last_trade":
        matched.append("last_trade_gap_basis")
        risk_notes.append(
            "gap_basis=last_trade; this is not a confirmed premarket move."
        )
    elif result.gap_basis is None:
        risk_notes.append("gap_basis unknown; not a confirmed premarket move.")
    else:
        risk_notes.append(
            f"gap_basis={result.gap_basis}; not a confirmed premarket move."
        )

    risk_notes.extend(_missing_field_notes(provided_missing_fields))
    grade = _grade_with_gates(
        score,
        confidence=result.confidence,
        gap_basis=result.gap_basis,
        abnormal_move=abnormal_move,
        has_catalyst=bool(has_catalyst),
        cap_tier=cap_tier,
    )
    return _candidate(
        result,
        score,
        grade,
        cap_tier,
        abnormal_move,
        consecutive_days_direction,
        has_catalyst,
        matched,
        provided_missing_fields,
        risk_notes,
    )


def _apply_evidence_signals(candidate: BreitsteinCandidate) -> None:
    evidence = candidate.evidence
    if evidence is None:
        candidate.grade = _grade_with_gates(
            candidate.score,
            confidence=candidate.confidence,
            gap_basis=candidate.gap_basis,
            abnormal_move=bool(candidate.abnormal_move),
            has_catalyst=bool(candidate.has_catalyst),
            cap_tier=candidate.cap_tier,
        )
        return

    has_catalyst = bool(evidence.catalysts or evidence.filings)
    candidate.has_catalyst = has_catalyst
    candidate.missing_fields = list(evidence.missing_fields)
    candidate.risk_notes.extend(
        note for note in evidence.risk_notes if note not in candidate.risk_notes
    )
    for source in evidence.sources:
        _append_unique(candidate.sources, source)

    if has_catalyst and "fresh_catalyst_context" not in candidate.matched_signals:
        candidate.score += 10
        candidate.matched_signals.append("fresh_catalyst_context")

    candidate.grade = _grade_with_gates(
        candidate.score,
        confidence=candidate.confidence,
        gap_basis=candidate.gap_basis,
        abnormal_move=bool(candidate.abnormal_move),
        has_catalyst=has_catalyst,
        cap_tier=candidate.cap_tier,
    )


def _candidate(
    result: ScannerResult,
    score: int,
    grade: BreitsteinGrade,
    cap_tier: str | None,
    abnormal_move: bool | None,
    consecutive_days_direction: int | None,
    has_catalyst: bool | None,
    matched_signals: list[str],
    missing_fields: list[str],
    risk_notes: list[str],
) -> BreitsteinCandidate:
    return BreitsteinCandidate(
        ticker=result.ticker,
        name=result.name,
        market_cap=result.market_cap,
        gap_pct=result.gap_pct,
        gap_dollar=result.gap_dollar,
        volume=result.volume,
        rel_volume=result.rel_volume,
        confidence=result.confidence,
        gap_basis=result.gap_basis,
        cap_tier=cap_tier,
        abnormal_move=abnormal_move,
        consecutive_days_direction=consecutive_days_direction,
        has_catalyst=has_catalyst,
        score=score,
        grade=grade,
        matched_signals=list(matched_signals),
        missing_fields=list(missing_fields),
        risk_notes=list(risk_notes),
        sources=list(result.sources),
        timestamp=result.timestamp,
    )


def _grade_with_gates(
    score: int,
    *,
    confidence: str,
    gap_basis: str | None,
    abnormal_move: bool,
    has_catalyst: bool,
    cap_tier: str | None,
) -> BreitsteinGrade:
    grade = _score_grade(score)
    if grade == "A_WATCH" and (confidence != "OK" or gap_basis != "premarket"):
        grade = "B_WATCH"
    if grade == "A_WATCH" and (not has_catalyst and not abnormal_move):
        grade = "B_WATCH"
    if grade == "A_WATCH" and cap_tier not in PREFERRED_CAP_TIERS:
        grade = "B_WATCH"
    return grade


def _score_grade(score: int) -> BreitsteinGrade:
    if score >= 75:
        return "A_WATCH"
    if score >= 55:
        return "B_WATCH"
    if score >= 35:
        return "C_WATCH"
    return "REJECT"


def _is_abnormal_move(gap_pct: float | None, cap_tier: str | None) -> bool | None:
    if gap_pct is None:
        return None
    threshold = 3.0 if cap_tier in {"large", "mega"} else 5.0
    return abs(gap_pct) >= threshold


def _cap_tier_for_market_cap(market_cap: float | None) -> str | None:
    if market_cap is None:
        return None
    for name, (lower, upper) in CAP_TIERS.items():
        if market_cap >= lower and (upper is None or market_cap < upper):
            return name
    return None


def _union_cap_bounds(cap_tiers: list[str]) -> tuple[float, float | None]:
    lows: list[float] = []
    highs: list[float] = []
    for tier in cap_tiers:
        low, high = resolve_cap_tier(tier)
        lows.append(low or 0.0)
        highs.append(float("inf") if high is None else high)

    upper = max(highs)
    return min(lows), (None if upper == float("inf") else upper)


def _missing_field_notes(missing_fields: list[str]) -> list[str]:
    return [
        f"{field} is unknown; do not infer it from price or volume."
        for field in missing_fields
    ]


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
