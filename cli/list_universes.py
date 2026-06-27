from services.universe_service import UniverseService

if __name__ == "__main__":
    svc = UniverseService()
    for name, tickers in svc.list_universes().items():
        print(f"{name}: {len(tickers)} tickers")
