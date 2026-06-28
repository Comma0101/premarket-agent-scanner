"""CLI: refresh cached company profiles for a universe, watchlist, or ad-hoc tickers.

Examples:
    python -m cli.refresh_profiles --universe MAG7
    python -m cli.refresh_profiles --watchlist PERSONAL_ACTIVE --force
    python -m cli.refresh_profiles --tickers NVDA,AMD
"""

from __future__ import annotations

import typer

from app.config import get_config
from services.profile_service import ProfileService
from services.universe_service import UniverseService

app = typer.Typer(add_completion=False, help="Refresh cached company profiles.")


@app.command()
def main(
    universe: str = typer.Option(None, "--universe", "-u", help="Universe name(s)."),
    watchlist: str = typer.Option(None, "--watchlist", "-w", help="Watchlist name(s)."),
    tickers: str = typer.Option(None, "--tickers", "-t", help="Ad-hoc tickers, comma-separated."),
    all_universes: bool = typer.Option(False, "--all", help="Refresh every defined universe."),
    force: bool = typer.Option(False, "--force", help="Ignore cache freshness and re-fetch."),
) -> None:
    if not any([universe, watchlist, tickers, all_universes]):
        raise typer.BadParameter("Pick a selection: --universe, --watchlist, --tickers, or --all.")

    selection = UniverseService().resolve_selection(
        universe=universe,
        watchlist=watchlist,
        tickers=tickers,
        all_universes=all_universes,
    )
    if not selection.tickers:
        typer.echo("No tickers resolved for the requested selection.")
        return

    db_path = str(get_config().database_path)
    service = ProfileService(db_path=db_path)
    typer.echo(f"Refreshing {len(selection.tickers)} profile(s) [{selection.label}]...")
    profiles = service.refresh_profiles(selection.tickers, force=force)

    try:
        from rich.console import Console
        from rich.table import Table

        table = Table(title="Profiles", header_style="bold")
        table.add_column("Ticker", style="bold cyan")
        table.add_column("Name", overflow="ellipsis", max_width=28)
        table.add_column("Mkt Cap", justify="right")
        table.add_column("Sector")
        table.add_column("Source", style="dim")
        for p in profiles:
            table.add_row(p.ticker, p.name or "-", _format_cap(p.market_cap), p.sector or "-", p.source or "-")
        Console().print(table)
    except ImportError:
        for p in profiles:
            print(f"{p.ticker:<6} {p.name or '-':<28} cap={_format_cap(p.market_cap):>10}  {p.sector or '-'}")

    missing = len(selection.tickers) - len(profiles)
    if missing:
        typer.echo(f"{missing} profile(s) could not be resolved.")


def _format_cap(value: float | None) -> str:
    if value is None:
        return "-"
    if value >= 1e12:
        return f"${value / 1e12:.2f}T"
    if value >= 1e9:
        return f"${value / 1e9:.2f}B"
    if value >= 1e6:
        return f"${value / 1e6:.1f}M"
    return f"${value:,.0f}"


if __name__ == "__main__":
    app()
