from __future__ import annotations

from pathlib import Path
from typing import Any

from services.lance_market_scan_service import DISCLAIMER


class LanceCommandCenterService:
    """One-call Lance desk workflow: now, changes, tomorrow prep, and review loop."""

    def __init__(
        self,
        *,
        full_cycle_service: Any | None = None,
        tracker_service: Any | None = None,
        data_doctor_service: Any | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        if full_cycle_service is None:
            from services.lance_full_cycle_service import LanceFullCycleService

            full_cycle_service = LanceFullCycleService(db_path=db_path)
        if tracker_service is None:
            from services.lance_session_tracker_service import LanceSessionTrackerService

            tracker_service = LanceSessionTrackerService()
        if data_doctor_service is None:
            from services.lance_data_doctor_service import LanceDataDoctorService

            data_doctor_service = LanceDataDoctorService()

        self.full_cycle_service = full_cycle_service
        self.tracker_service = tracker_service
        self.data_doctor_service = data_doctor_service

    def run(
        self,
        *,
        tickers: list[str] | str | None = None,
        universe: str | list[str] | None = None,
        watchlist: str | list[str] | None = None,
        all_universes: bool = False,
        min_gap_abs: float = 3.0,
        max_candidates: int = 20,
        persist: bool = True,
        session_id: str | None = None,
        swing_session_id: str | None = None,
        max_workers: int = 6,
        include_caveated_context: bool | None = None,
        lookback_days: int = 60,
        update_limit: int = 50,
        review_limit: int = 500,
        target_session_date: str | None = None,
        summary_limit: int = 5,
        previous: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        full_cycle = self.full_cycle_service.run(
            tickers=tickers,
            universe=universe,
            watchlist=watchlist,
            all_universes=all_universes,
            min_gap_abs=min_gap_abs,
            max_candidates=max_candidates,
            persist=persist,
            session_id=session_id,
            swing_session_id=swing_session_id,
            max_workers=max_workers,
            include_caveated_context=include_caveated_context,
            lookback_days=lookback_days,
            update_limit=update_limit,
            review_limit=review_limit,
            target_session_date=target_session_date,
            summary_limit=summary_limit,
        )
        normalized_previous = _previous_full_cycle(previous)
        tracker = (
            self.tracker_service.diff(previous=normalized_previous, current=full_cycle)
            if previous is not None
            else None
        )
        signal_quality = _signal_quality(full_cycle)
        data_doctor = self.data_doctor_service.from_signal_quality(signal_quality)
        session_ids = _session_ids(full_cycle)
        data_used = _data_used(full_cycle)
        return {
            "agent_name": "lance_full_cycle",
            "mode": "command_center",
            "strategy": "Lance command center single-run workflow",
            "status": str(full_cycle.get("status") or "UNKNOWN"),
            "session_ids": session_ids,
            "single_run_read": _single_run_read(full_cycle, signal_quality),
            "tracker": tracker,
            "signal_quality": signal_quality,
            "data_used": data_used,
            "data_doctor": data_doctor,
            "tomorrow_prep": _tomorrow_prep(full_cycle),
            "outcome_loop": _outcome_loop(full_cycle),
            "workflow_commands": _workflow_commands(
                tickers=tickers,
                universe=universe,
                watchlist=watchlist,
                all_universes=all_universes,
                target_session_date=target_session_date,
                session_ids=session_ids,
            ),
            "agent_handoff": _agent_handoff(
                single_run_read=_single_run_read(full_cycle, signal_quality),
                session_ids=session_ids,
                data_doctor=data_doctor,
                data_used=data_used,
                outcome_loop=_outcome_loop(full_cycle),
                workflow_commands=_workflow_commands(
                    tickers=tickers,
                    universe=universe,
                    watchlist=watchlist,
                    all_universes=all_universes,
                    target_session_date=target_session_date,
                    session_ids=session_ids,
                ),
            ),
            "full_cycle": full_cycle,
            "notes": [
                "Command center composes existing Lance services; scanner numbers stay in the data layer.",
                "Carryover/tomorrow rows require a fresh scan before live use.",
            ],
            "disclaimer": full_cycle.get("disclaimer") or DISCLAIMER,
    }


def _agent_handoff(
    *,
    single_run_read: dict[str, Any],
    session_ids: dict[str, Any],
    data_doctor: dict[str, Any],
    data_used: dict[str, Any],
    outcome_loop: dict[str, Any],
    workflow_commands: dict[str, str],
) -> dict[str, Any]:
    doctor_read = data_doctor.get("doctor_read") if isinstance(data_doctor.get("doctor_read"), dict) else {}
    return {
        "summary": single_run_read.get("one_liner"),
        "session_ids": session_ids,
        "active_monitor": list(single_run_read.get("active_monitor") or []),
        "swing_watch": list(single_run_read.get("swing_watch") or []),
        "blocked_data_quality": list(single_run_read.get("blocked_data_quality") or []),
        "data_doctor": doctor_read.get("one_liner"),
        "data_used": data_used,
        "pending_review_tickers": list(outcome_loop.get("pending_review_tickers") or []),
        "next_commands": workflow_commands,
        "handoff_prompt": (
            "Use this block to brief another agent: preserve data-quality caveats, "
            "do not infer missing market numbers, and keep outcomes unknown until manual review."
        ),
    }


BENCHMARK_ORDER = ["SPY", "QQQ", "IWM", "SMH", "XLK"]


def _data_used(full_cycle: dict[str, Any]) -> dict[str, Any]:
    benchmarks = _benchmark_rows(full_cycle)
    candidate_rows = _candidate_rows(full_cycle)
    source_paths = []
    if benchmarks:
        source_paths.append("full_cycle.market_context.benchmarks")
    if candidate_rows:
        source_paths.append("full_cycle.combined_watchlist")
    return {
        "summary": f"{_phrase(len(candidate_rows), 'candidate row')}, {_phrase(len(benchmarks), 'benchmark row')}.",
        "source_paths": source_paths,
        "benchmarks": benchmarks,
        "candidate_rows": candidate_rows,
    }


def _benchmark_rows(full_cycle: dict[str, Any]) -> list[dict[str, Any]]:
    context = full_cycle.get("market_context") if isinstance(full_cycle.get("market_context"), dict) else {}
    benchmarks = context.get("benchmarks") if isinstance(context.get("benchmarks"), dict) else {}
    symbols = [symbol for symbol in BENCHMARK_ORDER if symbol in benchmarks]
    known_symbols = set(BENCHMARK_ORDER)
    symbols.extend(sorted(symbol for symbol in benchmarks if symbol not in known_symbols))
    rows = []
    for symbol in symbols:
        data = benchmarks.get(symbol)
        if not isinstance(data, dict):
            continue
        rows.append({
            "ticker": symbol,
            "gap_pct": data.get("gap_pct"),
            "gap_basis": data.get("gap_basis"),
            "confidence": data.get("confidence"),
            "as_of": data.get("as_of") or data.get("as_of_et"),
            "sources": list(data.get("sources") or []),
        })
    return rows


def _candidate_rows(full_cycle: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in full_cycle.get("combined_watchlist") or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        quality = row.get("data_quality") if isinstance(row.get("data_quality"), dict) else {}
        rows.append({
            "ticker": ticker,
            "intraday_state": row.get("intraday_state"),
            "swing_state": row.get("swing_state"),
            "intraday_playbook": row.get("intraday_playbook"),
            "swing_playbook": row.get("swing_playbook"),
            "latest_price": quality.get("latest_price"),
            "gap_pct": quality.get("gap_pct"),
            "gap_basis": quality.get("gap_basis"),
            "confidence": quality.get("confidence"),
            "data_status": quality.get("data_status"),
            "rel_volume": quality.get("rel_volume"),
            "volume": quality.get("volume"),
            "as_of": quality.get("as_of"),
            "as_of_et": quality.get("as_of_et"),
            "sources": list(quality.get("sources") or []),
            "data_caveat": quality.get("data_caveat"),
        })
    return rows


def _single_run_read(
    full_cycle: dict[str, Any],
    signal_quality: list[dict[str, Any]],
) -> dict[str, Any]:
    active = [row["ticker"] for row in signal_quality if row["posture"] == "active_monitor"]
    swing = [row["ticker"] for row in signal_quality if row["posture"] == "swing_watch"]
    blocked = [
        row["ticker"] for row in signal_quality if row["posture"] == "blocked_data_quality"
    ]
    pending_count = len(full_cycle.get("pending_reviews") or [])
    return {
        "one_liner": (
            f"{_phrase(len(active), 'active monitor')}, "
            f"{_phrase(len(swing), 'swing watch')}, "
            f"{_phrase(len(blocked), 'blocked/data-caveat')}, "
            f"{_phrase(pending_count, 'pending review')}."
        ),
        "active_monitor": active,
        "swing_watch": swing,
        "blocked_data_quality": blocked,
        "pending_review_count": pending_count,
        "desk_read": full_cycle.get("desk_read") or {},
    }


def _previous_full_cycle(previous: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(previous, dict):
        return None
    nested = previous.get("full_cycle")
    if previous.get("mode") == "command_center" and isinstance(nested, dict):
        return nested
    return previous


def _signal_quality(full_cycle: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for row in full_cycle.get("combined_watchlist") or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        quality = row.get("data_quality") if isinstance(row.get("data_quality"), dict) else {}
        state = _primary_state(row)
        posture = _posture(row, quality, state)
        confidence = quality.get("confidence")
        gap_basis = quality.get("gap_basis")
        as_of = quality.get("as_of_et") or quality.get("as_of")
        output.append({
            "ticker": ticker,
            "posture": posture,
            "state": state,
            "intraday_state": row.get("intraday_state"),
            "swing_state": row.get("swing_state"),
            "rel_volume": quality.get("rel_volume"),
            "data_status": quality.get("data_status"),
            "confidence": confidence,
            "gap_basis": gap_basis,
            "as_of_et": as_of,
            "quality_reason": (
                f"confidence={_value(confidence)} / "
                f"gap_basis={_value(gap_basis)} / as_of={_value(as_of)}"
            ),
        })
    return output


def _posture(row: dict[str, Any], quality: dict[str, Any], state: str) -> str:
    if _is_caveated(quality) or "blocked" in state:
        return "blocked_data_quality"
    if row.get("intraday_state") in {
        "triggered_reference",
        "setup_forming",
        "waiting_for_turn",
        "watching",
    }:
        return "active_monitor"
    if row.get("swing_state"):
        return "swing_watch"
    return "context_watch"


def _is_caveated(quality: dict[str, Any]) -> bool:
    return (
        quality.get("confidence") not in {None, "OK"}
        or quality.get("data_status") in {"stale", "provider_failure", "no_providers"}
        or bool(quality.get("provider_failures"))
    )


def _primary_state(row: dict[str, Any]) -> str:
    return str(row.get("intraday_state") or row.get("swing_state") or "unknown")


def _tomorrow_prep(full_cycle: dict[str, Any]) -> dict[str, Any]:
    watchlist = []
    seen = set()
    for row in full_cycle.get("combined_watchlist") or []:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            watchlist.append(ticker)
    return {
        "fresh_scan_required": True,
        "watchlist": watchlist,
        "checklist": [
            "Run a fresh Lance full-cycle scan.",
            "Require current as-of timestamps and acceptable confidence.",
            "Use 2-minute structure before upgrading intraday names.",
            "Journal outcomes only after manual chart review.",
        ],
    }


def _outcome_loop(full_cycle: dict[str, Any]) -> dict[str, Any]:
    workflow = full_cycle.get("session_workflow") if isinstance(full_cycle.get("session_workflow"), dict) else {}
    pending = [row for row in full_cycle.get("pending_reviews") or [] if isinstance(row, dict)]
    return {
        "pending_review_count": len(pending),
        "pending_review_tickers": _pending_tickers(pending),
        "journal_commands": [_journal_command(row) for row in pending],
        "pending_reviews": pending,
        "review_command": workflow.get("review_command"),
        "journal_tool": workflow.get("journal_tool") or "journal_lance_full_cycle_outcome",
        "journal_note": (
            "Journal observed outcomes only after manual chart review; use unknown when not reviewed."
        ),
    }


def _pending_tickers(rows: list[dict[str, Any]]) -> list[str]:
    tickers = []
    seen = set()
    for row in rows:
        ticker = str(row.get("ticker") or "").strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    return tickers


def _journal_command(row: dict[str, Any]) -> str:
    lane = _value(row.get("lane"))
    ticker = _value(row.get("ticker"))
    playbook = _value(row.get("playbook"))
    return (
        "journal_lance_full_cycle_outcome "
        f"lane={lane} ticker={ticker} playbook={playbook} outcome=unknown"
    )


def _workflow_commands(
    *,
    tickers: list[str] | str | None,
    universe: str | list[str] | None,
    watchlist: str | list[str] | None,
    all_universes: bool,
    target_session_date: str | None,
    session_ids: dict[str, Any],
) -> dict[str, str]:
    selection = _selection_args(tickers=tickers, universe=universe, watchlist=watchlist, all_universes=all_universes)
    target = f" --target-session-date {target_session_date}" if target_session_date else ""
    intraday_id = session_ids.get("intraday")
    swing_id = session_ids.get("swing")
    tomorrow = ".venv/bin/python -m cli.lance_dashboard tomorrow"
    if intraday_id:
        tomorrow = f"{tomorrow} --intraday-session-id {intraday_id}"
    if swing_id:
        tomorrow = f"{tomorrow} --swing-session-id {swing_id}"
    if target_session_date:
        tomorrow = f"{tomorrow} --target-session-date {target_session_date}"
    return {
        "now": f".venv/bin/python -m cli.lance{selection}{target}",
        "watch": f".venv/bin/python -m cli.lance_full_cycle{selection} --watch 30",
        "tomorrow": tomorrow,
    }


def _selection_args(
    *,
    tickers: list[str] | str | None,
    universe: str | list[str] | None,
    watchlist: str | list[str] | None,
    all_universes: bool,
) -> str:
    parts = []
    if tickers:
        parts.append(f"--tickers {_join_values(tickers)}")
    if universe:
        parts.append(f"--universe {_join_values(universe)}")
    if watchlist:
        parts.append(f"--watchlist {_join_values(watchlist)}")
    if all_universes:
        parts.append("--full-universe")
    return "" if not parts else " " + " ".join(parts)


def _session_ids(full_cycle: dict[str, Any]) -> dict[str, Any]:
    session_ids = full_cycle.get("session_ids")
    return dict(session_ids) if isinstance(session_ids, dict) else {}


def _join_values(value: list[str] | str) -> str:
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return str(value)


def _phrase(count: int, label: str) -> str:
    plurals = {
        "active monitor": "active monitors",
        "swing watch": "swing watches",
        "blocked/data-caveat": "blocked/data-caveat names",
        "pending review": "pending reviews",
    }
    return f"{count} {label}" if count == 1 else f"{count} {plurals.get(label, f'{label}s')}"


def _value(value: Any) -> str:
    return "unknown" if value is None else str(value)
