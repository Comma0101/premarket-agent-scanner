"""CLI: run Lance's full intraday-plus-swing desk cycle."""

from __future__ import annotations

import json
import time
from typing import Any

import typer

from agent_tools.tools import run_lance_full_cycle
from services.lance_session_tracker_service import LanceSessionTrackerService


app = typer.Typer(add_completion=False, help="Run Lance full desk cycle.")


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
    market: str | None = typer.Option(None, "--market", help="Full-market source, e.g. us-listed."),
    market_limit: int | None = typer.Option(
        None,
        "--market-limit",
        help="Optional cap on market symbols for bounded testing.",
    ),
    min_gap_abs: float = typer.Option(3.0, "--min-gap-abs", help="Intraday minimum move %."),
    max_candidates: int = typer.Option(20, "--max-candidates", help="Intraday candidate cap."),
    persist: bool = typer.Option(False, "--persist", help="Persist intraday and swing state."),
    session_id: str | None = typer.Option(None, "--session-id", help="Intraday session id."),
    swing_session_id: str | None = typer.Option(None, "--swing-session-id", help="Swing session id."),
    max_workers: int = typer.Option(6, "--max-workers", help="Bounded scanner worker count."),
    include_caveated_context: bool = typer.Option(
        False,
        "--include-caveated-context",
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
    watch: float | None = typer.Option(
        None,
        "--watch",
        min=0.0,
        help="Re-run the full Lance cycle every N seconds and print session changes.",
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
    if not any([tickers, universe, watchlist, all_universes, market]):
        all_universes = True
    if (all_universes or market) and not any([tickers, universe, watchlist]):
        include_caveated_context = True

    if watch is not None and json_output:
        typer.echo("--json cannot be combined with --watch")
        raise typer.Exit(code=2)

    run_kwargs = {
        "tickers": tickers,
        "universe": universe,
        "watchlist": watchlist,
        "all_universes": all_universes,
        "market": market,
        "market_limit": market_limit,
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

    if watch is not None:
        _run_watch(
            run_kwargs=run_kwargs,
            interval_seconds=watch,
            watch_iterations=watch_iterations,
        )
        return

    payload = run_lance_full_cycle(
        **run_kwargs,
    )
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_readable(payload)


def _run_watch(
    *,
    run_kwargs: dict[str, Any],
    interval_seconds: float,
    watch_iterations: int | None,
) -> None:
    typer.echo(f"Full-Cycle Watch Mode: every {interval_seconds:g} seconds")
    tracker = LanceSessionTrackerService()
    previous: dict[str, Any] | None = None
    iteration = 0
    try:
        while watch_iterations is None or iteration < watch_iterations:
            iteration += 1
            payload = run_lance_full_cycle(**run_kwargs)
            _section(f"Watch Cycle {iteration}")
            if previous is None:
                _render_readable(payload)
            else:
                _render_tracker(tracker.diff(previous=previous, current=payload))
            previous = payload
            if watch_iterations is not None and iteration >= watch_iterations:
                break
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        typer.echo("")
        typer.echo("Watch stopped.")


def _render_readable(payload: dict[str, Any]) -> None:
    _section("Lance Full Cycle")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    session_ids = payload.get("session_ids") or {}
    typer.echo(
        f"sessions: intraday={_value(session_ids.get('intraday'))} "
        f"swing={_value(session_ids.get('swing'))}"
    )
    _render_session_workflow(payload.get("session_workflow") or {})
    _render_summary(payload.get("summary") or {})
    _render_desk_read(payload.get("desk_read") or {})
    _render_combined(payload.get("combined_watchlist") or [])
    _render_section_rows("Top Intraday", payload.get("top_intraday_watchlist") or [])
    _render_section_rows("Top Swing", payload.get("top_swing_watchlist") or [])
    _render_swing_carryover(
        payload.get("swing_carryover_groups") or {},
        payload.get("swing_carryover_summary") or {},
    )
    disclaimer = str(payload.get("disclaimer") or "")
    if disclaimer:
        typer.echo("")
        typer.echo(disclaimer)


def _render_summary(summary: dict[str, Any]) -> None:
    _section("Summary")
    if not summary:
        typer.echo("- unknown")
        return
    typer.echo(" ".join(f"{key}={_value(value)}" for key, value in summary.items()))


def _render_session_workflow(workflow: dict[str, Any]) -> None:
    _section("Session Workflow")
    if not workflow:
        typer.echo("- unknown")
        return
    typer.echo(
        " ".join([
            f"persisted={_value(workflow.get('persisted'))}",
            f"full_universe={_value(workflow.get('full_universe'))}",
            f"include_caveated_context={_value(workflow.get('include_caveated_context'))}",
            f"review_tool={_value(workflow.get('review_tool'))}",
            f"journal_tool={_value(workflow.get('journal_tool'))}",
        ])
    )
    if workflow.get("triage_mode") or workflow.get("swing_scope"):
        typer.echo(
            " ".join([
                f"triage_mode={_value(workflow.get('triage_mode'))}",
                f"swing_scope={_value(workflow.get('swing_scope'))}",
                f"swing_scope_count={_value(workflow.get('swing_scope_count'))}",
            ])
        )
        if workflow.get("triage_note"):
            typer.echo(f"triage_note={_value(workflow.get('triage_note'))}")
    if workflow.get("review_command"):
        typer.echo(f"review_command={_value(workflow.get('review_command'))}")
    if workflow.get("journal_note"):
        typer.echo(f"journal_note={_value(workflow.get('journal_note'))}")


def _render_desk_read(desk_read: dict[str, Any]) -> None:
    _section("Desk Read")
    if not desk_read:
        typer.echo("- unknown")
        return
    if desk_read.get("one_liner"):
        typer.echo(_value(desk_read.get("one_liner")))
    for label in ["intraday_focus", "swing_watch", "blocked_data_quality", "swing_carryover"]:
        rows = desk_read.get(label) or []
        tickers = [_value(row.get("ticker")) for row in rows if isinstance(row, dict)]
        typer.echo(f"{label}: {','.join(tickers) if tickers else 'none'}")
    notes = desk_read.get("workflow_notes") or []
    for note in notes:
        typer.echo(f"- {_value(note)}")


def _render_combined(rows: list[dict[str, Any]]) -> None:
    _section("Combined Lance Watchlist")
    if not rows:
        typer.echo("- none")
        return
    for row in rows:
        data_quality = row.get("data_quality") or {}
        lanes = row.get("lanes")
        lane_text = ",".join(lanes) if isinstance(lanes, list) else _value(lanes)
        typer.echo(
            " ".join([
                f"- {_value(row.get('ticker'))}",
                f"lanes={lane_text}",
                f"intraday_state={_value(row.get('intraday_state'))}",
                f"swing_state={_value(row.get('swing_state'))}",
                f"as_of={_value(data_quality.get('as_of_et') or data_quality.get('as_of'))}",
                f"gap_basis={_value(data_quality.get('gap_basis'))}",
                f"confidence={_value(data_quality.get('confidence'))}",
            ])
        )


def _render_section_rows(title: str, rows: list[dict[str, Any]]) -> None:
    _section(title)
    if not rows:
        typer.echo("- none")
        return
    for row in rows:
        typer.echo(
            " ".join([
                f"- {_value(row.get('ticker'))}",
                f"state={_value(row.get('state') or row.get('current_state'))}",
                f"score={_value(row.get('score'))}",
            ])
        )


def _render_swing_carryover(
    groups: dict[str, list[dict[str, Any]]],
    summary: dict[str, Any],
) -> None:
    _section("Swing Carryover")
    if summary:
        typer.echo(" ".join(f"{key}={_value(value)}" for key, value in summary.items()))
    if not groups:
        typer.echo("- none")
        return
    any_rows = False
    for name, rows in groups.items():
        if not rows:
            continue
        tickers = [_value(row.get("ticker")) for row in rows if isinstance(row, dict)]
        if tickers:
            any_rows = True
            typer.echo(f"{name}: {','.join(tickers)}")
    if not any_rows:
        typer.echo("- none")


def _render_tracker(payload: dict[str, Any]) -> None:
    _section("Lance Session Tracker")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    if payload.get("one_liner"):
        typer.echo(_value(payload.get("one_liner")))
    groups = payload.get("groups") if isinstance(payload.get("groups"), dict) else {}
    for name in ["new", "upgraded", "downgraded", "unchanged", "removed"]:
        _render_tracker_group(name, groups.get(name) or [])
    data_caveats = payload.get("data_caveats") if isinstance(payload.get("data_caveats"), list) else []
    if data_caveats:
        _section("Data Caveats")
        for caveat in data_caveats:
            typer.echo(f"- {_value(caveat)}")
    disclaimer = str(payload.get("disclaimer") or "")
    if disclaimer:
        typer.echo("")
        typer.echo(disclaimer)


def _render_tracker_group(name: str, rows: list[dict[str, Any]]) -> None:
    typer.echo(f"{name}:")
    if not rows:
        typer.echo("- none")
        return
    for row in rows:
        if name in {"upgraded", "downgraded", "unchanged"}:
            typer.echo(
                " ".join([
                    f"- {_value(row.get('ticker'))}",
                    f"previous_state={_value(row.get('previous_state'))}",
                    f"current_state={_value(row.get('current_state'))}",
                    f"score_delta={_value(row.get('score_delta'))}",
                    f"flags={_value(row.get('change_flags'))}",
                    f"as_of={_value(row.get('as_of_et'))}",
                    f"gap_basis={_value(row.get('gap_basis'))}",
                    f"confidence={_value(row.get('confidence'))}",
                ])
            )
            continue
        typer.echo(
            " ".join([
                f"- {_value(row.get('ticker'))}",
                f"state={_value(row.get('state'))}",
                f"score={_value(row.get('score'))}",
                f"as_of={_value(row.get('as_of_et'))}",
                f"gap_basis={_value(row.get('gap_basis'))}",
                f"confidence={_value(row.get('confidence'))}",
            ])
        )


def _section(title: str) -> None:
    typer.echo("")
    typer.echo(title)


def _value(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


if __name__ == "__main__":
    app()
