"""CLI: run the small-cap discovery scanner over a selected universe."""

from __future__ import annotations

import typer

from cli._render import format_gap, format_market_cap, format_price, format_rvol
from services.small_cap_scanner_service import SmallCapScannerService

app = typer.Typer(add_completion=False, help="Small-cap discovery scanner.")


@app.command()
def main(
    preset_name: str = typer.Option(
        "sykes_small_cap_v0",
        "--preset",
        help="Small-cap scanner preset name.",
    ),
    universe: str = typer.Option(None, "--universe", "-u", help="Universe name(s)."),
    watchlist: str = typer.Option(None, "--watchlist", "-w", help="Watchlist name(s)."),
    tickers: str = typer.Option(None, "--tickers", "-t", help="Ad-hoc tickers, comma-separated."),
    all_universes: bool = typer.Option(False, "--all", help="Scan every defined universe."),
) -> None:
    if not any([universe, watchlist, tickers, all_universes]):
        raise typer.BadParameter(
            "Pick a selection: --universe, --watchlist, --tickers, or --all."
        )

    try:
        output = SmallCapScannerService().scan(
            preset_name=preset_name,
            universe=universe,
            watchlist=watchlist,
            tickers=tickers,
            all_universes=all_universes,
        )
    except (KeyError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _render(output)


def _render(output) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        _render_plain(output)
        return

    console = Console()
    table = Table(title=f"Small-cap scan [{output.preset}]", header_style="bold")
    table.add_column("Ticker", style="bold cyan")
    table.add_column("Grade")
    table.add_column("Score", justify="right")
    table.add_column("Gap", justify="right")
    table.add_column("RVOL", justify="right")
    table.add_column("Volume", justify="right")
    table.add_column("Market Cap", justify="right")
    table.add_column("Missing Fields")

    for item in output.candidates:
        table.add_row(
            item.ticker,
            item.grade,
            str(item.score),
            format_gap(item.gap_pct),
            format_rvol(item.rel_volume),
            _format_volume(item.volume),
            format_market_cap(item.market_cap),
            _format_missing_fields(item.missing_fields),
        )

    console.print(table)
    console.print(f"[dim]{output.candidate_count} candidate(s).[/dim]")
    for note in output.notes:
        console.print(f"[dim]note: {note}[/dim]")


def _render_plain(output) -> None:
    print(f"Small-cap scan [{output.preset}]")
    if not output.candidates:
        print("No candidates.")
    for item in output.candidates:
        print(
            f"{item.ticker:<6} "
            f"grade={item.grade:<8} "
            f"score={item.score:>3} "
            f"gap={format_gap(item.gap_pct):>8} "
            f"rvol={format_rvol(item.rel_volume):>6} "
            f"volume={_format_volume(item.volume):>12} "
            f"market_cap={format_market_cap(item.market_cap):>9} "
            f"missing={_format_missing_fields(item.missing_fields)}"
        )
    print(f"{output.candidate_count} candidate(s).")
    for note in output.notes:
        print(f"note: {note}")


def _format_missing_fields(missing_fields: list[str]) -> str:
    return ", ".join(missing_fields) or "-"


def _format_volume(value: float | None) -> str:
    formatted = format_price(value)
    return formatted.removesuffix(".00")


if __name__ == "__main__":
    app()
