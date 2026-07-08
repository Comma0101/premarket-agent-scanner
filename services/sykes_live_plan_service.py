from __future__ import annotations

from typing import Any

from app.models import SmallCapCandidate, SmallCapEvidence
from services.session_time_service import data_caveat_for, format_et, session_banner_for, session_mode_for
from services.small_cap_scanner_service import SmallCapScannerService


DISCLAIMER = "Matches your filter - not buy/sell advice. Verify before acting."


class SykesLivePlanService:
    """Read-only Tim Sykes-style live/swing watch packaging."""

    def __init__(self, *, scanner_service: Any | None = None) -> None:
        self.scanner_service = scanner_service or SmallCapScannerService()

    def run(
        self,
        *,
        tickers: list[str] | str | None = None,
        universe: str | list[str] | None = None,
        watchlist: str | list[str] | None = None,
        market: str | None = "us-listed",
        market_limit: int | None = None,
        max_workers: int | None = None,
        include_rejected: bool = False,
        live_intraday: bool = True,
        summary_limit: int = 10,
    ) -> dict[str, Any]:
        if any([tickers, universe, watchlist]):
            market = None

        scan = self.scanner_service.scan(
            preset_name="sykes_small_cap_v0",
            tickers=tickers,
            universe=universe,
            watchlist=watchlist,
            market=market,
            market_limit=market_limit,
            max_workers=max_workers,
            include_rejected=include_rejected,
            live_intraday=live_intraday,
        )

        rows = [_row(candidate) for candidate in scan.candidates]
        rejected = [_row(candidate) for candidate in getattr(scan, "rejected", []) or []]
        blocked = [row for row in [*rows, *rejected] if row["state"] == "blocked_data_quality"]
        intraday = [row for row in rows if row["state"] != "blocked_data_quality"]
        swing = [_swing_row(row) for row in rows if row.get("swing_state")]
        limit = max(0, int(summary_limit))

        return {
            "agent_name": "timothy_sykes",
            "mode": "live_and_swing",
            "strategy": "Sykes-style small-cap live and swing watchlist",
            "status": "OK",
            "session_banner": session_banner_for(_latest_timestamp([*rows, *rejected])),
            "desk_read": {
                "one_liner": (
                    f"{len(intraday)} intraday watch, {len(swing)} swing watch, "
                    f"{len(blocked)} blocked."
                )
            },
            "intraday_watchlist": intraday[:limit],
            "swing_watchlist": swing[:limit],
            "blocked": blocked[:limit],
            "auto_slices": _auto_slices([*intraday, *swing, *blocked], limit=limit),
            "scanner": {
                "preset": scan.preset,
                "run_ids": list(scan.run_ids),
                "candidate_count": scan.candidate_count,
                "rejected_count": getattr(scan, "rejected_count", 0),
                "live_intraday": live_intraday,
                "notes": list(scan.notes),
            },
            "disclaimer": DISCLAIMER,
        }


def _row(candidate: SmallCapCandidate) -> dict[str, Any]:
    blocked = candidate.grade == "REJECT" or candidate.confidence != "OK"
    setup = _setup(candidate)
    swing_setup = _swing_setup(candidate)
    state = "blocked_data_quality" if blocked else _intraday_state(candidate)
    return {
        "ticker": candidate.ticker,
        "name": candidate.name,
        "state": state,
        "setup": setup if not blocked else "none",
        "swing_state": None if blocked or swing_setup == "none" else "next_session_watch",
        "swing_setup": swing_setup if not blocked else "none",
        "grade": candidate.grade,
        "score": candidate.score,
        "data_quality": _data_quality(candidate),
        "evidence": _evidence(candidate.evidence),
        "matched_signals": list(candidate.matched_signals),
        "missing_fields": _missing_fields(candidate),
        "risk_notes": list(candidate.risk_notes),
        "why": _why(candidate, setup, blocked),
        "watch": _watch(candidate, setup, blocked),
        "invalidates_if": _invalidates_if(candidate, blocked),
    }


def _swing_row(row: dict[str, Any]) -> dict[str, Any]:
    output = dict(row)
    output["state"] = row.get("swing_state")
    output["setup"] = row.get("swing_setup")
    return output


def _intraday_state(candidate: SmallCapCandidate) -> str:
    if candidate.grade == "A_WATCH":
        return "primary_live_watch"
    if candidate.grade == "B_WATCH":
        return "secondary_live_watch"
    return "context_watch"


def _setup(candidate: SmallCapCandidate) -> str:
    signals = set(candidate.matched_signals)
    if signals & {"fresh_hard_catalyst", "soft_catalyst"}:
        return "catalyst_spiker_watch"
    if "former_runner_context" in signals:
        return "former_runner_reactivation_watch"
    if signals & {"low_float_fit", "full_float_rotation", "high_float_rotation"}:
        return "low_float_spiker_watch"
    if signals & {"strong_gap", "high_rvol"}:
        return "high_rvol_gap_watch"
    return "small_cap_gap_watch"


def _swing_setup(candidate: SmallCapCandidate) -> str:
    signals = set(candidate.matched_signals)
    if "former_runner_context" in signals:
        return "former_runner_reactivation_watch"
    if signals & {"fresh_hard_catalyst", "soft_catalyst"}:
        return "catalyst_continuation_watch"
    if signals & {"low_float_fit", "full_float_rotation"}:
        return "low_float_continuation_watch"
    return "none"


def _data_quality(candidate: SmallCapCandidate) -> dict[str, Any]:
    timestamp = candidate.timestamp
    return {
        "market_cap": candidate.market_cap,
        "gap_pct": candidate.gap_pct,
        "gap_dollar": candidate.gap_dollar,
        "gap_basis": candidate.gap_basis,
        "volume": candidate.volume,
        "rel_volume": candidate.rel_volume,
        "rel_volume_basis": candidate.rel_volume_basis,
        "confidence": candidate.confidence,
        "as_of_utc": timestamp,
        "as_of_et": format_et(timestamp),
        "session_mode": session_mode_for(timestamp),
        "data_caveat": data_caveat_for(
            timestamp,
            gap_basis=candidate.gap_basis,
            confidence=candidate.confidence,
        ),
        "sources": list(candidate.sources),
    }


def _evidence(evidence: SmallCapEvidence | None) -> dict[str, Any]:
    if evidence is None:
        return {
            "float_shares": None,
            "is_low_float": None,
            "float_rotation": None,
            "catalyst_count": 0,
            "filing_risk_tags": [],
            "former_runner": False,
            "sources": [],
        }
    return {
        "float_shares": evidence.float_shares,
        "is_low_float": evidence.is_low_float,
        "float_rotation": evidence.float_rotation,
        "catalyst_count": len(evidence.catalysts),
        "filing_risk_tags": _filing_risk_tags(evidence),
        "former_runner": evidence.former_runner is not None,
        "sources": list(evidence.sources),
    }


def _filing_risk_tags(evidence: SmallCapEvidence) -> list[str]:
    tags: list[str] = []
    for filing in evidence.filings:
        for tag in filing.risk_tags:
            if tag not in tags:
                tags.append(tag)
    return tags


def _missing_fields(candidate: SmallCapCandidate) -> list[str]:
    if candidate.evidence is not None:
        return list(candidate.evidence.missing_fields)
    return list(candidate.missing_fields)


def _why(candidate: SmallCapCandidate, setup: str, blocked: bool) -> str:
    if blocked:
        return f"{candidate.ticker} is blocked by data quality or rejection notes."
    return (
        f"{candidate.ticker} fits {setup}: grade={candidate.grade}, "
        f"score={candidate.score}, gap={_value(candidate.gap_pct)}%, "
        f"rvol={_value(candidate.rel_volume)}x."
    )


def _watch(candidate: SmallCapCandidate, setup: str, blocked: bool) -> str:
    if blocked:
        return "Fix data quality before treating this as a Tim watch."
    if setup == "catalyst_spiker_watch":
        return "Verify catalyst freshness, float, filings, liquidity, then manually review chart."
    if setup == "former_runner_reactivation_watch":
        return "Verify prior runner history and current catalyst before upgrading."
    return "Manual chart review; do not chase weak liquidity or missing evidence."


def _invalidates_if(candidate: SmallCapCandidate, blocked: bool) -> list[str]:
    if blocked:
        return ["confidence is not OK", "required setup evidence is missing"]
    risks = ["volume/RVOL fades", "data confidence deteriorates"]
    if "filings" in _missing_fields(candidate):
        risks.append("filing/dilution risk remains unknown")
    if candidate.evidence is not None and _filing_risk_tags(candidate.evidence):
        risks.append("fresh offering/dilution risk is present")
    return risks


def _auto_slices(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    slices = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        lane = "swing" if row.get("swing_state") and row["state"] != "blocked_data_quality" else "intraday"
        if row["state"] == "blocked_data_quality":
            lane = "blocked"
        key = (row["ticker"], lane)
        if key in seen:
            continue
        seen.add(key)
        slices.append({
            "ticker": row["ticker"],
            "lane": lane,
            "state": row.get("swing_state") if lane == "swing" else row["state"],
            "setup": row.get("swing_setup") if lane == "swing" else row["setup"],
            "data": _data_line(row["data_quality"]),
            "why": row["why"],
            "watch": row["watch"],
            "risk": "; ".join(row["invalidates_if"][:3]),
        })
        if len(slices) >= limit:
            break
    return slices


def _data_line(data: dict[str, Any]) -> str:
    return (
        f"gap={_value(data.get('gap_pct'))}% "
        f"rvol={_value(data.get('rel_volume'))}x "
        f"basis={_value(data.get('gap_basis'))} "
        f"confidence={_value(data.get('confidence'))} "
        f"as_of={_value(data.get('as_of_et'))}"
    )


def _latest_timestamp(rows: list[dict[str, Any]]) -> str | None:
    latest = None
    for row in rows:
        timestamp = (row.get("data_quality") or {}).get("as_of_utc")
        if isinstance(timestamp, str) and (latest is None or timestamp > latest):
            latest = timestamp
    return latest


def _value(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)
