"""CLI: Lance command center single-run workflow."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import typer

from agent_tools.tools import run_lance_command_center
from cli.lance_data_used import data_used_lines, selection_audit_lines


app = typer.Typer(add_completion=False, help="Run the Lance command center.")


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
    previous_json: Path | None = typer.Option(
        None,
        "--previous-json",
        help="Optional previous command-center/full-cycle JSON payload for change tracking.",
    ),
    watch: float | None = typer.Option(
        None,
        "--watch",
        min=0.0,
        help="Re-run Lance command center every N seconds and carry previous payload into tracking.",
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

    previous = _load_previous(previous_json)
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
    if watch is not None and json_output:
        typer.echo("--json cannot be combined with --watch")
        raise typer.Exit(code=2)
    if watch is not None:
        _run_watch(
            run_kwargs=run_kwargs,
            previous=previous,
            interval_seconds=watch,
            watch_iterations=watch_iterations,
        )
        return

    payload = run_lance_command_center(**run_kwargs, previous=previous)
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render(payload)


def _run_watch(
    *,
    run_kwargs: dict[str, Any],
    previous: dict[str, Any] | None,
    interval_seconds: float,
    watch_iterations: int | None,
) -> None:
    typer.echo(f"Lance Command Center Watch: every {interval_seconds:g} seconds")
    current_previous = previous
    iteration = 0
    try:
        while watch_iterations is None or iteration < watch_iterations:
            iteration += 1
            _section(f"Watch Cycle {iteration}")
            typer.echo("phase=running_command_center")
            payload = run_lance_command_center(**run_kwargs, previous=current_previous)
            _render(payload)
            current_previous = payload
            if watch_iterations is not None and iteration >= watch_iterations:
                break
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        typer.echo("")
        typer.echo("Watch stopped.")


def _load_previous(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    with path.open("r", encoding="utf-8") as handle:
        parsed = json.load(handle)
    return parsed if isinstance(parsed, dict) else None


def _render(payload: dict[str, Any]) -> None:
    _section("Lance Command Center")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    session_ids = payload.get("session_ids") if isinstance(payload.get("session_ids"), dict) else {}
    typer.echo(
        f"intraday={_value(session_ids.get('intraday'))} "
        f"swing={_value(session_ids.get('swing'))}"
    )

    read = payload.get("single_run_read") if isinstance(payload.get("single_run_read"), dict) else {}
    if read.get("one_liner"):
        typer.echo(_value(read.get("one_liner")))
    if payload.get("session_banner"):
        typer.echo(_value(payload.get("session_banner")))
    typer.echo(f"Active Monitor: {_join(read.get('active_monitor') or [])}")
    typer.echo(f"Swing Watch: {_join(read.get('swing_watch') or [])}")
    typer.echo(f"Blocked/Data Caveat: {_join(read.get('blocked_data_quality') or [])}")
    _render_data_used(payload)
    _render_selection_audit(payload)

    tracker = payload.get("tracker") if isinstance(payload.get("tracker"), dict) else None
    if tracker:
        _section("Session Changes")
        if tracker.get("one_liner"):
            typer.echo(_value(tracker.get("one_liner")))

    _section("Signal Quality")
    rows = payload.get("signal_quality") if isinstance(payload.get("signal_quality"), list) else []
    if not rows:
        typer.echo("- none")
    for row in rows:
        if not isinstance(row, dict):
            continue
        typer.echo(
            " ".join([
                f"- {_value(row.get('ticker'))}",
                f"posture={_value(row.get('posture'))}",
                f"state={_value(row.get('state'))}",
                f"rvol={_value(row.get('rel_volume'))}",
                f"confidence={_value(row.get('confidence'))}",
                f"gap_basis={_value(row.get('gap_basis'))}",
                f"as_of={_value(row.get('as_of_et'))}",
            ])
        )
        if row.get("quality_reason"):
            typer.echo(f"  quality={_value(row.get('quality_reason'))}")

    doctor = payload.get("data_doctor") if isinstance(payload.get("data_doctor"), dict) else {}
    _section("Data Doctor")
    doctor_read = doctor.get("doctor_read") if isinstance(doctor.get("doctor_read"), dict) else {}
    if doctor_read.get("one_liner"):
        typer.echo(_value(doctor_read.get("one_liner")))
    root_causes = doctor.get("root_causes") if isinstance(doctor.get("root_causes"), dict) else {}
    for key in [
        "provider_failure",
        "missing_price",
        "stale_or_off_session",
        "halted",
        "confidence",
        "unknown",
    ]:
        values = root_causes.get(key) if isinstance(root_causes.get(key), list) else []
        if values:
            typer.echo(f"{key}: {_join(values)}")
    next_actions = doctor.get("next_actions") if isinstance(doctor.get("next_actions"), list) else []
    for action in next_actions:
        typer.echo(f"- {_value(action)}")

    outcome = payload.get("outcome_loop") if isinstance(payload.get("outcome_loop"), dict) else {}
    _section("Outcome Loop")
    typer.echo(f"pending_review_count={_value(outcome.get('pending_review_count'))}")
    if outcome.get("pending_review_tickers"):
        typer.echo(f"pending_review_tickers={_join(outcome.get('pending_review_tickers'))}")
    if outcome.get("review_command"):
        typer.echo(f"review_command={_value(outcome.get('review_command'))}")
    if outcome.get("journal_tool"):
        typer.echo(f"journal_tool={_value(outcome.get('journal_tool'))}")
    journal_commands = outcome.get("journal_commands") if isinstance(outcome.get("journal_commands"), list) else []
    for command in journal_commands:
        typer.echo(f"journal_command={_value(command)}")
    if outcome.get("journal_note"):
        typer.echo(f"journal_note={_value(outcome.get('journal_note'))}")

    tomorrow = payload.get("tomorrow_prep") if isinstance(payload.get("tomorrow_prep"), dict) else {}
    _section("Tomorrow Prep")
    typer.echo(f"fresh_scan_required={_value(tomorrow.get('fresh_scan_required'))}")
    typer.echo(f"watchlist={_join(tomorrow.get('watchlist') or [])}")

    commands = payload.get("workflow_commands") if isinstance(payload.get("workflow_commands"), dict) else {}
    _section("Workflow Commands")
    for key in ["now", "watch", "tomorrow"]:
        if commands.get(key):
            typer.echo(f"{key}={_value(commands.get(key))}")

    handoff = payload.get("agent_handoff") if isinstance(payload.get("agent_handoff"), dict) else {}
    if handoff:
        _section("Agent Handoff")
        for key in [
            "summary",
            "active_monitor",
            "swing_watch",
            "blocked_data_quality",
            "data_doctor",
            "pending_review_tickers",
        ]:
            value = handoff.get(key)
            if isinstance(value, list):
                typer.echo(f"{key}={_join(value)}")
            elif value is not None:
                typer.echo(f"{key}={_value(value)}")
        if handoff.get("handoff_prompt"):
            typer.echo(f"handoff_prompt={_value(handoff.get('handoff_prompt'))}")

    disclaimer = str(payload.get("disclaimer") or "")
    if disclaimer:
        typer.echo("")
        typer.echo(disclaimer)


def _render_data_used(payload: dict[str, Any]) -> None:
    lines = data_used_lines(payload)
    if not lines:
        return
    _section("Data Lance Used")
    for line in lines:
        typer.echo(line)


def _render_selection_audit(payload: dict[str, Any]) -> None:
    lines = selection_audit_lines(payload)
    if not lines:
        return
    _section("Requested Ticker Coverage")
    for line in lines:
        typer.echo(line)


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
