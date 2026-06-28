"""Shared rendering helpers for the CLI commands."""

from __future__ import annotations

from app.models import ScanRunOutput

# Confidence labels worth highlighting in yellow/red in the table.
_WARN_CONFIDENCE = {
    "LOW_CONFIDENCE",
    "CONFLICT",
    "STALE_DATA",
    "MISSING_MARKET_CAP",
}


def format_market_cap(value: float | None) -> str:
    if value is None:
        return "-"
    if value >= 1e12:
        return f"${value / 1e12:.2f}T"
    if value >= 1e9:
        return f"${value / 1e9:.2f}B"
    if value >= 1e6:
        return f"${value / 1e6:.1f}M"
    return f"${value:,.0f}"


def format_price(value: float | None) -> str:
    return "-" if value is None else f"{value:,.2f}"


def format_gap(value: float | None) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def format_gap_dollar(value: float | None) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def format_rvol(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}x"


def render_scan(output: ScanRunOutput) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        _render_scan_plain(output)
        return

    console = Console()
    title = f"Premarket scan [{output.universe or 'selection'}] — run {output.run_id}"
    table = Table(title=title, header_style="bold")
    table.add_column("Ticker", style="bold cyan")
    table.add_column("Name", overflow="ellipsis", max_width=22)
    table.add_column("Gap", justify="right")
    table.add_column("Gap$", justify="right")
    table.add_column("RVol", justify="right")
    table.add_column("Pre/Last", justify="right")
    table.add_column("Prev Close", justify="right")
    table.add_column("Mkt Cap", justify="right")
    table.add_column("Conf")

    if not output.results:
        console.print(f"[yellow]No matches.[/yellow] (status: {output.status})")
        _print_notes(console, output)
        return

    for r in output.results:
        gap_style = "green" if (r.gap_pct or 0) > 0 else "red" if (r.gap_pct or 0) < 0 else ""
        price = r.premarket_price if r.premarket_price is not None else r.latest_price
        conf_style = "yellow" if r.confidence in _WARN_CONFIDENCE else "dim"
        gap_cell = f"[{gap_style}]{format_gap(r.gap_pct)}[/{gap_style}]" if gap_style else format_gap(r.gap_pct)
        gap_dollar_cell = (
            f"[{gap_style}]{format_gap_dollar(r.gap_dollar)}[/{gap_style}]"
            if gap_style
            else format_gap_dollar(r.gap_dollar)
        )
        table.add_row(
            r.ticker,
            r.name or "-",
            gap_cell,
            gap_dollar_cell,
            format_rvol(r.rel_volume),
            format_price(price),
            format_price(r.previous_close),
            format_market_cap(r.market_cap),
            f"[{conf_style}]{r.confidence}[/{conf_style}]",
        )

    console.print(table)
    console.print(f"[dim]{len(output.results)} match(es).[/dim]")
    _print_notes(console, output)


def _print_notes(console, output: ScanRunOutput) -> None:
    for note in output.notes:
        console.print(f"[dim]note: {note}[/dim]")


def _render_scan_plain(output: ScanRunOutput) -> None:
    print(f"Premarket scan [{output.universe or 'selection'}] — run {output.run_id}")
    if not output.results:
        print(f"No matches. (status: {output.status})")
    for r in output.results:
        price = r.premarket_price if r.premarket_price is not None else r.latest_price
        print(
            f"{r.ticker:<6} {format_gap(r.gap_pct):>8} {format_gap_dollar(r.gap_dollar):>10}  "
            f"rvol={format_rvol(r.rel_volume):>6}  "
            f"pre/last={format_price(price):>10}  prev={format_price(r.previous_close):>10}  "
            f"cap={format_market_cap(r.market_cap):>9}  {r.confidence}"
        )
    for note in output.notes:
        print(f"note: {note}")
