from __future__ import annotations

from typing import Any

from services.lance_market_scan_service import DISCLAIMER


class LanceSessionTrackerService:
    """Compare two Lance full-cycle payloads and summarize workflow changes."""

    def diff(
        self,
        *,
        previous: dict[str, Any] | None,
        current: dict[str, Any],
    ) -> dict[str, Any]:
        previous_rows = _index_rows(previous)
        current_rows = _index_rows(current)
        groups: dict[str, list[dict[str, Any]]] = {
            "new": [],
            "upgraded": [],
            "downgraded": [],
            "unchanged": [],
            "removed": [],
        }

        for ticker in sorted(current_rows):
            current_row = current_rows[ticker]
            previous_row = previous_rows.get(ticker)
            if previous_row is None:
                groups["new"].append(current_row)
                continue
            change = _change(previous_row, current_row)
            groups[_change_bucket(change)].append(change)

        for ticker in sorted(set(previous_rows) - set(current_rows)):
            groups["removed"].append(previous_rows[ticker])

        data_caveats = _data_caveats(current_rows.values())
        summary = {
            "previous_count": len(previous_rows),
            "current_count": len(current_rows),
            "new_count": len(groups["new"]),
            "upgraded_count": len(groups["upgraded"]),
            "downgraded_count": len(groups["downgraded"]),
            "unchanged_count": len(groups["unchanged"]),
            "removed_count": len(groups["removed"]),
            "data_caveat_count": len(data_caveats),
        }
        return {
            "agent_name": "lance_full_cycle",
            "mode": "session_tracker",
            "strategy": "Lance full-cycle session tracking",
            "status": _status(current),
            "previous_session_ids": _session_ids(previous),
            "current_session_ids": _session_ids(current),
            "summary": summary,
            "one_liner": _one_liner(summary),
            "groups": groups,
            "data_caveats": data_caveats,
            "notes": [
                "Tracker compares tool-produced full-cycle watchlist rows only.",
                "Changes are workflow buckets, not trade outcomes.",
            ],
            "disclaimer": current.get("disclaimer") or DISCLAIMER,
        }


def _index_rows(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    rows = payload.get("combined_watchlist")
    if not isinstance(rows, list):
        return {}
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = _normalize_row(row)
        ticker = normalized.get("ticker")
        if ticker:
            output[str(ticker)] = normalized
    return output


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").strip().upper()
    quality = row.get("data_quality") if isinstance(row.get("data_quality"), dict) else {}
    state = _primary_state(row)
    score = _primary_score(row)
    return {
        "ticker": ticker,
        "lanes": list(row.get("lanes") or []),
        "state": state,
        "intraday_state": row.get("intraday_state"),
        "swing_state": row.get("swing_state"),
        "score": score,
        "intraday_score": row.get("intraday_score"),
        "swing_score": row.get("swing_score"),
        "data_quality": dict(quality),
        "confidence": quality.get("confidence"),
        "gap_basis": quality.get("gap_basis"),
        "as_of_et": quality.get("as_of_et") or quality.get("as_of"),
    }


def _primary_state(row: dict[str, Any]) -> str:
    states = [
        str(row.get("intraday_state") or ""),
        str(row.get("swing_state") or ""),
    ]
    states = [state for state in states if state]
    if not states:
        return "unknown"
    return max(states, key=_state_rank)


def _primary_score(row: dict[str, Any]) -> float:
    values = [row.get("intraday_score"), row.get("swing_score"), row.get("score")]
    numbers = [float(value) for value in values if isinstance(value, int | float)]
    return max(numbers) if numbers else 0.0


def _change(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    previous_score = float(previous.get("score") or 0)
    current_score = float(current.get("score") or 0)
    score_delta = round(current_score - previous_score, 2)
    previous_state = str(previous.get("state") or "unknown")
    current_state = str(current.get("state") or "unknown")
    rank_delta = _state_rank(current_state) - _state_rank(previous_state)
    flags = _change_flags(
        previous=previous,
        current=current,
        previous_state=previous_state,
        current_state=current_state,
        score_delta=score_delta,
        rank_delta=rank_delta,
    )
    return {
        "ticker": current["ticker"],
        "lanes": current.get("lanes") or [],
        "previous_state": previous_state,
        "current_state": current_state,
        "previous_score": previous_score,
        "current_score": current_score,
        "score_delta": score_delta,
        "state_rank_delta": rank_delta,
        "change_flags": flags,
        "data_quality": current.get("data_quality") or {},
        "confidence": current.get("confidence"),
        "gap_basis": current.get("gap_basis"),
        "as_of_et": current.get("as_of_et"),
    }


def _change_flags(
    *,
    previous: dict[str, Any],
    current: dict[str, Any],
    previous_state: str,
    current_state: str,
    score_delta: float,
    rank_delta: int,
) -> list[str]:
    flags: list[str] = []
    if current_state != previous_state:
        if rank_delta > 0:
            flags.append("state_upgraded")
        elif rank_delta < 0:
            flags.append("state_downgraded")
        else:
            flags.append("state_changed")
    if score_delta >= 15:
        flags.append("score_improved")
    elif score_delta <= -15:
        flags.append("score_deteriorated")
    if _is_caveated(current) and not _is_caveated(previous):
        flags.append("data_caveat")
    elif _is_caveated(previous) and not _is_caveated(current):
        flags.append("data_quality_improved")
    if not flags:
        flags.append("no_material_change")
    return flags


def _change_bucket(change: dict[str, Any]) -> str:
    flags = set(change.get("change_flags") or [])
    if flags & {"state_downgraded", "score_deteriorated", "data_caveat"}:
        return "downgraded"
    if flags & {"state_upgraded", "score_improved", "data_quality_improved"}:
        return "upgraded"
    return "unchanged"


def _is_caveated(row: dict[str, Any]) -> bool:
    quality = row.get("data_quality") if isinstance(row.get("data_quality"), dict) else {}
    confidence = quality.get("confidence") or row.get("confidence")
    data_status = quality.get("data_status")
    provider_failures = quality.get("provider_failures")
    return (
        confidence not in {None, "OK"}
        or data_status in {"stale", "provider_failure", "no_providers"}
        or bool(provider_failures)
    )


def _data_caveats(rows: Any) -> list[str]:
    caveats = []
    for row in rows:
        if not isinstance(row, dict) or not _is_caveated(row):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        quality = row.get("data_quality") if isinstance(row.get("data_quality"), dict) else {}
        confidence = quality.get("confidence") or row.get("confidence") or "unknown"
        gap_basis = quality.get("gap_basis") or row.get("gap_basis") or "unknown"
        as_of = quality.get("as_of_et") or quality.get("as_of") or row.get("as_of_et") or "unknown"
        if ticker:
            caveats.append(
                f"{ticker}: confidence={confidence} / gap_basis={gap_basis} as of {as_of}."
            )
    return caveats


def _state_rank(state: str) -> int:
    return {
        "triggered_reference": 60,
        "active_watch": 50,
        "setup_forming": 45,
        "waiting_for_turn": 40,
        "watching": 35,
        "mean_reversion_watch": 30,
        "not_in_play": 10,
        "blocked_data_quality": 0,
        "invalidated": 0,
        "unknown": 0,
    }.get(state, 20)


def _session_ids(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    session_ids = payload.get("session_ids")
    return dict(session_ids) if isinstance(session_ids, dict) else {}


def _status(current: dict[str, Any]) -> str:
    status = str(current.get("status") or "UNKNOWN")
    return status if status in {"OK", "PARTIAL", "EMPTY", "ERROR"} else "UNKNOWN"


def _one_liner(summary: dict[str, int]) -> str:
    return (
        f"{summary['new_count']} {_plural(summary['new_count'], 'new', 'new')}, "
        f"{summary['upgraded_count']} {_plural(summary['upgraded_count'], 'upgraded', 'upgraded')}, "
        f"{summary['downgraded_count']} {_plural(summary['downgraded_count'], 'downgraded', 'downgraded')}, "
        f"{summary['unchanged_count']} {_plural(summary['unchanged_count'], 'unchanged', 'unchanged')}, "
        f"{summary['removed_count']} {_plural(summary['removed_count'], 'removed', 'removed')}, "
        f"{summary['data_caveat_count']} "
        f"{_plural(summary['data_caveat_count'], 'data caveat', 'data caveats')}."
    )


def _plural(count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural
