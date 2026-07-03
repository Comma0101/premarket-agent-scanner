"""CLI: Lance live operator console."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import typer

from agent_tools.tools import run_lance_command_center


app = typer.Typer(add_completion=False, help="Run Lance as a live operator console.")

DATA_USED_ROW_LIMIT = 6
BENCHMARK_ORDER = ["SPY", "QQQ", "IWM", "SMH", "XLK"]


@app.command()
def main(
    tickers: str | None = typer.Option(None, "--tickers", "-t", help="Tickers, comma-separated."),
    universe: str | None = typer.Option(None, "--universe", "-u", help="Universe name(s)."),
    watchlist: str | None = typer.Option(None, "--watchlist", "-w", help="Watchlist name(s)."),
    all_universes: bool = typer.Option(
        False,
        "--all-universes",
        "--all",
        "--full-universe",
        help="Use every configured universe.",
    ),
    min_gap_abs: float = typer.Option(3.0, "--min-gap-abs", help="Intraday minimum move %."),
    max_candidates: int = typer.Option(20, "--max-candidates", help="Intraday candidate cap."),
    persist: bool = typer.Option(True, "--persist/--no-persist", help="Persist Lance session state."),
    session_id: str | None = typer.Option(None, "--session-id", help="Intraday session id."),
    swing_session_id: str | None = typer.Option(None, "--swing-session-id", help="Swing session id."),
    max_workers: int = typer.Option(6, "--max-workers", help="Bounded scanner worker count."),
    include_caveated_context: bool | None = typer.Option(
        None,
        "--include-caveated-context/--exclude-caveated-context",
        help="Allow stale/conflict/low-confidence names as blocked context rows.",
    ),
    lookback_days: int = typer.Option(60, "--lookback-days", help="Swing daily bars to request."),
    update_limit: int = typer.Option(50, "--update-limit", help="Intraday rows to update."),
    review_limit: int = typer.Option(500, "--review-limit", help="Review/carryover rows."),
    target_session_date: str | None = typer.Option(
        None,
        "--target-session-date",
        help="Target date for carryover prep.",
    ),
    summary_limit: int = typer.Option(5, "--summary-limit", help="Rows per summary section."),
    handoff_dir: Path = typer.Option(
        Path("data/live_sessions"),
        "--handoff-dir",
        help="Directory for latest_agent_handoff.md.",
    ),
    write_handoff: bool = typer.Option(
        True,
        "--write-handoff/--no-write-handoff",
        help="Write agent handoff markdown and JSON artifacts after each run.",
    ),
    previous_json: Path | None = typer.Option(
        None,
        "--previous-json",
        help="Optional previous command-center/full-cycle JSON payload for change tracking.",
    ),
    watch: float | None = typer.Option(
        None,
        "--watch",
        min=0.0,
        help="Re-run Lance live every N seconds.",
    ),
    watch_iterations: int | None = typer.Option(
        None,
        "--watch-iterations",
        min=1,
        hidden=True,
        help="Bounded watch iterations for tests/smoke runs.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    if not any([tickers, universe, watchlist, all_universes]):
        all_universes = True
    if all_universes and include_caveated_context is None:
        include_caveated_context = True
    if watch is not None and json_output:
        typer.echo("--json cannot be combined with --watch")
        raise typer.Exit(code=2)

    run_kwargs = {
        "tickers": tickers,
        "universe": universe,
        "watchlist": watchlist,
        "all_universes": all_universes,
        "min_gap_abs": min_gap_abs,
        "max_candidates": max_candidates,
        "persist": persist,
        "session_id": session_id,
        "swing_session_id": swing_session_id,
        "max_workers": max_workers,
        "include_caveated_context": include_caveated_context,
        "lookback_days": lookback_days,
        "update_limit": update_limit,
        "review_limit": review_limit,
        "target_session_date": target_session_date,
        "summary_limit": summary_limit,
    }
    previous = _load_previous(previous_json)
    if watch is not None:
        _run_watch(
            run_kwargs=run_kwargs,
            previous=previous,
            interval_seconds=watch,
            watch_iterations=watch_iterations,
            handoff_dir=handoff_dir,
            write_handoff=write_handoff,
        )
        return

    payload = run_lance_command_center(**run_kwargs, previous=previous)
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render(payload, handoff_dir=handoff_dir, write_handoff=write_handoff)


def _run_watch(
    *,
    run_kwargs: dict[str, Any],
    previous: dict[str, Any] | None,
    interval_seconds: float,
    watch_iterations: int | None,
    handoff_dir: Path,
    write_handoff: bool,
) -> None:
    typer.echo(f"Lance Live Watch: every {interval_seconds:g} seconds")
    current_previous = previous
    iteration = 0
    try:
        while watch_iterations is None or iteration < watch_iterations:
            iteration += 1
            _section(f"Cycle {iteration}")
            typer.echo("phase=running_lance_command_center")
            payload = run_lance_command_center(**run_kwargs, previous=current_previous)
            _render(payload, handoff_dir=handoff_dir, write_handoff=write_handoff)
            current_previous = payload
            if watch_iterations is not None and iteration >= watch_iterations:
                break
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        typer.echo("")
        typer.echo("Watch stopped.")


def _render(payload: dict[str, Any], *, handoff_dir: Path, write_handoff: bool) -> None:
    _section("Lance Live Operator")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    _render_session(payload)
    _render_buckets(payload)
    _render_data_used(payload)
    _render_changes(payload)
    _render_data_doctor(payload)
    _render_next_actions(payload)
    _render_outcome(payload)
    _render_handoff(payload)
    if write_handoff:
        handoff_path = _write_handoff(payload, handoff_dir=handoff_dir)
        json_path = _write_payload_json(payload, handoff_dir=handoff_dir)
        typer.echo(f"Handoff written: {handoff_path}")
        typer.echo(f"JSON written: {json_path}")
    disclaimer = str(payload.get("disclaimer") or "")
    if disclaimer:
        typer.echo("")
        typer.echo(disclaimer)


def _render_session(payload: dict[str, Any]) -> None:
    _section("Session")
    session_ids = payload.get("session_ids") if isinstance(payload.get("session_ids"), dict) else {}
    typer.echo(f"intraday={_value(session_ids.get('intraday'))}")
    typer.echo(f"swing={_value(session_ids.get('swing'))}")
    read = payload.get("single_run_read") if isinstance(payload.get("single_run_read"), dict) else {}
    if read.get("one_liner"):
        typer.echo(_value(read.get("one_liner")))


def _render_buckets(payload: dict[str, Any]) -> None:
    read = payload.get("single_run_read") if isinstance(payload.get("single_run_read"), dict) else {}
    _section("Buckets")
    typer.echo(f"Active Monitor: {_join(read.get('active_monitor') or [])}")
    typer.echo(f"Swing Watch: {_join(read.get('swing_watch') or [])}")
    typer.echo(f"Blocked/Data Caveat: {_join(read.get('blocked_data_quality') or [])}")


def _render_data_used(payload: dict[str, Any]) -> None:
    lines = _data_used_lines(payload)
    if not lines:
        return
    _section("Data Lance Used")
    for line in lines:
        typer.echo(line)


def _render_changes(payload: dict[str, Any]) -> None:
    tracker = payload.get("tracker") if isinstance(payload.get("tracker"), dict) else None
    if not tracker:
        return
    _section("Changes Since Last Run")
    if tracker.get("one_liner"):
        typer.echo(_value(tracker.get("one_liner")))


def _render_data_doctor(payload: dict[str, Any]) -> None:
    doctor = payload.get("data_doctor") if isinstance(payload.get("data_doctor"), dict) else {}
    _section("Blocked / Data Doctor")
    doctor_read = doctor.get("doctor_read") if isinstance(doctor.get("doctor_read"), dict) else {}
    if doctor_read.get("one_liner"):
        typer.echo(_value(doctor_read.get("one_liner")))
    root_causes = doctor.get("root_causes") if isinstance(doctor.get("root_causes"), dict) else {}
    for key in ["provider_failure", "missing_price", "stale_or_off_session", "halted", "confidence", "unknown"]:
        values = root_causes.get(key) if isinstance(root_causes.get(key), list) else []
        if values:
            typer.echo(f"{key}: {_join(values)}")
    for action in doctor.get("next_actions") or []:
        typer.echo(f"- {_value(action)}")


def _render_next_actions(payload: dict[str, Any]) -> None:
    workflow_commands = payload.get("workflow_commands")
    if not isinstance(workflow_commands, dict) or not workflow_commands:
        handoff = payload.get("agent_handoff") if isinstance(payload.get("agent_handoff"), dict) else {}
        workflow_commands = handoff.get("next_commands") if isinstance(handoff.get("next_commands"), dict) else {}
    if not workflow_commands:
        return
    _section("Next Actions")
    for key in ["now", "watch", "tomorrow", "review"]:
        if key in workflow_commands:
            typer.echo(f"{key}={_value(workflow_commands.get(key))}")
    for key, value in workflow_commands.items():
        if key not in {"now", "watch", "tomorrow", "review"}:
            typer.echo(f"{key}={_value(value)}")


def _render_outcome(payload: dict[str, Any]) -> None:
    outcome = payload.get("outcome_loop") if isinstance(payload.get("outcome_loop"), dict) else {}
    _section("Outcome Queue")
    typer.echo(f"pending_review_count={_value(outcome.get('pending_review_count'))}")
    if outcome.get("pending_review_tickers"):
        typer.echo(f"pending_review_tickers={_join(outcome.get('pending_review_tickers'))}")
    if outcome.get("review_command"):
        typer.echo(f"review_command={_value(outcome.get('review_command'))}")
    for command in outcome.get("journal_commands") or []:
        typer.echo(f"journal_command={_value(command)}")


def _render_handoff(payload: dict[str, Any]) -> None:
    handoff = payload.get("agent_handoff") if isinstance(payload.get("agent_handoff"), dict) else {}
    _section("Agent Handoff")
    if not handoff:
        typer.echo("- none")
        return
    for key in ["summary", "active_monitor", "swing_watch", "blocked_data_quality", "data_doctor"]:
        value = handoff.get(key)
        typer.echo(f"{key}={_join(value) if isinstance(value, list) else _value(value)}")


def _write_handoff(payload: dict[str, Any], *, handoff_dir: Path) -> Path:
    handoff_dir.mkdir(parents=True, exist_ok=True)
    path = handoff_dir / "latest_agent_handoff.md"
    path.write_text(_handoff_markdown(payload), encoding="utf-8")
    return path


def _write_payload_json(payload: dict[str, Any], *, handoff_dir: Path) -> Path:
    handoff_dir.mkdir(parents=True, exist_ok=True)
    path = handoff_dir / "latest_command_center.json"
    content = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
    path.write_text(content, encoding="utf-8")
    return path


def _handoff_markdown(payload: dict[str, Any]) -> str:
    handoff = payload.get("agent_handoff") if isinstance(payload.get("agent_handoff"), dict) else {}
    session_ids = handoff.get("session_ids") if isinstance(handoff.get("session_ids"), dict) else {}
    commands = handoff.get("next_commands") if isinstance(handoff.get("next_commands"), dict) else {}
    doctor = payload.get("data_doctor") if isinstance(payload.get("data_doctor"), dict) else {}
    doctor_read = doctor.get("doctor_read") if isinstance(doctor.get("doctor_read"), dict) else {}
    root_causes = doctor.get("root_causes") if isinstance(doctor.get("root_causes"), dict) else {}
    lines = [
        "# Lance Agent Handoff",
        "",
        f"summary: {_value(handoff.get('summary'))}",
        f"intraday_session_id: {_value(session_ids.get('intraday'))}",
        f"swing_session_id: {_value(session_ids.get('swing'))}",
        f"active_monitor: {_join(handoff.get('active_monitor') or [])}",
        f"swing_watch: {_join(handoff.get('swing_watch') or [])}",
        f"blocked_data_quality: {_join(handoff.get('blocked_data_quality') or [])}",
        f"data_doctor: {_value(handoff.get('data_doctor'))}",
        f"pending_review_tickers: {_join(handoff.get('pending_review_tickers') or [])}",
        "",
        "## Data Lance Used",
    ]
    data_used = _data_used_lines(payload)
    lines.extend(data_used or ["none"])
    lines.extend(
        [
            "",
            "## Data Doctor",
            f"summary: {_value(doctor_read.get('one_liner') or handoff.get('data_doctor'))}",
        ]
    )
    for key in ["provider_failure", "missing_price", "stale_or_off_session", "halted", "confidence", "unknown"]:
        values = root_causes.get(key) if isinstance(root_causes.get(key), list) else []
        if values:
            lines.append(f"{key}: {_join(values)}")
    for action in doctor.get("next_actions") or []:
        lines.append(f"next_action: {_value(action)}")
    lines.extend(
        [
            "",
            "## Agent Task Prompt",
            "Use latest_command_center.json as the source of truth before rerunning scans. "
            "Preserve data-quality caveats, inspect blocked names first, then continue Lance's "
            "watch-cycle from the active_monitor and swing_watch lists.",
            "",
            "## Next Commands",
        ]
    )
    for key, value in commands.items():
        lines.append(f"{key}: {_value(value)}")
    if handoff.get("handoff_prompt"):
        lines.extend(["", f"handoff_prompt: {_value(handoff.get('handoff_prompt'))}"])
    disclaimer = str(payload.get("disclaimer") or "")
    if disclaimer:
        lines.extend(["", disclaimer])
    return "\n".join(lines) + "\n"


def _data_used_lines(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    benchmark_lines = _benchmark_lines(payload)
    if benchmark_lines:
        lines.extend(benchmark_lines)
    rows = _candidate_evidence_rows(payload)
    if rows:
        for row in rows[:DATA_USED_ROW_LIMIT]:
            lines.append(_format_candidate_evidence(row))
        remaining = len(rows) - DATA_USED_ROW_LIMIT
        if remaining > 0:
            lines.append(f"... {remaining} more row(s) in latest_command_center.json")
    return lines


def _benchmark_lines(payload: dict[str, Any]) -> list[str]:
    full_cycle = payload.get("full_cycle") if isinstance(payload.get("full_cycle"), dict) else {}
    context = full_cycle.get("market_context") if isinstance(full_cycle.get("market_context"), dict) else {}
    benchmarks = context.get("benchmarks") if isinstance(context.get("benchmarks"), dict) else {}
    symbols = [symbol for symbol in BENCHMARK_ORDER if symbol in benchmarks]
    known_symbols = set(BENCHMARK_ORDER)
    symbols.extend(sorted(symbol for symbol in benchmarks if symbol not in known_symbols))
    return [_format_benchmark(symbol, benchmarks[symbol]) for symbol in symbols[:5] if isinstance(benchmarks[symbol], dict)]


def _candidate_evidence_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    full_cycle = payload.get("full_cycle") if isinstance(payload.get("full_cycle"), dict) else {}
    for key in ["combined_watchlist", "top_intraday_watchlist", "top_swing_watchlist", "top_updates"]:
        rows = full_cycle.get(key)
        if isinstance(rows, list) and rows:
            return [row for row in rows if isinstance(row, dict)]
    return []


def _format_benchmark(symbol: str, data: dict[str, Any]) -> str:
    sources = _format_sources(data.get("sources"))
    return (
        f"{symbol}: gap={_format_pct(data.get('gap_pct'))} "
        f"basis={_value(data.get('gap_basis'))} "
        f"confidence={_value(data.get('confidence'))} "
        f"as_of={_value(data.get('as_of') or data.get('as_of_et'))} "
        f"sources={sources}"
    )


def _format_candidate_evidence(row: dict[str, Any]) -> str:
    data_quality = row.get("data_quality") if isinstance(row.get("data_quality"), dict) else {}
    parts = [
        _value(row.get("ticker")),
        f"intraday={_value(row.get('intraday_state') or row.get('state'))}",
        f"swing={_value(row.get('swing_state'))}",
        f"playbook={_value(row.get('intraday_playbook') or row.get('playbook') or row.get('swing_playbook'))}",
        f"price={_format_price(data_quality.get('latest_price'))}",
        f"gap={_format_pct(data_quality.get('gap_pct'))}",
        f"rvol={_format_multiple(data_quality.get('rel_volume'))}",
        f"basis={_value(data_quality.get('gap_basis'))}",
        f"confidence={_value(data_quality.get('confidence'))}",
        f"status={_value(data_quality.get('data_status'))}",
        f"as_of={_value(data_quality.get('as_of_et') or data_quality.get('as_of'))}",
        f"sources={_format_sources(data_quality.get('sources'))}",
    ]
    caveat = data_quality.get("data_caveat")
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


def _load_previous(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    with path.open("r", encoding="utf-8") as handle:
        parsed = json.load(handle)
    return parsed if isinstance(parsed, dict) else None


def _section(title: str) -> None:
    typer.echo("")
    typer.echo(title)


def _join(values: Any) -> str:
    if not isinstance(values, list) or not values:
        return "none"
    return ", ".join(_value(value) for value in values)


def _value(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


if __name__ == "__main__":
    app()
