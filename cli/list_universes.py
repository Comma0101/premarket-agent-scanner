"""CLI: list defined universes and watchlists with their tickers."""

from __future__ import annotations

import typer

from services.universe_service import UniverseService

app = typer.Typer(add_completion=False, help="List universes and watchlists.")


@app.command()
def main(
    show_tickers: bool = typer.Option(True, "--tickers/--no-tickers", help="Show member tickers."),
) -> None:
    service = UniverseService()
    universes = service.list_universes()
    watchlists = service.list_watchlists()

    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        _rich_section(console, Table, "Universes", universes, show_tickers)
        if watchlists:
            _rich_section(console, Table, "Watchlists", watchlists, show_tickers)
        return
    except ImportError:
        pass

    _plain_section("Universes", universes, show_tickers)
    if watchlists:
        _plain_section("Watchlists", watchlists, show_tickers)


def _rich_section(console, Table, heading, mapping, show_tickers) -> None:
    table = Table(title=heading, header_style="bold")
    table.add_column("Name", style="bold cyan")
    table.add_column("Count", justify="right")
    if show_tickers:
        table.add_column("Tickers")
    for name, tickers in mapping.items():
        row = [name, str(len(tickers))]
        if show_tickers:
            row.append(", ".join(tickers))
        table.add_row(*row)
    console.print(table)


def _plain_section(heading, mapping, show_tickers) -> None:
    print(f"\n{heading}:")
    for name, tickers in mapping.items():
        line = f"  {name} ({len(tickers)})"
        if show_tickers:
            line += f": {', '.join(tickers)}"
        print(line)


if __name__ == "__main__":
    app()
