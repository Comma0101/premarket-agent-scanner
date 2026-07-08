from __future__ import annotations

import json
from typing import Any

import typer

from services.sykes_live_plan_service import SykesLivePlanService


app = typer.Typer(add_completion=False, help="Tim Sykes-style live/swing watchlist.")


@app.command()
def main(
    tickers: str | None = typer.Option(None, "--tickers", "-t", help="Comma-separated tickers."),
    universe: str | None = typer.Option(None, "--universe", "-u", help="Universe name(s)."),
    watchlist: str | None = typer.Option(None, "--watchlist", "-w", help="Watchlist name(s)."),
    market: str | None = typer.Option("us-listed", "--market", help="Market source."),
    market_limit: int | None = typer.Option(None, "--market-limit", help="Limit market symbols."),
    max_workers: int | None = typer.Option(6, "--max-workers", help="Bounded scan workers."),
    include_rejected: bool = typer.Option(False, "--include-rejected", help="Include rejects."),
    live_intraday: bool = typer.Option(True, "--live-intraday/--strict-premarket"),
    summary_limit: int = typer.Option(10, "--summary-limit", help="Rows to show."),
    json_output: bool = typer.Option(False, "--json/--no-json", help="Print JSON."),
) -> None:
    output = SykesLivePlanService().run(
        tickers=tickers,
        universe=universe,
        watchlist=watchlist,
        market=market,
        market_limit=market_limit,
        max_workers=max_workers,
        include_rejected=include_rejected,
        live_intraday=live_intraday,
        summary_limit=summary_limit,
    )
    if json_output:
        typer.echo(json.dumps(output, indent=2, sort_keys=True))
        return
    _render(output)


def _render(output: dict[str, Any]) -> None:
    typer.echo("Tim Sykes Live")
    if output.get("session_banner"):
        typer.echo(str(output["session_banner"]))
    read = output.get("desk_read") if isinstance(output.get("desk_read"), dict) else {}
    if read.get("one_liner"):
        typer.echo(str(read["one_liner"]))

    _section("Auto Slices")
    for row in output.get("auto_slices") or []:
        if not isinstance(row, dict):
            continue
        typer.echo(
            " ".join([
                f"slice {_value(row.get('ticker'))}",
                _value(row.get("lane")),
                _value(row.get("state")),
                _value(row.get("setup")),
            ])
        )
        typer.echo(f"  data={_value(row.get('data'))}")
        typer.echo(f"  why={_value(row.get('why'))}")
        typer.echo(f"  watch={_value(row.get('watch'))}")
        typer.echo(f"  risk={_value(row.get('risk'))}")

    _section("Intraday")
    _rows(output.get("intraday_watchlist"))
    _section("Swing")
    _rows(output.get("swing_watchlist"))
    _section("Blocked")
    _rows(output.get("blocked"))

    scanner = output.get("scanner") if isinstance(output.get("scanner"), dict) else {}
    _section("Scanner")
    typer.echo(
        " ".join([
            f"preset={_value(scanner.get('preset'))}",
            f"candidates={_value(scanner.get('candidate_count'))}",
            f"rejected={_value(scanner.get('rejected_count'))}",
            f"live_intraday={_value(scanner.get('live_intraday'))}",
        ])
    )
    if output.get("disclaimer"):
        typer.echo(str(output["disclaimer"]))


def _rows(rows: Any) -> None:
    if not rows:
        typer.echo("- none")
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        data = row.get("data_quality") if isinstance(row.get("data_quality"), dict) else {}
        typer.echo(
            " ".join([
                f"- {_value(row.get('ticker'))}",
                f"state={_value(row.get('state'))}",
                f"setup={_value(row.get('setup'))}",
                f"swing={_value(row.get('swing_state'))}",
                f"grade={_value(row.get('grade'))}",
                f"score={_value(row.get('score'))}",
                f"gap={_value(data.get('gap_pct'))}%",
                f"rvol={_value(data.get('rel_volume'))}x",
                f"basis={_value(data.get('gap_basis'))}",
                f"confidence={_value(data.get('confidence'))}",
                f"as_of={_value(data.get('as_of_et'))}",
            ])
        )


def _section(title: str) -> None:
    typer.echo("")
    typer.echo(title)


def _value(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


if __name__ == "__main__":
    app()
