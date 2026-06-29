"""CLI: run the small-cap discovery scanner over a selected universe."""

from __future__ import annotations

import typer

from app.models import SmallCapCandidate, SmallCapEvidence
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
    market: str = typer.Option(
        None,
        "--market",
        help="Whole-market source, e.g. us-listed.",
    ),
    market_limit: int = typer.Option(
        None,
        "--market-limit",
        help="Limit market symbols for smoke tests.",
    ),
    all_universes: bool = typer.Option(False, "--all", help="Scan every defined universe."),
) -> None:
    if not any([universe, watchlist, tickers, market, all_universes]):
        raise typer.BadParameter(
            "Pick a selection: --universe, --watchlist, --tickers, --market, or --all."
        )

    try:
        output = SmallCapScannerService().scan(
            preset_name=preset_name,
            universe=universe,
            watchlist=watchlist,
            tickers=tickers,
            market=market,
            market_limit=market_limit,
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
    table.add_column("Evidence", overflow="ellipsis", no_wrap=True, max_width=32)
    table.add_column("Missing", overflow="ellipsis", max_width=24)

    for item in output.candidates:
        table.add_row(
            item.ticker,
            item.grade,
            str(item.score),
            format_gap(item.gap_pct),
            format_rvol(item.rel_volume),
            _format_volume(item.volume),
            format_market_cap(item.market_cap),
            _format_evidence_summary(item.evidence),
            _format_candidate_missing_fields(item),
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
            f"float={_format_evidence_float(item.evidence):>9} "
            f"rotation={_format_float_rotation(item.evidence):>6} "
            f"catalyst={_format_catalyst(item.evidence)} "
            f"filing_risk={_format_filing_risk(item.evidence)} "
            f"former={_format_former_runner(item.evidence)} "
            f"missing={_format_candidate_missing_fields(item)}"
        )
    print(f"{output.candidate_count} candidate(s).")
    for note in output.notes:
        print(f"note: {note}")


def _format_missing_fields(missing_fields: list[str]) -> str:
    return ", ".join(missing_fields) or "-"


def _format_volume(value: float | None) -> str:
    formatted = format_price(value)
    return formatted.removesuffix(".00")


def _format_candidate_missing_fields(candidate: SmallCapCandidate) -> str:
    if candidate.evidence is not None:
        return _format_missing_fields(candidate.evidence.missing_fields)
    return _format_missing_fields(candidate.missing_fields)


def _format_evidence_summary(evidence: SmallCapEvidence | None) -> str:
    if evidence is None:
        return "-"

    parts: list[str] = []
    float_label = _format_evidence_float(evidence)
    has_catalyst = bool(evidence.catalysts)
    filing_risk = _format_filing_risk(evidence)
    former_runner = _format_former_runner(evidence)

    if float_label != "-":
        parts.append(float_label)
    rotation = _format_float_rotation(evidence)
    if rotation != "-":
        parts.append(rotation)
    if has_catalyst:
        parts.append("cat")
    if filing_risk != "-":
        parts.append(filing_risk)
    if former_runner != "-":
        parts.append("prev")

    return _compact(" ".join(parts), 32) if parts else "-"


def _format_evidence_float(evidence: SmallCapEvidence | None) -> str:
    if evidence is None or evidence.float_shares is None:
        return "-"

    label = _format_share_count(evidence.float_shares)
    if evidence.is_low_float:
        return f"{label} low"
    return label


def _format_float_rotation(evidence: SmallCapEvidence | None) -> str:
    if evidence is None or evidence.float_rotation is None:
        return "-"
    return f"{evidence.float_rotation:.1f}x"


def _format_catalyst(evidence: SmallCapEvidence | None) -> str:
    if evidence is None or not evidence.catalysts:
        return "-"

    catalyst = evidence.catalysts[0]
    label = f"{catalyst.source}: {catalyst.headline}" if catalyst.source else catalyst.headline
    return _compact(label, 32)


def _format_filing_risk(evidence: SmallCapEvidence | None) -> str:
    if evidence is None:
        return "-"

    tags: list[str] = []
    for filing in evidence.filings:
        for tag in filing.risk_tags:
            if tag not in tags:
                tags.append(tag)

    return ", ".join(tags) or "-"


def _format_former_runner(evidence: SmallCapEvidence | None) -> str:
    if evidence is None or evidence.former_runner is None:
        return "-"
    return "yes"


def _format_share_count(value: float) -> str:
    if abs(value) >= 1e9:
        return f"{value / 1e9:.1f}B"
    if abs(value) >= 1e6:
        return f"{value / 1e6:.1f}M"
    if abs(value) >= 1e3:
        return f"{value / 1e3:.1f}K"
    return f"{value:,.0f}"


def _compact(value: str, max_length: int) -> str:
    clean = " ".join(value.split())
    if len(clean) <= max_length:
        return clean or "-"
    return f"{clean[: max_length - 3]}..."


if __name__ == "__main__":
    app()
