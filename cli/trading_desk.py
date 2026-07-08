from __future__ import annotations

import json
from typing import Any

import typer

from services.trading_desk_service import TradingDeskService


app = typer.Typer(add_completion=False, help="One-run trading desk brief.")


@app.command()
def main(
    tickers: str | None = typer.Option(None, "--tickers", "-t", help="Comma-separated tickers."),
    universe: str | None = typer.Option(None, "--universe", "-u", help="Universe name(s)."),
    watchlist: str | None = typer.Option(None, "--watchlist", "-w", help="Watchlist name(s)."),
    market: str | None = typer.Option("us-listed", "--market", help="Market source."),
    market_limit: int | None = typer.Option(None, "--market-limit", help="Limit market symbols."),
    max_workers: int = typer.Option(6, "--max-workers", help="Bounded scan workers."),
    summary_limit: int = typer.Option(8, "--summary-limit", help="Top slices to show."),
    persist: bool = typer.Option(False, "--persist/--no-persist", help="Persist agent sessions."),
    json_output: bool = typer.Option(False, "--json/--no-json", help="Print JSON."),
) -> None:
    output = TradingDeskService().run(
        tickers=tickers,
        universe=universe,
        watchlist=watchlist,
        market=market,
        market_limit=market_limit,
        max_workers=max_workers,
        summary_limit=summary_limit,
        persist=persist,
    )
    if json_output:
        typer.echo(json.dumps(output, indent=2, sort_keys=True))
        return
    _render(output)


def _render(output: dict[str, Any]) -> None:
    typer.echo("Trading Desk One Run")
    if output.get("session_banner"):
        typer.echo(str(output["session_banner"]))
    read = output.get("desk_read") if isinstance(output.get("desk_read"), dict) else {}
    if read.get("one_liner"):
        typer.echo(str(read["one_liner"]))

    _section("Top Slices")
    for row in output.get("top_slices") or []:
        if not isinstance(row, dict):
            continue
        typer.echo(
            " ".join([
                f"slice {_value(row.get('agent'))}",
                _value(row.get("ticker")),
                _value(row.get("lane")),
                _value(row.get("state")),
                _value(row.get("setup")),
            ])
        )
        typer.echo(f"  data={_value(row.get('data'))}")
        typer.echo(f"  why={_value(row.get('why'))}")
        typer.echo(f"  watch={_value(row.get('watch'))}")
        typer.echo(f"  risk={_value(row.get('risk'))}")

    _section("Blocked")
    blocked = output.get("blocked_data") or []
    if not blocked:
        typer.echo("- none")
    for row in blocked:
        if isinstance(row, dict):
            typer.echo(f"blocked {_value(row.get('agent'))} {_value(row.get('ticker'))}")

    if output.get("disclaimer"):
        typer.echo(str(output["disclaimer"]))


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
