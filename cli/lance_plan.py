"""CLI: build unified Lance daily-plus-intraday plans."""

from __future__ import annotations

import json
from typing import Any

import typer

from agent_tools.tools import build_lance_unified_plan


app = typer.Typer(add_completion=False, help="Build unified Lance plans.")


@app.command()
def main(
    tickers: str = typer.Option(..., "--tickers", "-t", help="Tickers, comma-separated."),
    lookback_days: int = typer.Option(
        60,
        "--lookback-days",
        help="Daily bars to request for the swing side of the plan.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print the raw payload as JSON."),
) -> None:
    payload = build_lance_unified_plan(
        tickers=tickers,
        lookback_days=lookback_days,
    )

    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return

    _render_readable(payload)


def _render_readable(payload: dict[str, Any]) -> None:
    _section("Lance Unified Plan")
    typer.echo(f"Agent: {_value(payload.get('agent_name'))}")
    typer.echo(f"Strategy: {_value(payload.get('strategy'))}")
    typer.echo(f"Timeframe: {_value(payload.get('timeframe'))}")
    typer.echo(
        f"Plans: {_value(payload.get('plan_count'))} / tickers={_value(payload.get('ticker_count'))}"
    )
    _section("Plans")
    plans = payload.get("plans") or []
    if not plans:
        typer.echo("- none")
    for plan in plans:
        typer.echo(_plan_line(plan))
        thesis = plan.get("thesis")
        if thesis:
            typer.echo(f"  thesis: {_value(thesis)}")
        memory_line = _memory_line(plan.get("outcome_memory") or {})
        if memory_line:
            typer.echo(f"  {memory_line}")
        _render_list("waiting_for", plan.get("waiting_for") or [])
        _render_list("invalidates_if", plan.get("invalidates_if") or [])
        flags = plan.get("conflict_flags") or []
        if flags:
            _render_list("conflict_flags", flags)
    _render_disclaimer(str(payload.get("disclaimer") or ""))


def _plan_line(plan: dict[str, Any]) -> str:
    swing = plan.get("swing") or {}
    intraday = plan.get("intraday") or {}
    return " ".join([
        f"- {_value(plan.get('ticker'))}",
        f"action={_value(plan.get('action_mode'))}",
        f"alignment={_value(plan.get('alignment'))}",
        f"primary={_value(plan.get('primary_timeframe'))}",
        f"score={_value(plan.get('rank_score'))}",
        f"swing={_value(swing.get('state'))}",
        f"swing_grade={_value(swing.get('lance_quality_grade'))}",
        f"intraday={_value(intraday.get('state'))}",
        f"intraday_grade={_value(intraday.get('lance_quality_grade'))}",
    ])


def _memory_line(memory: dict[str, Any]) -> str | None:
    if not memory:
        return None
    action = memory.get("matching_action_mode") or {}
    alignment = memory.get("matching_alignment") or {}
    return " ".join([
        "memory:",
        f"status={_value(memory.get('status'))}",
        f"outcome_count={_value(memory.get('outcome_count'))}",
        f"action_mode_total={_value(action.get('total'))}",
        f"action_mode_worked_rate={_value(action.get('worked_rate'))}",
        f"alignment_total={_value(alignment.get('total'))}",
        f"alignment_worked_rate={_value(alignment.get('worked_rate'))}",
    ])


def _render_list(label: str, values: list[Any]) -> None:
    if not values:
        return
    typer.echo(f"  {label}:")
    for value in values:
        typer.echo(f"    - {_value(value)}")


def _render_disclaimer(disclaimer: str) -> None:
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
