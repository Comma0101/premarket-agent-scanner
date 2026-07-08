"""Shared Lance data-evidence formatting for CLI surfaces."""

from __future__ import annotations

from typing import Any

DATA_USED_ROW_LIMIT = 6
BENCHMARK_ORDER = ["SPY", "QQQ", "IWM", "SMH", "XLK"]


def data_used_lines(payload: dict[str, Any], *, row_limit: int = DATA_USED_ROW_LIMIT) -> list[str]:
    """Return compact evidence lines from the normalized payload or full-cycle fallback."""
    data_used = payload.get("data_used") if isinstance(payload.get("data_used"), dict) else {}
    benchmark_rows = data_used.get("benchmarks") if isinstance(data_used.get("benchmarks"), list) else []
    candidate_rows = data_used.get("candidate_rows") if isinstance(data_used.get("candidate_rows"), list) else []

    if not benchmark_rows and not candidate_rows:
        benchmark_rows = _benchmark_rows_from_full_cycle(payload)
        candidate_rows = _candidate_rows_from_full_cycle(payload)

    lines: list[str] = []
    lines.extend(_format_benchmark(row) for row in benchmark_rows[:5] if isinstance(row, dict))
    clean_rows = [row for row in candidate_rows if isinstance(row, dict)]
    for row in clean_rows[:row_limit]:
        lines.append(_format_candidate_evidence(row))
    remaining = len(clean_rows) - row_limit
    if remaining > 0:
        lines.append(f"... {remaining} more row(s) in latest_command_center.json")
    return lines


def selection_audit_lines(payload: dict[str, Any]) -> list[str]:
    audit = payload.get("selection_audit") if isinstance(payload.get("selection_audit"), dict) else {}
    requested = audit.get("requested_tickers") if isinstance(audit.get("requested_tickers"), list) else []
    returned = audit.get("returned_tickers") if isinstance(audit.get("returned_tickers"), list) else []
    omitted = audit.get("omitted_tickers") if isinstance(audit.get("omitted_tickers"), list) else []
    if not requested and not returned and not omitted:
        return []
    lines = [
        f"requested={_join_values(requested)}",
        f"returned={_join_values(returned)}",
    ]
    if not omitted:
        lines.append("omitted=none")
        return lines
    for row in omitted:
        if not isinstance(row, dict):
            continue
        stage = row.get("stage")
        stage_label = f" [{_value(stage)}]" if stage else ""
        lines.append(f"omitted {_value(row.get('ticker'))}{stage_label}: {_value(row.get('reason'))}")
    return lines


def _benchmark_rows_from_full_cycle(payload: dict[str, Any]) -> list[dict[str, Any]]:
    full_cycle = payload.get("full_cycle") if isinstance(payload.get("full_cycle"), dict) else {}
    context = full_cycle.get("market_context") if isinstance(full_cycle.get("market_context"), dict) else {}
    benchmarks = context.get("benchmarks") if isinstance(context.get("benchmarks"), dict) else {}
    symbols = [symbol for symbol in BENCHMARK_ORDER if symbol in benchmarks]
    known_symbols = set(BENCHMARK_ORDER)
    symbols.extend(sorted(symbol for symbol in benchmarks if symbol not in known_symbols))
    rows = []
    for symbol in symbols:
        data = benchmarks.get(symbol)
        if isinstance(data, dict):
            rows.append({
                "ticker": symbol,
                "gap_pct": data.get("gap_pct"),
                "gap_basis": data.get("gap_basis"),
                "confidence": data.get("confidence"),
                "as_of": data.get("as_of") or data.get("as_of_et"),
                "sources": data.get("sources") or [],
            })
    return rows


def _candidate_rows_from_full_cycle(payload: dict[str, Any]) -> list[dict[str, Any]]:
    full_cycle = payload.get("full_cycle") if isinstance(payload.get("full_cycle"), dict) else {}
    for key in ["combined_watchlist", "top_intraday_watchlist", "top_swing_watchlist", "top_updates"]:
        rows = full_cycle.get(key)
        if isinstance(rows, list) and rows:
            return [_candidate_row_from_full_cycle(row) for row in rows if isinstance(row, dict)]
    return []


def _candidate_row_from_full_cycle(row: dict[str, Any]) -> dict[str, Any]:
    data_quality = row.get("data_quality") if isinstance(row.get("data_quality"), dict) else {}
    output = {
        "ticker": row.get("ticker"),
        "intraday_state": row.get("intraday_state") or row.get("state"),
        "swing_state": row.get("swing_state"),
        "intraday_playbook": row.get("intraday_playbook") or row.get("playbook"),
        "swing_playbook": row.get("swing_playbook"),
        "latest_price": data_quality.get("latest_price"),
        "gap_pct": data_quality.get("gap_pct"),
        "gap_basis": data_quality.get("gap_basis"),
        "confidence": data_quality.get("confidence"),
        "data_status": data_quality.get("data_status"),
        "rel_volume": data_quality.get("rel_volume"),
        "volume": data_quality.get("volume"),
        "as_of": data_quality.get("as_of"),
        "as_of_et": data_quality.get("as_of_et"),
        "sources": data_quality.get("sources") or [],
        "data_caveat": data_quality.get("data_caveat"),
    }
    if data_quality.get("rel_volume_basis") is not None:
        output["rel_volume_basis"] = data_quality.get("rel_volume_basis")
    bias = row.get("swing_bias") or row.get("bias")
    if bias:
        output["swing_bias"] = bias
    return output


def _format_benchmark(data: dict[str, Any]) -> str:
    return (
        f"{_value(data.get('ticker'))}: gap={_format_pct(data.get('gap_pct'))} "
        f"basis={_value(data.get('gap_basis'))} "
        f"confidence={_value(data.get('confidence'))} "
        f"as_of={_value(data.get('as_of') or data.get('as_of_et'))} "
        f"sources={_format_sources(data.get('sources'))}"
    )


def _format_candidate_evidence(row: dict[str, Any]) -> str:
    parts = [
        _value(row.get("ticker")),
        f"intraday={_value(row.get('intraday_state'))}",
        f"swing={_value(row.get('swing_state'))}",
        f"playbook={_value(row.get('intraday_playbook') or row.get('swing_playbook'))}",
        f"price={_format_price(row.get('latest_price'))}",
        f"gap={_format_pct(row.get('gap_pct'))}",
        f"rvol={_format_multiple(row.get('rel_volume'))}",
        f"basis={_value(row.get('gap_basis'))}",
        f"confidence={_value(row.get('confidence'))}",
        f"status={_value(row.get('data_status'))}",
        f"as_of={_value(row.get('as_of_et') or row.get('as_of'))}",
        f"sources={_format_sources(row.get('sources'))}",
    ]
    if row.get("rel_volume_basis") is not None:
        parts.insert(7, f"rvol_basis={_value(row.get('rel_volume_basis'))}")
    if row.get("swing_bias"):
        parts.insert(4, f"bias={_value(row.get('swing_bias'))}")
    caveat = row.get("data_caveat")
    if caveat:
        parts.append(f"caveat={_value(caveat)}")
    return " | ".join(parts)


def _format_pct(value: Any) -> str:
    if not isinstance(value, int | float):
        return "unknown"
    return f"{float(value):.2f}%"


def _format_price(value: Any) -> str:
    if not isinstance(value, int | float):
        return "unknown"
    return f"{float(value):.2f}"


def _format_multiple(value: Any) -> str:
    if not isinstance(value, int | float):
        return "unknown"
    return f"{float(value):.2f}x"


def _format_sources(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "none"
    return ",".join(_value(source) for source in value)


def _join_values(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "none"
    return ", ".join(_value(item) for item in value)


def _value(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)
