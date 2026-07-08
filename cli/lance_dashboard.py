"""CLI: Lance session dashboard and next-session prep."""

from __future__ import annotations

import json
from typing import Any

import typer

from agent_tools.tools import (
    build_lance_tomorrow_prep,
    get_lance_session_dashboard,
)


app = typer.Typer(add_completion=False, help="Show Lance session dashboard and tomorrow prep.")


@app.command("dashboard")
def dashboard_command(
    intraday_session_id: str | None = typer.Option(
        None,
        "--intraday-session-id",
        help="Optional intraday Lance session id.",
    ),
    swing_session_id: str | None = typer.Option(
        None,
        "--swing-session-id",
        help="Optional swing Lance session id.",
    ),
    target_session_date: str | None = typer.Option(
        None,
        "--target-session-date",
        help="Optional next-session date label.",
    ),
    limit: int = typer.Option(500, "--limit", help="Maximum review/carryover rows."),
    memory_limit: int = typer.Option(100, "--memory-limit", help="Maximum memory rows."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    payload = get_lance_session_dashboard(
        intraday_session_id=intraday_session_id,
        swing_session_id=swing_session_id,
        target_session_date=target_session_date,
        limit=limit,
        memory_limit=memory_limit,
    )
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_dashboard(payload)


@app.command("tomorrow")
def tomorrow_command(
    intraday_session_id: str | None = typer.Option(
        None,
        "--intraday-session-id",
        help="Optional intraday Lance session id.",
    ),
    swing_session_id: str | None = typer.Option(
        None,
        "--swing-session-id",
        help="Optional swing Lance session id.",
    ),
    target_session_date: str | None = typer.Option(
        None,
        "--target-session-date",
        help="Optional next-session date label.",
    ),
    limit: int = typer.Option(500, "--limit", help="Maximum review/carryover rows."),
    memory_limit: int = typer.Option(100, "--memory-limit", help="Maximum memory rows."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    payload = build_lance_tomorrow_prep(
        intraday_session_id=intraday_session_id,
        swing_session_id=swing_session_id,
        target_session_date=target_session_date,
        limit=limit,
        memory_limit=memory_limit,
    )
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_tomorrow(payload)


def _render_dashboard(payload: dict[str, Any]) -> None:
    _section("Lance Session Dashboard")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    session_ids = payload.get("session_ids") or {}
    typer.echo(
        f"intraday={_value(session_ids.get('intraday'))} "
        f"swing={_value(session_ids.get('swing'))} "
        f"target={_value(payload.get('target_session_date'))}"
    )
    summary = payload.get("summary") or {}
    typer.echo(" ".join(f"{key}={_value(value)}" for key, value in summary.items()))

    dashboard_read = payload.get("dashboard_read") if isinstance(payload.get("dashboard_read"), dict) else {}
    if dashboard_read:
        _render_dashboard_read(dashboard_read)
    else:
        buckets = payload.get("buckets") or {}
        for name in [
            "needs_manual_review",
            "relative_strength_watch",
            "swing_reclaim_watch",
            "caveated_context",
            "invalidated",
        ]:
            _render_bucket(name, buckets.get(name) or [])

    memory = payload.get("memory") or {}
    _section("Memory")
    typer.echo(
        f"status={_value(memory.get('status'))} "
        f"outcome_count={_value(memory.get('outcome_count'))}"
    )
    _render_list("next_actions", payload.get("next_actions") or [])
    _render_disclaimer(payload)


def _render_tomorrow(payload: dict[str, Any]) -> None:
    _section("Lance Tomorrow Prep")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    typer.echo(
        f"target={_value(payload.get('target_session_date'))} "
        f"fresh_scan_required={_value(payload.get('fresh_scan_required'))}"
    )
    if payload.get("what_lance_would_do_now"):
        typer.echo(_value(payload.get("what_lance_would_do_now")))

    _section("Watchlist")
    rows = payload.get("watchlist") or []
    if not rows:
        typer.echo("- none")
    for row in rows:
        typer.echo(_tomorrow_row(row))
    _render_list("confirmation_checklist", payload.get("confirmation_checklist") or [])
    _render_disclaimer(payload)


def _render_dashboard_read(read: dict[str, Any]) -> None:
    if read.get("one_liner"):
        typer.echo(_value(read.get("one_liner")))
    sections = read.get("sections") if isinstance(read.get("sections"), list) else []
    for section in sections:
        if not isinstance(section, dict):
            continue
        name = str(section.get("name") or "")
        if name == "fresh_scan_required":
            _section("Fresh Scan Required")
            tickers = _join(section.get("tickers") or [])
            typer.echo(f"tickers={tickers if tickers else 'none'}")
            if section.get("note"):
                typer.echo(_value(section.get("note")))
            continue
        if name == "manual_review_queue":
            count = _value(section.get("count"))
            tickers = _join(section.get("tickers") or [])
            typer.echo(f"Manual Review Queue: {count} item(s) - {tickers if tickers else 'none'}")
            continue
        _render_bucket(_title(name), section.get("rows") or [])
    _render_list("Data Caveats", read.get("data_caveats") or [])


def _render_bucket(name: str, rows: list[dict[str, Any]]) -> None:
    _section(name)
    if not rows:
        typer.echo("- none")
        return
    for row in rows:
        typer.echo(_dashboard_row(row))


def _dashboard_row(row: dict[str, Any]) -> str:
    return " ".join([
        f"- {_value(row.get('ticker'))}",
        f"lane={_value(row.get('lane'))}",
        f"state={_value(row.get('latest_state'))}",
        f"playbook={_value(row.get('playbook'))}",
        f"confidence={_value(row.get('confidence'))}",
        f"gap_basis={_value(row.get('gap_basis'))}",
        f"as_of={_value(row.get('as_of_et'))}",
    ])


def _tomorrow_row(row: dict[str, Any]) -> str:
    lanes = row.get("lanes")
    lane_text = ",".join(lanes) if isinstance(lanes, list) else _value(lanes)
    return " ".join([
        f"- {_value(row.get('ticker'))}",
        f"lane={lane_text}",
        f"bucket={_value(row.get('bucket'))}",
        f"state={_value(row.get('latest_state'))}",
        f"playbook={_value(row.get('playbook'))}",
        f"confidence={_value(row.get('confidence'))}",
        f"gap_basis={_value(row.get('gap_basis'))}",
        f"as_of={_value(row.get('as_of_et'))}",
    ])


def _render_list(label: str, values: list[Any]) -> None:
    if not values:
        return
    _section(label)
    for value in values:
        typer.echo(f"- {_value(value)}")


def _join(values: list[Any]) -> str:
    return ", ".join(_value(value) for value in values if value is not None)


def _title(value: str) -> str:
    return value.replace("_", " ").title()


def _render_disclaimer(payload: dict[str, Any]) -> None:
    disclaimer = str(payload.get("disclaimer") or "")
    if disclaimer:
        typer.echo("")
        typer.echo(disclaimer)


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
