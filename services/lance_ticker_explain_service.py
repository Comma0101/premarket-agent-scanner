from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.lance_market_scan_service import DISCLAIMER


DEFAULT_LANCE_PAYLOAD_PATH = Path("data/live_sessions/latest_command_center.json")


class LanceTickerExplainService:
    """Explain one ticker from an existing Lance command-center payload."""

    def explain(
        self,
        *,
        ticker: str,
        payload: dict[str, Any] | None = None,
        payload_path: str | Path | None = DEFAULT_LANCE_PAYLOAD_PATH,
    ) -> dict[str, Any]:
        normalized = str(ticker or "").strip().upper()
        if not normalized:
            return {"error": "ticker is required."}
        source_payload = payload if isinstance(payload, dict) else _load_payload(payload_path)
        if not isinstance(source_payload, dict):
            return {"error": f"Lance payload not found: {payload_path}"}

        candidate = _candidate_row(normalized, source_payload)
        if candidate is not None:
            return _found_output(normalized, source_payload, candidate)

        omitted = _omitted_row(normalized, source_payload)
        if omitted is not None:
            return _omitted_output(normalized, source_payload, omitted)

        return {
            "agent_name": "lance_full_cycle",
            "mode": "ticker_explain",
            "ticker": normalized,
            "status": "NOT_FOUND",
            "session_banner": source_payload.get("session_banner"),
            "summary": f"{normalized} was not found in Lance output or requested ticker audit.",
            "source_paths": [],
            "disclaimer": source_payload.get("disclaimer") or DISCLAIMER,
        }


def _load_payload(payload_path: str | Path | None) -> dict[str, Any] | None:
    path = Path(payload_path or DEFAULT_LANCE_PAYLOAD_PATH)
    if not path.exists():
        return None
    parsed = json.loads(path.read_text(encoding="utf-8"))
    return parsed if isinstance(parsed, dict) else None


def _found_output(
    ticker: str,
    payload: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    intraday = _detail_row(ticker, payload, key="top_intraday_watchlist")
    swing = _detail_row(ticker, payload, key="top_swing_watchlist")
    source_paths = ["data_used.candidate_rows"]
    if intraday:
        source_paths.append("full_cycle.top_intraday_watchlist")
    if swing:
        source_paths.append("full_cycle.top_swing_watchlist")
    confidence = candidate.get("confidence")
    gap_basis = candidate.get("gap_basis")
    intraday_state = candidate.get("intraday_state")
    swing_state = candidate.get("swing_state")
    return {
        "agent_name": "lance_full_cycle",
        "mode": "ticker_explain",
        "ticker": ticker,
        "status": "FOUND",
        "session_banner": payload.get("session_banner"),
        "summary": (
            f"{ticker} is in Lance output: intraday={_value(intraday_state)}, "
            f"swing={_value(swing_state)}, confidence={_value(confidence)}, "
            f"gap_basis={_value(gap_basis)}."
        ),
        "data_quality": _data_quality(candidate),
        "lance_state": {
            "intraday_state": intraday_state,
            "swing_state": swing_state,
            "intraday_playbook": candidate.get("intraday_playbook"),
            "swing_playbook": candidate.get("swing_playbook"),
            "swing_bias": candidate.get("swing_bias"),
            "swing_bias_reason": candidate.get("swing_bias_reason"),
        },
        "intraday": intraday,
        "swing": swing,
        "benchmark_context": _benchmarks(payload),
        "source_paths": source_paths,
        "disclaimer": payload.get("disclaimer") or DISCLAIMER,
    }


def _omitted_output(
    ticker: str,
    payload: dict[str, Any],
    omitted: dict[str, Any],
) -> dict[str, Any]:
    stage = _value(omitted.get("stage"))
    reason = _value(omitted.get("reason"))
    return {
        "agent_name": "lance_full_cycle",
        "mode": "ticker_explain",
        "ticker": ticker,
        "status": "OMITTED",
        "session_banner": payload.get("session_banner"),
        "summary": f"{ticker} was requested but omitted at {stage}: {reason}",
        "omitted_reason": omitted,
        "source_paths": ["selection_audit.omitted_tickers"],
        "disclaimer": payload.get("disclaimer") or DISCLAIMER,
    }


def _candidate_row(ticker: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    data_used = payload.get("data_used") if isinstance(payload.get("data_used"), dict) else {}
    rows = data_used.get("candidate_rows") if isinstance(data_used.get("candidate_rows"), list) else []
    for row in rows:
        if isinstance(row, dict) and str(row.get("ticker") or "").upper() == ticker:
            return row
    return None


def _omitted_row(ticker: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    audit = payload.get("selection_audit") if isinstance(payload.get("selection_audit"), dict) else {}
    rows = audit.get("omitted_tickers") if isinstance(audit.get("omitted_tickers"), list) else []
    for row in rows:
        if isinstance(row, dict) and str(row.get("ticker") or "").upper() == ticker:
            return row
    return None


def _detail_row(ticker: str, payload: dict[str, Any], *, key: str) -> dict[str, Any]:
    full_cycle = payload.get("full_cycle") if isinstance(payload.get("full_cycle"), dict) else {}
    rows = full_cycle.get(key) if isinstance(full_cycle.get(key), list) else []
    for row in rows:
        if isinstance(row, dict) and str(row.get("ticker") or "").upper() == ticker:
            return {
                "state": row.get("state") or row.get("current_state"),
                "playbook": row.get("playbook"),
                "bias": row.get("bias"),
                "bias_reason": row.get("bias_reason"),
                "thesis": row.get("thesis") or row.get("state_reason"),
                "waiting_for": list(row.get("waiting_for") or []),
                "invalidates_if": list(row.get("invalidates_if") or []),
                "conflict_flags": list(row.get("conflict_flags") or []),
            }
    return {}


def _benchmarks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data_used = payload.get("data_used") if isinstance(payload.get("data_used"), dict) else {}
    rows = data_used.get("benchmarks") if isinstance(data_used.get("benchmarks"), list) else []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _data_quality(candidate: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "latest_price",
        "gap_pct",
        "gap_basis",
        "confidence",
        "data_status",
        "rel_volume",
        "rel_volume_basis",
        "volume",
        "as_of",
        "as_of_et",
        "sources",
        "data_caveat",
    ]
    return {key: candidate.get(key) for key in keys}


def _value(value: Any) -> str:
    return "unknown" if value is None or value == "" else str(value)
