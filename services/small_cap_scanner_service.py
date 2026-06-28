from __future__ import annotations

from app.models import (
    ScannerResult,
    SmallCapCandidate,
    SmallCapGrade,
    SmallCapScanOutput,
    make_scan_filters,
)
from services.scanner_preset_service import PresetService
from services.scanner_service import ScannerService


UNUSABLE_CONFIDENCE = {
    "ERROR",
    "CONFLICT",
    "STALE_DATA",
    "MISSING_PREVIOUS_CLOSE",
    "MISSING_PREMARKET_PRICE",
}


class SmallCapScannerService:
    def __init__(
        self,
        scanner_service: ScannerService | None = None,
        preset_service: PresetService | None = None,
    ) -> None:
        self.scanner_service = scanner_service or ScannerService()
        self.preset_service = preset_service or PresetService()

    def scan(
        self,
        *,
        preset_name: str = "sykes_small_cap_v0",
        universe: str | list[str] | None = None,
        watchlist: str | list[str] | None = None,
        tickers: list[str] | str | None = None,
        all_universes: bool = False,
    ) -> SmallCapScanOutput:
        preset = self.preset_service.get_preset(preset_name)
        run_ids: list[str] = []
        notes = list(preset.notes)
        candidates_by_ticker: dict[str, SmallCapCandidate] = {}

        for cap_tier in preset.cap_tiers:
            filters = make_scan_filters(
                cap_tier=cap_tier,
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
            )
            run_ids.append(scan_run.run_id)
            notes.extend(scan_run.notes)

            for result in scan_run.results:
                candidate = grade_small_cap_candidate(
                    result,
                    missing_fields=list(preset.missing_fields),
                )
                if candidate.grade == "REJECT":
                    continue

                existing = candidates_by_ticker.get(candidate.ticker)
                if existing is None or candidate.score > existing.score:
                    candidates_by_ticker[candidate.ticker] = candidate

        candidates = sorted(
            candidates_by_ticker.values(),
            key=lambda candidate: candidate.score,
            reverse=True,
        )
        return SmallCapScanOutput(
            preset=preset.name,
            run_ids=run_ids,
            candidate_count=len(candidates),
            candidates=candidates,
            notes=notes,
        )


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
) -> SmallCapGrade:
    if score >= 80 and len(missing_fields) <= 6 and has_absolute_volume_floor:
        return "A_WATCH"
    if score >= 60:
        return "B_WATCH"
    if score >= 35:
        return "C_WATCH"
    return "REJECT"


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
        matched_signals=matched,
        missing_fields=missing_fields,
        risk_notes=risk_notes,
        sources=list(result.sources),
        timestamp=result.timestamp,
    )
