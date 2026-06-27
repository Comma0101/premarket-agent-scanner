"""CLI: run a premarket gap scan over a universe, watchlist, or ad-hoc tickers.

Examples:
    python -m cli.scan_premarket --universe MAG7 --min-gap-abs 1
    python -m cli.scan_premarket --watchlist PERSONAL_ACTIVE --direction up
    python -m cli.scan_premarket --tickers NVDA,AMD --min-market-cap 10000000000
"""

from __future__ import annotations

import typer

from app.models import ScanFilters
from cli._render import render_scan
from services.scanner_service import ScannerService

app = typer.Typer(add_completion=False, help="Premarket gap scanner.")


@app.command()
def main(
    universe: str = typer.Option(None, "--universe", "-u", help="Universe name(s), comma-separated."),
    watchlist: str = typer.Option(None, "--watchlist", "-w", help="Watchlist name(s)."),
    tickers: str = typer.Option(None, "--tickers", "-t", help="Ad-hoc tickers, comma-separated."),
    all_universes: bool = typer.Option(False, "--all", help="Scan every defined universe."),
    min_market_cap: float = typer.Option(0, "--min-market-cap", help="Minimum market cap (USD)."),
    max_market_cap: float = typer.Option(None, "--max-market-cap", help="Maximum market cap (USD)."),
    min_gap_abs: float = typer.Option(0, "--min-gap-abs", help="Minimum absolute gap %."),
    direction: str = typer.Option("both", "--direction", "-d", help="up | down | both."),
    only_confident: bool = typer.Option(False, "--only-confident", help="Drop non-OK rows."),
    no_persist: bool = typer.Option(False, "--no-persist", help="Do not write to the database."),
) -> None:
    if direction not in {"up", "down", "both"}:
        raise typer.BadParameter("direction must be up, down, or both")

    if not any([universe, watchlist, tickers, all_universes]):
        raise typer.BadParameter(
            "Pick a selection: --universe, --watchlist, --tickers, or --all."
        )

    filters = ScanFilters(
        min_market_cap=min_market_cap or 0,
        max_market_cap=max_market_cap,
        min_gap_abs=min_gap_abs or 0,
        direction=direction,  # type: ignore[arg-type]
        include_low_confidence=not only_confident,
    )

    service = ScannerService(persist=not no_persist)
    output = service.scan(
        universe=universe,
        watchlist=watchlist,
        tickers=tickers,
        all_universes=all_universes,
        filters=filters,
    )
    render_scan(output)


if __name__ == "__main__":
    app()
