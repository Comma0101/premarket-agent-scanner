from __future__ import annotations

from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from services.session_time_service import data_caveat_for, session_mode_for


DISCLAIMER = "Matches your filter — not buy/sell advice. Verify before acting."
NY_TZ = ZoneInfo("America/New_York")
LANCE_INTRADAY_CONFIRMATIONS = [
    "2-minute prior-bar high/low break",
    "2x volume confirmation",
    "VWAP filter pass",
]


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
    lance_state = _lance_state(snapshot=snapshot, candidate=candidate)

    return {
        "ticker": ticker,
        "trader": "lance_breitstein",
        "lens": "mean_reversion_after_capitulation",
        "verdict": _verdict(candidate),
        "moment_state": lance_state["state"],
        "lance_state": lance_state,
        "data_card": data_card,
        "setup_stack": setup_stack,
        "moment_path": _moment_path(snapshot, candidate),
        "what_we_lack": _what_we_lack(snapshot, candidate),
        "next_needed": next_needed,
        "candidate": candidate,
        "notes": list(scan_output.get("notes") or []),
        "disclaimer": DISCLAIMER,
    }


def build_trader_context_explanation(context: dict[str, Any]) -> dict[str, Any]:
    snapshot = _as_dict(context.get("snapshot"))
    evidence = _as_dict(context.get("evidence"))
    technicals = _as_dict(context.get("technicals"))
    trader = str(context.get("trader_profile") or "default")
    ticker = str(context.get("ticker") or snapshot.get("ticker") or "").upper()
    missing_fields = [str(field) for field in context.get("missing_fields") or []]
    setup_stack = _context_setup_stack(
        trader=trader,
        snapshot=snapshot,
        evidence=evidence,
        technicals=technicals,
    )
    lance_state = (
        _lance_state(snapshot=snapshot, technicals=technicals)
        if trader == "lance_breitstein"
        else None
    )
    moment_state = (
        lance_state["state"]
        if lance_state is not None
        else _context_moment_state(snapshot)
    )

    output = {
        "ticker": ticker,
        "trader": trader,
        "lens": _context_lens(trader),
        "verdict": _context_verdict(snapshot),
        "moment_state": moment_state,
        "data_card": _data_card(snapshot),
        "setup_stack": setup_stack,
        "moment_path": _context_moment_path(snapshot, evidence, technicals),
        "what_we_lack": missing_fields,
        "next_needed": _context_next_needed(snapshot, missing_fields),
        "context": context,
        "notes": list(context.get("notes") or []),
        "disclaimer": DISCLAIMER,
    }
    if lance_state is not None:
        output["lance_state"] = lance_state
    return output


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
        "halt_status": snapshot.get("halt_status"),
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
    return _lance_state(snapshot=snapshot, candidate=candidate)["state"]


def _lance_state(
    *,
    snapshot: dict[str, Any],
    candidate: dict[str, Any] | None = None,
    technicals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    caveat = data_caveat_for(
        snapshot.get("timestamp"),
        gap_basis=snapshot.get("gap_basis"),
        confidence=snapshot.get("confidence"),
        halt_status=snapshot.get("halt_status"),
    )
    if _lance_data_quality_blocked(snapshot):
        return _lance_state_packet(
            state="blocked_data_quality",
            reason=(
                "Data quality blocks Lance review: "
                f"gap_basis={snapshot.get('gap_basis') or 'unknown'}, "
                f"confidence={snapshot.get('confidence') or 'unknown'}."
            ),
            data_caveat=caveat,
        )

    intraday = _as_dict((technicals or {}).get("intraday"))
    signal = _as_dict(intraday.get("breitstein_signal"))
    if signal:
        if signal.get("vwap_filter_passed") is False:
            return _lance_state_packet(
                state="invalidated",
                reason="VWAP filter failed; Lance setup is invalidated.",
                direction=signal.get("direction"),
                data_caveat=caveat,
            )
        if (
            signal.get("confidence") == "OK"
            and signal.get("volume_2x_confirmed") is True
        ):
            return _lance_state_packet(
                state="triggered_reference",
                reason=(
                    "Lance intraday trigger is present: prior-bar break, "
                    "2x volume, and VWAP filter passed."
                ),
                required_confirmations=[],
                entry_reference=signal.get("entry_price"),
                risk_reference=signal.get("stop_price"),
                target_reference=signal.get("target_price"),
                reference_source="breitstein_intraday",
                direction=signal.get("direction"),
                data_caveat=caveat,
            )

    failures = _lance_phase_one_failures(
        snapshot=snapshot,
        candidate=candidate,
    )
    if failures:
        return _lance_state_packet(
            state="not_in_play",
            reason="Lance Phase 1 filters are not satisfied.",
            required_confirmations=failures,
            data_caveat=caveat,
        )

    if _technical_status(technicals or {}, "intraday") == "PASS":
        return _lance_state_packet(
            state="setup_forming",
            reason=(
                "Lance Phase 1 context and intraday bars are present; "
                "waiting for the exact trigger."
            ),
            required_confirmations=list(LANCE_INTRADAY_CONFIRMATIONS),
            data_caveat=caveat,
        )

    return _lance_state_packet(
        state="watching_for_setup",
        reason="Phase 1 Lance context is present; waiting for 2-minute confirmation.",
        required_confirmations=list(LANCE_INTRADAY_CONFIRMATIONS),
        data_caveat=caveat,
    )


def _lance_state_packet(
    *,
    state: str,
    reason: str,
    required_confirmations: list[str] | None = None,
    entry_reference: float | None = None,
    risk_reference: float | None = None,
    target_reference: float | None = None,
    reference_source: str | None = None,
    direction: str | None = None,
    data_caveat: str | None = None,
) -> dict[str, Any]:
    return {
        "state": state,
        "reason": reason,
        "required_confirmations": (
            list(required_confirmations) if required_confirmations is not None else []
        ),
        "entry_reference": entry_reference,
        "risk_reference": risk_reference,
        "target_reference": target_reference,
        "reference_source": reference_source,
        "direction": direction,
        "data_caveat": data_caveat,
    }


def _lance_phase_one_failures(
    *,
    snapshot: dict[str, Any],
    candidate: dict[str, Any] | None,
) -> list[str]:
    failures: list[str] = []
    universe_status = (
        _universe_fit_status(snapshot, candidate)
        if candidate is not None
        else _liquid_name_status(snapshot)
    )
    if universe_status != "PASS":
        failures.append("liquid-name fit")
    if _move_status(snapshot) == "FAIL":
        failures.append("abnormal move")
    if _participation_status(snapshot) != "PASS":
        failures.append("RVOL expansion")
    return failures


def _lance_data_quality_blocked(snapshot: dict[str, Any]) -> bool:
    confidence = snapshot.get("confidence")
    gap_basis = snapshot.get("gap_basis")
    if confidence != "OK":
        return True
    if gap_basis == "premarket":
        return False
    return not (
        gap_basis == "last_trade"
        and session_mode_for(snapshot.get("timestamp")) == "MARKET_OPEN"
    )


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


def _context_setup_stack(
    *,
    trader: str,
    snapshot: dict[str, Any],
    evidence: dict[str, Any],
    technicals: dict[str, Any],
) -> list[dict[str, str]]:
    checks = [
        _check("Data quality", _data_quality_status(snapshot), _data_quality_detail(snapshot))
    ]
    if trader == "timothy_sykes":
        checks.extend(
            [
                _check(
                    "Small-cap fit",
                    _small_cap_status(snapshot),
                    _small_cap_detail(snapshot),
                ),
                _check(
                    "Float / rotation",
                    _float_status(evidence),
                    _float_detail(evidence),
                ),
                _check(
                    "Catalyst context",
                    _evidence_list_status(evidence, "catalysts"),
                    _evidence_list_detail(evidence, "catalysts"),
                ),
                _check(
                    "Filing context",
                    _evidence_list_status(evidence, "filings"),
                    _evidence_list_detail(evidence, "filings"),
                ),
                _check(
                    "Intraday context",
                    _technical_status(technicals, "intraday"),
                    _technical_detail(technicals, "intraday"),
                ),
            ]
        )
        return checks

    if trader == "lance_breitstein":
        checks.extend(
            [
                _check(
                    "Liquid-name fit",
                    _liquid_name_status(snapshot),
                    _liquid_name_detail(snapshot),
                ),
                _check(
                    "Participation",
                    _participation_status(snapshot),
                    _participation_detail(snapshot),
                ),
                _check(
                    "Intraday context",
                    _technical_status(technicals, "intraday"),
                    _technical_detail(technicals, "intraday"),
                ),
                _check(
                    "Daily context",
                    _technical_status(technicals, "daily"),
                    _technical_detail(technicals, "daily"),
                ),
                _check(
                    "Catalyst context",
                    _evidence_list_status(evidence, "catalysts"),
                    _evidence_list_detail(evidence, "catalysts"),
                ),
            ]
        )
        return checks

    if trader in {"alex_temiz", "tim_grittani"}:
        checks.extend(
            [
                _check(
                    "Small-cap fit",
                    _small_cap_status(snapshot),
                    _small_cap_detail(snapshot),
                ),
                _check(
                    "Participation",
                    _participation_status(snapshot),
                    _participation_detail(snapshot),
                ),
                _check(
                    "Daily context",
                    _technical_status(technicals, "daily"),
                    _technical_detail(technicals, "daily"),
                ),
                _check(
                    "Intraday context",
                    _technical_status(technicals, "intraday"),
                    _technical_detail(technicals, "intraday"),
                ),
                _check(
                    "Catalyst context",
                    _evidence_list_status(evidence, "catalysts"),
                    _evidence_list_detail(evidence, "catalysts"),
                ),
            ]
        )
        return checks

    checks.extend(
        [
            _check(
                "Evidence context",
                "PASS" if evidence else "UNKNOWN",
                "Evidence packet is present." if evidence else "Evidence packet is unavailable.",
            ),
            _check(
                "Intraday context",
                _technical_status(technicals, "intraday"),
                _technical_detail(technicals, "intraday"),
            ),
            _check(
                "Daily context",
                _technical_status(technicals, "daily"),
                _technical_detail(technicals, "daily"),
            ),
        ]
    )
    return checks


def _context_lens(trader: str) -> str:
    return {
        "timothy_sykes": "small_cap_gap_catalyst_and_float",
        "lance_breitstein": "liquid_name_mean_reversion_context",
        "alex_temiz": "small_cap_first_red_day_context",
        "tim_grittani": "small_cap_morning_panic_context",
    }.get(trader, "grounded_trader_context")


def _context_verdict(snapshot: dict[str, Any]) -> str:
    if _data_quality_status(snapshot) == "BLOCKED":
        return "Blocked by data quality"
    return "Context ready"


def _context_moment_state(snapshot: dict[str, Any]) -> str:
    if _data_quality_status(snapshot) == "BLOCKED":
        return "not_ready_data_quality"
    return "ready_for_profile_review"


def _context_moment_path(
    snapshot: dict[str, Any],
    evidence: dict[str, Any],
    technicals: dict[str, Any],
) -> list[dict[str, str]]:
    data_ready = _data_quality_status(snapshot) == "PASS"
    evidence_ready = bool(evidence)
    technical_ready = (
        _technical_status(technicals, "intraday") == "PASS"
        or _technical_status(technicals, "daily") == "PASS"
    )
    return [
        _moment(
            "Data",
            "ready" if data_ready else "blocked",
            _data_quality_detail(snapshot),
        ),
        _moment(
            "Evidence",
            "ready" if evidence_ready else "waiting",
            "Evidence packet is present." if evidence_ready else "Evidence packet is unavailable.",
        ),
        _moment(
            "Technicals",
            "ready" if technical_ready else "waiting",
            "At least one bar-derived packet is present."
            if technical_ready
            else "Requested bar-derived packet is unavailable or low confidence.",
        ),
        _moment(
            "Profile review",
            "ready" if data_ready else "blocked",
            "Trader profile can review grounded context."
            if data_ready
            else "Profile review is blocked until data quality improves.",
        ),
    ]


def _context_next_needed(
    snapshot: dict[str, Any],
    missing_fields: list[str],
) -> list[str]:
    needed: list[str] = []
    if _data_quality_status(snapshot) == "BLOCKED":
        needed.append("Fresh premarket quote with OK confidence")
    mapping = {
        "float": "Float data",
        "rvol": "RVOL from the data layer",
        "catalyst": "Catalyst classification",
        "filings": "Recent filing context",
        "former_runner": "Former-runner evidence",
        "short_interest": "Short-interest data",
        "intraday_bars": "Intraday bar packet",
        "daily_bars": "Daily bar packet",
        "vwap": "VWAP from intraday bars",
        "order_flow": "Order-flow context",
        "footprint": "Footprint context",
    }
    for field in missing_fields:
        label = mapping.get(field, field)
        if label not in needed:
            needed.append(label)
    return needed


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


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


def _small_cap_status(snapshot: dict[str, Any]) -> str:
    market_cap = snapshot.get("market_cap")
    if not isinstance(market_cap, int | float):
        return "UNKNOWN"
    return "PASS" if market_cap <= 2_000_000_000 else "FAIL"


def _small_cap_detail(snapshot: dict[str, Any]) -> str:
    if snapshot.get("market_cap") is None:
        return "Market cap is unknown."
    if _small_cap_status(snapshot) == "PASS":
        return "Market cap fits the small-cap profile in the data card."
    return "Market cap is above the small-cap profile range in the data card."


def _liquid_name_status(snapshot: dict[str, Any]) -> str:
    market_cap = snapshot.get("market_cap")
    if not isinstance(market_cap, int | float):
        return "UNKNOWN"
    return "PASS" if market_cap >= 2_000_000_000 else "FAIL"


def _liquid_name_detail(snapshot: dict[str, Any]) -> str:
    if snapshot.get("market_cap") is None:
        return "Market cap is unknown."
    if _liquid_name_status(snapshot) == "PASS":
        return "Market cap fits the liquid-name profile in the data card."
    return "Market cap is below the liquid-name profile range in the data card."


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


def _float_status(evidence: dict[str, Any]) -> str:
    if not evidence:
        return "UNKNOWN"
    if evidence.get("is_low_float") is True:
        return "PASS"
    if isinstance(evidence.get("float_rotation"), int | float):
        return "PASS"
    if evidence.get("is_low_float") is False:
        return "FAIL"
    return "UNKNOWN"


def _float_detail(evidence: dict[str, Any]) -> str:
    if not evidence:
        return "Float and rotation evidence is unavailable."
    if evidence.get("is_low_float") is True:
        return "Low-float evidence is present."
    if isinstance(evidence.get("float_rotation"), int | float):
        return "Float-rotation evidence is present."
    if evidence.get("is_low_float") is False:
        return "Low-float evidence is explicitly false."
    return "Float and rotation evidence is unknown."


def _evidence_list_status(evidence: dict[str, Any], key: str) -> str:
    if not evidence:
        return "UNKNOWN"
    return "PASS" if evidence.get(key) else "UNKNOWN"


def _evidence_list_detail(evidence: dict[str, Any], key: str) -> str:
    label = key.replace("_", " ")
    if not evidence:
        return f"{label} evidence is unavailable."
    if evidence.get(key):
        return f"{label} evidence is present."
    return f"{label} evidence is unknown."


def _technical_status(technicals: dict[str, Any], key: str) -> str:
    packet = _as_dict(technicals.get(key))
    if not packet:
        return "UNKNOWN"
    confidence = packet.get("confidence")
    if confidence == "OK":
        return "PASS"
    if confidence == "ERROR":
        return "BLOCKED"
    return "UNKNOWN"


def _technical_detail(technicals: dict[str, Any], key: str) -> str:
    packet = _as_dict(technicals.get(key))
    label = key.replace("_", " ")
    if not packet:
        return f"{label} packet is unavailable."
    confidence = packet.get("confidence") or "unknown"
    return f"{label} packet confidence={confidence}."


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
