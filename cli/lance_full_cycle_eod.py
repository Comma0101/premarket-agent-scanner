"""CLI: review and journal Lance full-cycle sessions."""

from __future__ import annotations

import json
from typing import Any

import typer

from agent_tools.tools import (
    journal_lance_full_cycle_outcome,
    review_lance_full_cycle,
)


app = typer.Typer(add_completion=False, help="Review and journal Lance full-cycle sessions.")


@app.command("review")
def review_command(
    intraday_session_id: str | None = typer.Option(
        None,
        "--intraday-session-id",
        help="Intraday Lance session id.",
    ),
    swing_session_id: str | None = typer.Option(
        None,
        "--swing-session-id",
        help="Swing Lance session id.",
    ),
    limit: int = typer.Option(500, "--limit", help="Maximum timeline events per lane."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    payload = review_lance_full_cycle(
        intraday_session_id=intraday_session_id,
        swing_session_id=swing_session_id,
        limit=limit,
    )
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_review(payload)


@app.command("journal")
def journal_command(
    lane: str = typer.Option(..., "--lane", help="intraday or swing."),
    ticker: str = typer.Option(..., "--ticker", help="Ticker to journal."),
    playbook: str = typer.Option(..., "--playbook", help="Playbook name."),
    outcome: str = typer.Option(..., "--outcome", help="worked, failed, chop, reversed, unknown."),
    session_id: str | None = typer.Option(None, "--session-id", help="Session id."),
    notes: str | None = typer.Option(None, "--notes", help="Manual review notes."),
    plan_json: str | None = typer.Option(None, "--plan-json", help="Optional plan JSON."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    payload = journal_lance_full_cycle_outcome(
        lane=lane,
        session_id=session_id,
        ticker=ticker,
        playbook=playbook,
        outcome=outcome,
        notes=notes,
        plan=_parse_plan_json(plan_json),
    )
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_journal(payload)


def _render_review(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Lance Full-Cycle EOD Review")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    session_ids = payload.get("session_ids") or {}
    typer.echo(
        f"sessions: intraday={_value(session_ids.get('intraday'))} "
        f"swing={_value(session_ids.get('swing'))}"
    )
    summary = payload.get("summary") or {}
    typer.echo(" ".join(f"{key}={_value(value)}" for key, value in summary.items()))
    typer.echo("")
    typer.echo("Journal Queue:")
    queue = payload.get("journal_queue") or []
    if not queue:
        typer.echo("- none")
    for row in queue:
        typer.echo(
            " ".join([
                f"- {_value(row.get('lane'))}",
                f"{_value(row.get('ticker'))}",
                f"latest_state={_value(row.get('latest_state'))}",
                f"playbook={_value(row.get('playbook'))}",
                f"suggested_outcome={_value(row.get('suggested_outcome'))}",
            ])
        )
    _render_notes(payload.get("notes") or [])
    _render_disclaimer(payload)


def _render_journal(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Recorded Full-Cycle Outcome")
    if payload.get("error"):
        typer.echo(f"error={payload['error']}")
        return
    journal = payload.get("journal") or {}
    if journal.get("error"):
        typer.echo(f"error={journal['error']}")
        return
    recorded = journal.get("recorded") or {}
    typer.echo(
        f"lane={_value(payload.get('lane'))} "
        f"{_value(recorded.get('ticker'))} "
        f"outcome={_value(recorded.get('outcome'))} "
        f"playbook={_value(recorded.get('playbook'))} "
        f"session_id={_value(recorded.get('session_id'))}"
    )
    _render_disclaimer(payload)


def _parse_plan_json(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise typer.BadParameter("--plan-json must decode to an object")
    return parsed


def _render_notes(notes: list[str]) -> None:
    if not notes:
        return
    typer.echo("")
    typer.echo("Notes:")
    for note in notes:
        typer.echo(f"- {_value(note)}")


def _render_disclaimer(payload: dict[str, Any]) -> None:
    disclaimer = str(payload.get("disclaimer") or "")
    if disclaimer:
        typer.echo("")
        typer.echo(disclaimer)


def _value(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


if __name__ == "__main__":
    app()
