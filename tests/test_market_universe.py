from __future__ import annotations

from providers.market_universe_provider import (
    MarketUniverseProvider,
    filter_common_stock_symbols,
    parse_nasdaq_trader_symbols,
)


NASDAQ_LISTED_SAMPLE = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
HOT|Hot Common Stock|Q|N|N|100|N|N
ETFQ|Example ETF|Q|N|N|100|Y|N
TEST|Test Company Common Stock|Q|Y|N|100|N|N
WAR|War Co Warrant|Q|N|N|100|N|N
File Creation Time: 0628202621:00|||||||
"""

OTHER_LISTED_SAMPLE = """ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
COOL|Cool Holdings Common Stock|N|COOL|N|100|N|COOL
FUND|Income Fund|A|FUND|N|100|N|FUND
UNIT|Acme Units|A|UNIT|N|100|N|UNIT
OTC1|OTC Name Common Stock|OTC|OTC1|N|100|N|OTC1
"""


def test_parse_nasdaq_trader_symbols_filters_to_common_stock_like_symbols():
    symbols = parse_nasdaq_trader_symbols(
        nasdaq_listed_text=NASDAQ_LISTED_SAMPLE,
        other_listed_text=OTHER_LISTED_SAMPLE,
    )

    assert symbols == ["COOL", "HOT"]


def test_filter_common_stock_symbols_excludes_structural_suffixes_and_descriptions():
    symbols = filter_common_stock_symbols(
        [
            {
                "symbol": "HOT",
                "name": "Hot Common Stock",
                "exchange": "NASDAQ",
                "is_etf": False,
                "is_test": False,
            },
            {
                "symbol": "ABCW",
                "name": "ABC Warrants",
                "exchange": "NASDAQ",
                "is_etf": False,
                "is_test": False,
            },
            {
                "symbol": "AGM.A",
                "name": "Class A Common Stock",
                "exchange": "NYSE",
                "is_etf": False,
                "is_test": False,
            },
            {
                "symbol": "ALL$B",
                "name": "Preferred Shares",
                "exchange": "NYSE",
                "is_etf": False,
                "is_test": False,
            },
            {
                "symbol": "SPY",
                "name": "SPDR S&P 500 ETF Trust",
                "exchange": "NYSE",
                "is_etf": True,
                "is_test": False,
            },
            {
                "symbol": "OTC",
                "name": "OTC Common Stock",
                "exchange": "OTC",
                "is_etf": False,
                "is_test": False,
            },
        ]
    )

    assert symbols == ["HOT"]


def test_market_universe_provider_prefers_alpaca_when_configured():
    class FakeAlpacaAssets:
        is_configured = True

        def list_assets(self):
            return [
                {
                    "symbol": "HOT",
                    "name": "Hot Common Stock",
                    "exchange": "NASDAQ",
                    "asset_class": "us_equity",
                    "status": "active",
                    "tradable": True,
                },
                {
                    "symbol": "ETFQ",
                    "name": "Example ETF",
                    "exchange": "NYSE",
                    "asset_class": "us_equity",
                    "status": "active",
                    "tradable": True,
                },
            ]

    provider = MarketUniverseProvider(alpaca_assets_provider=FakeAlpacaAssets())

    universe = provider.list_symbols("us-listed")

    assert universe.symbols == ["HOT"]
    assert universe.source == "alpaca_assets"
    assert "filtered 1 non-common-stock symbol(s)" in universe.notes


def test_market_universe_provider_falls_back_to_nasdaq_trader():
    class UnconfiguredAlpacaAssets:
        is_configured = False

    provider = MarketUniverseProvider(
        alpaca_assets_provider=UnconfiguredAlpacaAssets(),
        nasdaq_fetcher=lambda: (NASDAQ_LISTED_SAMPLE, OTHER_LISTED_SAMPLE),
    )

    universe = provider.list_symbols("us-listed")

    assert universe.symbols == ["COOL", "HOT"]
    assert universe.source == "nasdaq_trader"
    assert "Alpaca assets not configured; used Nasdaq Trader symbol files." in universe.notes
