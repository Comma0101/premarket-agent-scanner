from __future__ import annotations

from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo


DISCLAIMER = "Matches your filter — not buy/sell advice. Verify before acting."
NY_TZ = ZoneInfo("America/New_York")


def build_breitstein_ticker_explanation(
    *,
    snapshot: dict[str, Any],
    scan_output: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(snapshot.get("ticker") or "").upper()
    candidate = _candidate_for_ticker(scan_output, ticker)
    data_card = _data_card(snapshot)
    setup_stack = _setup_stack(snapshot, candidate)
    next_needed = _next_needed(snapshot, candidate)
    moment_state = _moment_state(snapshot, candidate)

    return {
        "ticker": ticker,
        "trader": "lance_breitstein",
        "lens": "mean_reversion_after_capitulation",
        "verdict": _verdict(candidate),
        "moment_state": moment_state,
        "data_card": data_card,
        "setup_stack": setup_stack,
        "moment_path": _moment_path(snapshot, candidate),
        "what_we_lack": _what_we_lack(snapshot, candidate),
        "next_needed": next_needed,
        "candidate": candidate,
        "notes": list(scan_output.get("notes") or []),
        "disclaimer": DISCLAIMER,
    }


def _data_card(snapshot: dict[str, Any]) -> dict[str, Any]:
    sources = snapshot.get("sources") or []
    source = ", ".join(str(source) for source in sources) if sources else "unknown"
    return {
        "source": source,
        "as_of": snapshot.get("timestamp"),
        "session": _ny_session_label(snapshot.get("timestamp")),
        "price_read": snapshot.get("gap_basis") or "unknown",
        "previous_close": snapshot.get("previous_close"),
        "premarket_price": snapshot.get("premarket_price"),
        "latest_price": snapshot.get("latest_price"),
        "gap_pct": snapshot.get("gap_pct"),
        "gap_dollar": snapshot.get("gap_dollar"),
        "volume": snapshot.get("volume"),
        "rel_volume": snapshot.get("rel_volume"),
        "market_cap": snapshot.get("market_cap"),
        "gap_basis": snapshot.get("gap_basis"),
        "confidence": snapshot.get("confidence"),
    }


def _setup_stack(
    snapshot: dict[str, Any],
    candidate: dict[str, Any] | None,
) -> list[dict[str, str]]:
    return [
        _check(
            "Universe fit",
            _universe_fit_status(snapshot, candidate),
            _universe_fit_detail(snapshot, candidate),
        ),
        _check("Move size", _move_status(snapshot), _move_detail(snapshot)),
        _check(
            "Participation",
            _participation_status(snapshot),
            _participation_detail(snapshot),
        ),
        _check(
            "Premarket data quality",
            _data_quality_status(snapshot),
            _data_quality_detail(snapshot),
        ),
        _check(
            "Catalyst context",
            "PASS" if _candidate_has_catalyst(candidate) else "UNKNOWN",
            (
                "Fresh catalyst context is present in scanner evidence."
                if _candidate_has_catalyst(candidate)
                else "Catalyst classification is unavailable; do not infer emotional dislocation."
            ),
        ),
        _check(
            "Intraday trigger",
            "UNKNOWN",
            "Requires 2-minute bars, VWAP, and prior-bar break confirmation.",
        ),
    ]


def _moment_path(
    snapshot: dict[str, Any],
    candidate: dict[str, Any] | None,
) -> list[dict[str, str]]:
    return [
        _moment(
            "Premarket",
            "ready" if _data_quality_status(snapshot) == "PASS" else "blocked",
            (
                "Valid premarket quote and OK confidence are present."
                if _data_quality_status(snapshot) == "PASS"
                else "Needs a real premarket quote with OK confidence."
            ),
        ),
        _moment(
            "Open",
            "waiting",
            "Check whether panic/euphoria volume expands versus the prior 2-minute bar.",
        ),
        _moment(
            "Turn",
            "waiting",
            "Valid only after a prior 2-minute high/low break on the right side of the move.",
        ),
        _moment(
            "Invalidation",
            "defined" if candidate else "pending",
            (
                "Phase 2 must define stop from prior 2-minute bar high/low."
                if candidate
                else "No setup yet; invalidation is data-quality, low participation, or no catalyst."
            ),
        ),
    ]


def _what_we_lack(
    snapshot: dict[str, Any],
    candidate: dict[str, Any] | None,
) -> list[str]:
    missing: list[str] = []
    if snapshot.get("gap_basis") != "premarket" or snapshot.get("confidence") != "OK":
        missing.append("live premarket-quality data")
    if not _candidate_has_catalyst(candidate):
        missing.append("fresh catalyst classification")
    missing.append("2-minute bars")
    missing.append("VWAP")
    missing.append("prior 2-minute high/low trigger")
    missing.append("order-flow/footprint context")
    return missing


def _next_needed(
    snapshot: dict[str, Any],
    candidate: dict[str, Any] | None,
) -> list[str]:
    needed: list[str] = []
    if snapshot.get("gap_basis") != "premarket" or snapshot.get("confidence") != "OK":
        needed.append("Fresh premarket quote")
    if _participation_status(snapshot) != "PASS":
        needed.append("RVOL expansion above Lance Phase 1 floor")
    if not _candidate_has_catalyst(candidate):
        needed.append("Catalyst classification")
    needed.append("2-minute bars and VWAP trigger check")
    return needed


def _moment_state(
    snapshot: dict[str, Any],
    candidate: dict[str, Any] | None,
) -> str:
    if candidate is not None:
        return "building_intraday_confirmation"
    if snapshot.get("confidence") in {"ERROR", "CONFLICT", "STALE_DATA"}:
        return "not_ready_data_quality"
    if snapshot.get("gap_basis") != "premarket":
        return "not_ready_data_quality"
    if _participation_status(snapshot) != "PASS":
        return "not_ready_participation"
    return "not_ready_missing_context"


def _verdict(candidate: dict[str, Any] | None) -> str:
    if candidate is None:
        return "No Phase 1 setup"
    grade = candidate.get("grade") or "candidate"
    return f"Phase 1 candidate: {grade}"


def _candidate_for_ticker(
    scan_output: dict[str, Any],
    ticker: str,
) -> dict[str, Any] | None:
    for candidate in scan_output.get("candidates") or []:
        if str(candidate.get("ticker") or "").upper() == ticker:
            return dict(candidate)
    return None


def _universe_fit_status(
    snapshot: dict[str, Any],
    candidate: dict[str, Any] | None,
) -> str:
    cap_tier = (candidate or {}).get("cap_tier")
    if cap_tier in {"mid", "large", "mega"}:
        return "PASS"
    market_cap = snapshot.get("market_cap")
    if isinstance(market_cap, int | float) and market_cap >= 2_000_000_000:
        return "PASS"
    if market_cap is None:
        return "UNKNOWN"
    return "FAIL"


def _universe_fit_detail(
    snapshot: dict[str, Any],
    candidate: dict[str, Any] | None,
) -> str:
    cap_tier = (candidate or {}).get("cap_tier")
    if cap_tier:
        return f"{cap_tier} cap fits Lance's liquid-name preference."
    if snapshot.get("market_cap") is not None:
        return "Market cap is available; liquid-name fit is inferred only from cap tier."
    return "Market cap is unknown."


def _move_status(snapshot: dict[str, Any]) -> str:
    gap_pct = snapshot.get("gap_pct")
    if not isinstance(gap_pct, int | float):
        return "UNKNOWN"
    abs_gap = abs(gap_pct)
    if abs_gap >= 5:
        return "PASS"
    if abs_gap >= 3:
        return "PARTIAL"
    return "FAIL"


def _move_detail(snapshot: dict[str, Any]) -> str:
    gap_pct = snapshot.get("gap_pct")
    if not isinstance(gap_pct, int | float):
        return "Move is unknown."
    return f"Absolute move is {abs(gap_pct):.2f}% versus a 3% Phase 1 floor."


def _participation_status(snapshot: dict[str, Any]) -> str:
    rel_volume = snapshot.get("rel_volume")
    if not isinstance(rel_volume, int | float):
        return "UNKNOWN"
    return "PASS" if rel_volume >= 3 else "FAIL"


def _participation_detail(snapshot: dict[str, Any]) -> str:
    rel_volume = snapshot.get("rel_volume")
    if not isinstance(rel_volume, int | float):
        return "RVOL is unknown."
    return f"RVOL is {rel_volume:.2f}x versus a 3.00x Lance Phase 1 floor."


def _data_quality_status(snapshot: dict[str, Any]) -> str:
    if snapshot.get("gap_basis") == "premarket" and snapshot.get("confidence") == "OK":
        return "PASS"
    return "BLOCKED"


def _data_quality_detail(snapshot: dict[str, Any]) -> str:
    return (
        f"gap_basis={snapshot.get('gap_basis') or 'unknown'}, "
        f"confidence={snapshot.get('confidence') or 'unknown'}."
    )


def _candidate_has_catalyst(candidate: dict[str, Any] | None) -> bool:
    if candidate is None:
        return False
    if candidate.get("has_catalyst") is True:
        return True
    evidence = candidate.get("evidence") or {}
    return bool(evidence.get("catalysts") or evidence.get("filings"))


def _ny_session_label(timestamp: Any) -> str:
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return "unknown"
    local = parsed.astimezone(NY_TZ).time()
    if time(4, 0) <= local < time(9, 30):
        return "premarket"
    if time(9, 30) <= local < time(10, 30):
        return "open_drive"
    if time(10, 30) <= local < time(15, 0):
        return "midday"
    if time(15, 0) <= local < time(16, 0):
        return "power_hour"
    if time(16, 0) <= local <= time(16, 0):
        return "regular_close"
    if time(16, 0) < local < time(20, 0):
        return "after_hours"
    return "off_session"


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=NY_TZ)
    return parsed


def _check(label: str, status: str, detail: str) -> dict[str, str]:
    return {"label": label, "status": status, "detail": detail}


def _moment(name: str, state: str, detail: str) -> dict[str, str]:
    return {"moment": name, "state": state, "detail": detail}
