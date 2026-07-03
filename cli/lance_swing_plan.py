"""CLI: build Lance daily/swing watch plans."""

from __future__ import annotations

import json
from typing import Any

import typer

from agent_tools.tools import build_lance_swing_plan


app = typer.Typer(add_completion=False, help="Build Lance daily/swing watch plans.")


@app.command()
def main(
    tickers: str | None = typer.Option(None, "--tickers", "-t", help="Tickers, comma-separated."),
    universe: str | None = typer.Option(None, "--universe", "-u", help="Universe name(s)."),
    watchlist: str | None = typer.Option(None, "--watchlist", "-w", help="Watchlist name(s)."),
    all_universes: bool = typer.Option(
        False,
        "--all-universes",
        "--all",
        help="Use every configured universe.",
    ),
    lookback_days: int = typer.Option(
        60,
        "--lookback-days",
        help="Daily bars to request for structure and relative-strength context.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print the raw payload as JSON."),
) -> None:
    if not any([tickers, universe, watchlist, all_universes]):
        all_universes = True

    payload = build_lance_swing_plan(
        tickers=tickers,
        universe=universe,
        watchlist=watchlist,
        all_universes=all_universes,
        lookback_days=lookback_days,
    )

    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return

    _render_readable(payload)


def _render_readable(payload: dict[str, Any]) -> None:
    _section("Lance Swing Plan")
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
        _render_list("waiting_for", plan.get("waiting_for") or [])
        _render_list("invalidates_if", plan.get("invalidates_if") or [])
    _render_disclaimer(str(payload.get("disclaimer") or ""))


def _plan_line(plan: dict[str, Any]) -> str:
    daily_context = plan.get("daily_context") or {}
    relative_strength = plan.get("relative_strength") or {}
    data_quality = plan.get("data_quality") or {}
    return " ".join([
        f"- {_value(plan.get('ticker'))}",
        f"state={_value(plan.get('state'))}",
        f"grade={_value(plan.get('lance_quality_grade'))}",
        f"playbook={_value(plan.get('playbook'))}",
        f"score={_value(plan.get('score'))}",
        f"trend={_value(daily_context.get('trend'))}",
        f"structure={_value(daily_context.get('structure'))}",
        f"rs={_value(relative_strength.get('classification'))}",
        f"vs_QQQ={_value(relative_strength.get('vs_QQQ'))}",
        f"confidence={_value(data_quality.get('confidence'))}",
        f"gap_basis={_value(data_quality.get('gap_basis'))}",
        f"as_of={_value(data_quality.get('as_of_et') or data_quality.get('as_of'))}",
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
