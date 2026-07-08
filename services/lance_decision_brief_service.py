from __future__ import annotations

from typing import Any

from services.lance_market_scan_service import DISCLAIMER


class LanceDecisionBriefService:
    """Build the concise Lance operator read from an existing command-center payload."""

    def build(self, payload: dict[str, Any]) -> dict[str, Any]:
        single_run = _dict(payload.get("single_run_read"))
        full_cycle = _dict(payload.get("full_cycle"))
        session_context = _dict(payload.get("session_context"))
        data_used = _dict(payload.get("data_used"))
        doctor = _dict(payload.get("data_doctor"))

        active_tickers = _symbols(single_run.get("active_monitor"))
        swing_tickers = _symbols(single_run.get("swing_watch"))
        blocked_tickers = _symbols(single_run.get("blocked_data_quality"))

        rows = _rows_by_ticker(data_used.get("candidate_rows"))
        full_cycle_rows = _rows_by_ticker(full_cycle.get("combined_watchlist"))
        intraday_lookup = _rows_by_ticker(full_cycle.get("top_intraday_watchlist"))
        swing_lookup = _rows_by_ticker(full_cycle.get("top_swing_watchlist"))

        focus = [
            _focus_card(
                ticker=ticker,
                lane="intraday",
                row=rows.get(ticker) or full_cycle_rows.get(ticker) or {},
                setup=intraday_lookup.get(ticker) or full_cycle_rows.get(ticker) or {},
            )
            for ticker in active_tickers
        ]
        swing_watch = [
            _focus_card(
                ticker=ticker,
                lane="swing",
                row=rows.get(ticker) or full_cycle_rows.get(ticker) or {},
                setup=swing_lookup.get(ticker) or full_cycle_rows.get(ticker) or {},
            )
            for ticker in swing_tickers
        ]
        blocked = [
            _blocked_card(ticker=ticker, row=rows.get(ticker) or full_cycle_rows.get(ticker) or {})
            for ticker in blocked_tickers
        ]

        is_open = bool(session_context.get("is_market_open"))
        session_mode = str(session_context.get("session_mode") or "").upper()
        posture = _posture(
            is_market_open=is_open,
            session_mode=session_mode,
            focus_count=len(focus),
            swing_count=len(swing_watch),
            blocked_count=len(blocked),
        )
        what_would_change = _what_would_change(
            focus=focus,
            swing_watch=swing_watch,
            doctor=doctor,
            session_mode=session_mode,
            is_market_open=is_open,
        )

        return {
            "agent_name": "lance_full_cycle",
            "mode": "decision_brief",
            "status": str(payload.get("status") or "OK"),
            "session_banner": payload.get("session_banner"),
            "lance_posture": posture,
            "headline": _headline(
                posture=posture,
                session_mode=session_mode,
                focus_count=len(focus),
                swing_count=len(swing_watch),
                blocked_count=len(blocked),
            ),
            "focus": focus,
            "swing_watch": swing_watch,
            "blocked": blocked,
            "ticker_slices": _ticker_slices(focus=focus, swing_watch=swing_watch, blocked=blocked),
            "omitted": _omitted(payload.get("selection_audit")),
            "what_would_change": what_would_change,
            "talk_track": _talk_track(
                posture=posture,
                session_mode=session_mode,
                focus=focus,
                swing_watch=swing_watch,
                blocked_count=len(blocked),
            ),
            "disclaimer": payload.get("disclaimer") or DISCLAIMER,
        }


def _posture(
    *,
    is_market_open: bool,
    session_mode: str,
    focus_count: int,
    swing_count: int,
    blocked_count: int,
) -> str:
    if not is_market_open and session_mode == "MARKET_CLOSED":
        return "stand_down"
    if focus_count or swing_count:
        return "monitor"
    if blocked_count:
        return "stand_down"
    return "review"


def _headline(
    *,
    posture: str,
    session_mode: str,
    focus_count: int,
    swing_count: int,
    blocked_count: int,
) -> str:
    if posture == "stand_down" and session_mode == "MARKET_CLOSED":
        return (
            f"Stand down: market is closed and {blocked_count} ticker(s) "
            "are blocked by data quality."
        )
    if posture == "stand_down":
        return f"Stand down: {blocked_count} ticker(s) blocked by data quality."
    if posture == "monitor":
        return (
            f"Monitor {focus_count} active ticker(s); "
            f"{swing_count} swing watch(es); {blocked_count} blocked."
        )
    return "Review only: no active Lance monitor or swing watch."


def _focus_card(
    *,
    ticker: str,
    lane: str,
    row: dict[str, Any],
    setup: dict[str, Any],
) -> dict[str, Any]:
    playbook_key = "intraday_playbook" if lane == "intraday" else "swing_playbook"
    state_key = "intraday_state" if lane == "intraday" else "swing_state"
    state = setup.get("state") or row.get(state_key) or setup.get(state_key)
    playbook = setup.get("playbook") or row.get(playbook_key) or setup.get(playbook_key)
    why = (
        setup.get("thesis")
        or setup.get("state_reason")
        or setup.get("why")
        or setup.get("reason")
        or "No setup thesis supplied by the current Lance payload."
    )
    card = {
        "ticker": ticker,
        "lane": lane,
        "state": state,
        "playbook": playbook,
        "why": why,
        "price": row.get("latest_price"),
        "gap_pct": row.get("gap_pct"),
        "rel_volume": row.get("rel_volume"),
        "gap_basis": row.get("gap_basis"),
        "confidence": row.get("confidence"),
        "as_of": row.get("as_of_et") or row.get("as_of"),
        "waiting_for": _list(setup.get("waiting_for")),
        "invalidates_if": _list(setup.get("invalidates_if")),
        "data_quality": _data_quality_text(row),
    }
    if row.get("rel_volume_basis") is not None:
        card["rel_volume_basis"] = row.get("rel_volume_basis")
    if lane == "swing":
        card["bias"] = setup.get("bias") or row.get("swing_bias")
        card["bias_reason"] = setup.get("bias_reason") or row.get("swing_bias_reason")
    return card


def _blocked_card(*, ticker: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "reason": (
            f"confidence={_value(row.get('confidence'))} / "
            f"gap_basis={_value(row.get('gap_basis'))} / "
            f"status={_value(row.get('data_status'))}"
        ),
        "caveat": row.get("data_caveat"),
    }


def _ticker_slices(
    *,
    focus: list[dict[str, Any]],
    swing_watch: list[dict[str, Any]],
    blocked: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = [*focus, *swing_watch]
    slices = []
    for row in rows:
        ticker = _value(row.get("ticker"))
        slices.append({
            "ticker": ticker,
            "lane": _value(row.get("lane")),
            "state": _value(row.get("state")),
            "playbook": _value(row.get("playbook")),
            "bias": row.get("bias"),
            "data": _slice_data(row),
            "why": _value(row.get("why")),
            "watch": _join_first(row.get("waiting_for")),
            "risk": _join_first(row.get("invalidates_if")),
            "quality": _value(row.get("data_quality")),
        })
    for row in blocked:
        slices.append({
            "ticker": _value(row.get("ticker")),
            "lane": "blocked",
            "state": "blocked_data_quality",
            "playbook": "none",
            "bias": None,
            "data": _value(row.get("reason")),
            "why": _value(row.get("caveat") or row.get("reason")),
            "watch": "fix data quality first",
            "risk": "do not treat as live setup",
            "quality": _value(row.get("reason")),
        })
    return slices


def _slice_data(row: dict[str, Any]) -> str:
    parts = [
        f"price={_value(row.get('price'))}",
        f"gap={_value(row.get('gap_pct'))}%",
        f"rvol={_value(row.get('rel_volume'))}x",
    ]
    if row.get("rel_volume_basis") is not None:
        parts.append(f"rvol_basis={_value(row.get('rel_volume_basis'))}")
    parts.extend([
        f"basis={_value(row.get('gap_basis'))}",
        f"confidence={_value(row.get('confidence'))}",
        f"as_of={_value(row.get('as_of'))}",
    ])
    return " ".join(parts)


def _join_first(value: Any) -> str:
    items = _list(value)
    if not items:
        return "none"
    return "; ".join(str(item) for item in items[:2])


def _data_quality_text(row: dict[str, Any]) -> str:
    parts = [
        f"confidence={_value(row.get('confidence'))}",
        f"gap_basis={_value(row.get('gap_basis'))}",
    ]
    if row.get("rel_volume_basis") is not None:
        parts.append(f"rvol_basis={_value(row.get('rel_volume_basis'))}")
    parts.append(f"as_of={_value(row.get('as_of_et') or row.get('as_of'))}")
    return " / ".join(parts)


def _what_would_change(
    *,
    focus: list[dict[str, Any]],
    swing_watch: list[dict[str, Any]],
    doctor: dict[str, Any],
    session_mode: str,
    is_market_open: bool,
) -> list[str]:
    changes: list[str] = []
    for action in _list(doctor.get("next_actions")):
        _append_unique(changes, str(action))
    for card in [*focus, *swing_watch]:
        invalidations = _list(card.get("invalidates_if"))
        if invalidations:
            _append_unique(changes, f"{card['ticker']}: {invalidations[0]}")
    if not is_market_open and session_mode == "MARKET_CLOSED":
        _append_unique(
            changes,
            "Market must be open or a fresh premarket print must be available before live Lance upgrades.",
        )
    return changes


def _talk_track(
    *,
    posture: str,
    session_mode: str,
    focus: list[dict[str, Any]],
    swing_watch: list[dict[str, Any]],
    blocked_count: int,
) -> list[str]:
    if posture == "stand_down" and session_mode == "MARKET_CLOSED":
        return ["No Lance live action context: market is closed and current rows are caveated."]
    if focus:
        first = focus[0]
        return [
            (
                f"Lance focus is {first['ticker']}: {first['state']} "
                f"under {first['playbook']}."
            )
        ]
    if swing_watch:
        first = swing_watch[0]
        return [
            (
                f"Lance swing focus is {first['ticker']}: {first['state']} "
                f"under {first['playbook']}."
            )
        ]
    if blocked_count:
        return [f"Lance has {blocked_count} blocked ticker(s); inspect data quality first."]
    return ["No Lance setup is active in the current payload."]


def _rows_by_ticker(value: Any) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in value or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker:
            rows[ticker] = row
    return rows


def _omitted(value: Any) -> list[dict[str, Any]]:
    audit = _dict(value)
    return [dict(row) for row in audit.get("omitted_tickers") or [] if isinstance(row, dict)]


def _symbols(value: Any) -> list[str]:
    output: list[str] = []
    for item in value or []:
        ticker = str(item.get("ticker") if isinstance(item, dict) else item).strip().upper()
        if ticker and ticker not in output:
            output.append(ticker)
    return output


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _value(value: Any) -> str:
    return "unknown" if value is None or value == "" else str(value)


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)
