"""CLI: run Lance's swing desk cycle."""

from __future__ import annotations

import json
from typing import Any

import typer

from agent_tools.tools import run_lance_swing_cycle


app = typer.Typer(add_completion=False, help="Run Lance swing desk cycle.")


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
    lookback_days: int = typer.Option(60, "--lookback-days", help="Daily bars to request."),
    persist: bool = typer.Option(False, "--persist", help="Persist swing cycle rows."),
    session_id: str | None = typer.Option(None, "--session-id", help="Session id to write/reuse."),
    summary_limit: int = typer.Option(10, "--summary-limit", help="Rows to print."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    if not any([tickers, universe, watchlist, all_universes]):
        all_universes = True

    payload = run_lance_swing_cycle(
        tickers=tickers,
        universe=universe,
        watchlist=watchlist,
        all_universes=all_universes,
        lookback_days=lookback_days,
        persist=persist,
        session_id=session_id,
        summary_limit=summary_limit,
    )
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_readable(payload)


def _render_readable(payload: dict[str, Any]) -> None:
    _section("Lance Swing Cycle")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    typer.echo(f"Session: {_value(payload.get('session_id'))}")
    typer.echo(
        f"selection={_value(payload.get('selection'))} "
        f"selection_count={_value(payload.get('selection_count'))}"
    )
    summary = payload.get("summary") or {}
    typer.echo(
        "summary: "
        f"plans={_value(summary.get('plan_count'))} "
        f"active={_value(summary.get('active_watch_count'))} "
        f"mean_reversion={_value(summary.get('mean_reversion_watch_count'))} "
        f"watching={_value(summary.get('watching_count'))} "
        f"invalidated={_value(summary.get('invalidated_count'))} "
        f"blocked={_value(summary.get('blocked_count'))}"
    )

    _section("Top Swing Rows")
    rows = payload.get("top_watchlist") or []
    if not rows:
        typer.echo("- none")
    for row in rows:
        typer.echo(_row_line(row))
        _render_list("waiting_for", row.get("waiting_for") or [])
        _render_list("invalidates_if", row.get("invalidates_if") or [])

    disclaimer = str(payload.get("disclaimer") or "")
    if disclaimer:
        typer.echo("")
        typer.echo(disclaimer)


def _row_line(row: dict[str, Any]) -> str:
    data_quality = row.get("data_quality") or {}
    relative_strength = row.get("relative_strength") or {}
    daily_context = row.get("daily_context") or {}
    sources = data_quality.get("sources")
    source_text = ",".join(sources) if isinstance(sources, list) else _value(sources)
    return " ".join([
        f"- {_value(row.get('ticker'))}",
        f"state={_value(row.get('state'))}",
        f"grade={_value(row.get('lance_quality_grade'))}",
        f"playbook={_value(row.get('playbook'))}",
        f"score={_value(row.get('score'))}",
        f"gap_pct={_value(data_quality.get('gap_pct'))}",
        f"rvol={_value(data_quality.get('rel_volume'))}",
        f"rs={_value(relative_strength.get('classification'))}",
        f"vs_QQQ={_value(relative_strength.get('vs_QQQ'))}",
        f"trend={_value(daily_context.get('trend'))}",
        f"structure={_value(daily_context.get('structure'))}",
        f"source={source_text}",
        f"as_of={_value(data_quality.get('as_of_et') or data_quality.get('as_of'))}",
        f"gap_basis={_value(data_quality.get('gap_basis'))}",
        f"confidence={_value(data_quality.get('confidence'))}",
    ])


def _render_list(label: str, values: list[Any]) -> None:
    if not values:
        return
    typer.echo(f"  {label}:")
    for value in values:
        typer.echo(f"    - {_value(value)}")


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
