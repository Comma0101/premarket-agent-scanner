import json
import typer
from rich.console import Console
from rich.table import Table
from app.models import ScanFilters
from services.gap_scanner import GapScanner

app = typer.Typer()

@app.command()
def main(universe: str | None = None, watchlist: str | None = None, tickers: str | None = None, min_market_cap: float = 0, max_market_cap: float | None = None, min_gap_abs: float = 0, direction: str = "both", limit: int = 50, sort: str = "gap_pct_abs", include_low_confidence: bool = True, export: str = "table"):
    out = GapScanner().scan(universe=universe, watchlist=watchlist, tickers=tickers, filters=ScanFilters(min_market_cap, max_market_cap, min_gap_abs, direction, include_low_confidence), limit=limit, sort=sort)
    if export == "json":
        print(json.dumps([r.__dict__ for r in out.results], default=str, indent=2))
        return
    table = Table(title="Premarket Gap Scanner")
    for col in ["Ticker", "Name", "Mkt Cap", "Prev Close", "Premkt", "Gap %", "Confidence", "Sources"]:
        table.add_column(col)
    for r in out.results:
        table.add_row(r.ticker, r.name or "", str(r.market_cap or ""), str(r.previous_close or ""), str(r.premarket_price or ""), "" if r.gap_pct is None else f"{r.gap_pct:+.2f}", r.confidence, ", ".join(r.sources))
    console = Console()
    for note in out.notes:
        console.print(f"Note: {note}")
    console.print(table)

if __name__ == "__main__":
    app()
