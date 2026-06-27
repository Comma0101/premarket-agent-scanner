import typer
from services.asset_service import AssetService
from services.universe_service import UniverseService

app = typer.Typer()

@app.command()
def main(universe: str | None = None, watchlist: str | None = None, tickers: str | None = None, force: bool = False):
    sel = UniverseService().resolve_selection(universe=universe, watchlist=watchlist, tickers=tickers)
    profiles = AssetService().refresh_profiles(sel.tickers, force=force)
    for p in profiles:
        print(f"{p.ticker}: {p.name or 'unknown'} market_cap={p.market_cap} source={p.source}")

if __name__ == "__main__":
    app()
