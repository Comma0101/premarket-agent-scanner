from __future__ import annotations

from app.models import ScannerResult, SmallCapCandidate, SmallCapGrade


UNUSABLE_CONFIDENCE = {
    "ERROR",
    "CONFLICT",
    "STALE_DATA",
    "MISSING_PREVIOUS_CLOSE",
    "MISSING_PREMARKET_PRICE",
}


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
