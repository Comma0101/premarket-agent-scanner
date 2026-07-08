"""CLI: Lance end-of-day review, outcome journal, and carryover prep."""

from __future__ import annotations

import json
from typing import Any

import typer

from agent_tools.tools import (
    build_lance_carryover_plan,
    journal_lance_outcome,
    review_lance_session,
    summarize_lance_memory,
)


app = typer.Typer(add_completion=False, help="Review and close a Lance session.")

DISCLAIMER = "Matches your filter - not buy/sell advice. Verify before acting."


@app.command("review")
def review_command(
    session_id: str | None = typer.Option(None, "--session-id", help="Lance session id."),
    limit: int = typer.Option(500, "--limit", help="Maximum timeline events to review."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    payload = review_lance_session(session_id=session_id, limit=limit)
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_review(payload)


@app.command("journal")
def journal_command(
    session_id: str = typer.Option(..., "--session-id", help="Lance session id."),
    ticker: str = typer.Option(..., "--ticker", help="Ticker to journal."),
    playbook: str = typer.Option(..., "--playbook", help="Playbook name."),
    outcome: str = typer.Option(..., "--outcome", help="worked, failed, chop, reversed, unknown."),
    notes: str | None = typer.Option(None, "--notes", help="Optional human review notes."),
    plan_json: str | None = typer.Option(
        None,
        "--plan-json",
        help="Optional unified plan JSON to attach to the journaled outcome.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    plan = _parse_plan_json(plan_json)
    payload = journal_lance_outcome(
        session_id=session_id,
        ticker=ticker,
        playbook=playbook,
        outcome=outcome,
        notes=notes,
        plan=plan,
    )
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_journal(payload)


@app.command("carryover")
def carryover_command(
    session_id: str | None = typer.Option(None, "--session-id", help="Source Lance session id."),
    target_session_date: str | None = typer.Option(
        None,
        "--target-session-date",
        help="Next-session date label.",
    ),
    limit: int = typer.Option(500, "--limit", help="Maximum timeline events to inspect."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    payload = build_lance_carryover_plan(
        session_id=session_id,
        target_session_date=target_session_date,
        limit=limit,
    )
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_carryover(payload)


@app.command("memory")
def memory_command(
    session_id: str | None = typer.Option(None, "--session-id", help="Optional session filter."),
    ticker: str | None = typer.Option(None, "--ticker", help="Optional ticker filter."),
    limit: int = typer.Option(100, "--limit", help="Maximum outcome rows to summarize."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    payload = summarize_lance_memory(
        session_id=session_id,
        ticker=ticker,
        limit=limit,
    )
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_memory(payload)


def _render_review(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Lance EOD Review:")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    typer.echo(f"Session: {_value(payload.get('session_id'))}")
    typer.echo(
        f"Counts: tickers={_value(payload.get('ticker_count'))} "
        f"pending={_value(payload.get('pending_count'))} "
        f"reviewed={_value(payload.get('reviewed_count'))}"
    )
    typer.echo("")
    typer.echo("Pending Reviews:")
    pending = payload.get("pending_reviews") or []
    if not pending:
        typer.echo("- none")
    for row in pending:
        typer.echo(
            f"- {_value(row.get('ticker'))} "
            f"latest_state={_value(row.get('latest_state'))} "
            f"score_delta={_value(row.get('score_delta'))} "
            f"gap_pct_delta={_value(row.get('gap_pct_delta'))} "
            f"rel_volume_delta={_value(row.get('rel_volume_delta'))} "
            f"focus={_value(row.get('review_focus'))}"
        )
        args = row.get("journal_args") or {}
        typer.echo(
            f"  journal: session_id={_value(args.get('session_id'))} "
            f"ticker={_value(args.get('ticker'))} "
            f"playbook={_value(args.get('playbook'))} "
            f"outcome={_value(args.get('outcome'))}"
        )
    _render_notes(payload.get("notes") or [])
    _render_disclaimer(payload)


def _render_memory(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Lance Market Memory:")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    typer.echo(f"outcome_count={_value(payload.get('outcome_count'))}")
    filters = payload.get("filters") or {}
    typer.echo(
        f"filters: session_id={_value(filters.get('session_id'))} "
        f"ticker={_value(filters.get('ticker'))} limit={_value(filters.get('limit'))}"
    )
    typer.echo("")
    typer.echo("By Playbook:")
    _render_memory_rows(payload.get("by_playbook") or [], "playbook")
    typer.echo("")
    typer.echo("By Ticker:")
    _render_memory_rows(payload.get("by_ticker") or [], "ticker")
    typer.echo("")
    typer.echo("By Action Mode:")
    _render_memory_rows(payload.get("by_action_mode") or [], "action_mode")
    typer.echo("")
    typer.echo("By Alignment:")
    _render_memory_rows(payload.get("by_alignment") or [], "alignment")
    typer.echo("")
    typer.echo("By Primary Timeframe:")
    _render_memory_rows(payload.get("by_primary_timeframe") or [], "primary_timeframe")
    _render_notes(payload.get("notes") or [])
    _render_disclaimer(payload)


def _render_memory_rows(rows: list[dict[str, Any]], label: str) -> None:
    if not rows:
        typer.echo("- none")
        return
    for row in rows:
        outcomes = row.get("outcomes") or {}
        typer.echo(
            f"- {_value(row.get(label))} "
            f"total={_value(row.get('total'))} "
            f"worked={_value(outcomes.get('worked'))} "
            f"failed={_value(outcomes.get('failed'))} "
            f"chop={_value(outcomes.get('chop'))} "
            f"reversed={_value(outcomes.get('reversed'))} "
            f"unknown={_value(outcomes.get('unknown'))} "
            f"worked_rate={_value(row.get('worked_rate'))}"
        )


def _render_journal(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Recorded Outcome:")
    if payload.get("error"):
        typer.echo(f"error={payload['error']}")
        return
    recorded = payload.get("recorded") or {}
    typer.echo(
        f"{_value(recorded.get('ticker'))} "
        f"outcome={_value(recorded.get('outcome'))} "
        f"playbook={_value(recorded.get('playbook'))} "
        f"session_id={_value(recorded.get('session_id'))}"
    )
    if recorded.get("notes"):
        typer.echo(f"notes={recorded['notes']}")
    plan_summary = recorded.get("plan_summary") or {}
    if plan_summary:
        typer.echo(
            "plan_summary: "
            f"action_mode={_value(plan_summary.get('action_mode'))} "
            f"alignment={_value(plan_summary.get('alignment'))} "
            f"primary_timeframe={_value(plan_summary.get('primary_timeframe'))}"
        )
        if plan_summary.get("thesis"):
            typer.echo(f"thesis={_value(plan_summary.get('thesis'))}")
    _render_disclaimer(payload)


def _render_carryover(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Lance Carryover Plan:")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    typer.echo(
        f"source_session={_value(payload.get('source_session_id'))} "
        f"target_session={_value(payload.get('target_session_date'))} "
        f"carryover_count={_value(payload.get('carryover_count'))} "
        f"fresh_scan_required={_value(payload.get('fresh_scan_required'))}"
    )
    groups = payload.get("groups") or {}
    for group_name in ["strength_carryover", "weakness_carryover", "context_only"]:
        typer.echo("")
        typer.echo(f"{group_name}:")
        rows = groups.get(group_name) or []
        if not rows:
            typer.echo("- none")
            continue
        for row in rows:
            typer.echo(_carryover_row(row))
    _render_notes(payload.get("notes") or [])
    _render_disclaimer(payload)


def _carryover_row(row: dict[str, Any]) -> str:
    parts = [
        f"- {_value(row.get('ticker'))}",
        f"latest_state={_value(row.get('latest_state'))}",
    ]
    if row.get("gap_pct") is not None:
        parts.append(f"gap_pct={_fmt_percent(row.get('gap_pct'))}")
    if row.get("rel_volume") is not None:
        parts.append(f"rvol={_value(row.get('rel_volume'))}")
    if row.get("as_of_et") is not None:
        parts.append(f"as_of={_value(row.get('as_of_et'))}")
    if row.get("gap_basis") is not None:
        parts.append(f"gap_basis={_value(row.get('gap_basis'))}")
    if row.get("confidence") is not None:
        parts.append(f"confidence={_value(row.get('confidence'))}")
    if row.get("review_focus"):
        parts.append(f"focus={_value(row.get('review_focus'))}")
    return " ".join(parts)


def _render_notes(notes: list[str]) -> None:
    typer.echo("")
    typer.echo("Notes:")
    if not notes:
        typer.echo("- none")
        return
    for note in notes:
        typer.echo(f"- {note}")


def _render_disclaimer(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Disclaimer:")
    typer.echo(str(payload.get("disclaimer") or DISCLAIMER))


def _parse_plan_json(plan_json: str | None) -> dict[str, Any] | None:
    if not plan_json:
        return None
    try:
        parsed = json.loads(plan_json)
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid --plan-json: {exc.msg}")
        raise typer.Exit(code=2) from exc
    if not isinstance(parsed, dict):
        typer.echo("Invalid --plan-json: expected a JSON object")
        raise typer.Exit(code=2)
    return parsed


def _fmt_percent(value: Any) -> str:
    clean = _value(value)
    if clean == "unknown" or clean.endswith("%"):
        return clean
    return f"{clean}%"


def _value(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, list):
        if not value:
            return "unknown"
        return ", ".join(_value(item) for item in value)
    if isinstance(value, dict):
        if not value:
            return "unknown"
        return json.dumps(value, sort_keys=True)
    return str(value)


if __name__ == "__main__":
    app()
