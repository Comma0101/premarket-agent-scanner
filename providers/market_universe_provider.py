from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from providers.alpaca_provider import AlpacaProvider


NasdaqFetcher = Callable[[], tuple[str, str]]

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
SUPPORTED_MARKETS = {"us-listed"}
MAJOR_EXCHANGES = {"NASDAQ", "NYSE", "AMEX", "N", "Q", "A", "P", "Z", "V"}

EXCLUDED_NAME_TERMS = (
    " ETF",
    " EXCHANGE TRADED",
    " FUND",
    " TRUST",
    " ETN",
    " WARRANT",
    " WARRANTS",
    " RIGHT",
    " RIGHTS",
    " UNIT",
    " UNITS",
    " PREFERRED",
    " PREFERENCE",
    " DEPOSITARY",
    " DEPOSITORY",
    " NOTES",
    " NOTE ",
    " BOND",
    " CLOSED END",
    " CLOSED-END",
    " INDEX",
)

EXCLUDED_SYMBOL_MARKERS = (
    ".W",
    ".WS",
    ".WT",
    ".U",
    ".R",
    ".RT",
    ".P",
    ".PR",
    "-W",
    "-WS",
    "-WT",
    "-U",
    "-R",
    "-RT",
    "-P",
    "-PR",
    "/W",
    "/U",
    "/R",
    "^",
)


@dataclass
class MarketUniverse:
    name: str
    symbols: list[str]
    source: str
    notes: list[str] = field(default_factory=list)


class AlpacaAssetsProvider:
    source_name = "alpaca_assets"
    trading_base_url = "https://paper-api.alpaca.markets/v2"

    def __init__(self, alpaca_provider: AlpacaProvider | None = None) -> None:
        self.alpaca_provider = alpaca_provider or AlpacaProvider()

    @property
    def is_configured(self) -> bool:
        return self.alpaca_provider.is_configured

    def list_assets(self) -> list[dict[str, Any]]:
        if not self.is_configured:
            return []

        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("requests package is not installed.") from exc

        response = requests.get(
            f"{self.trading_base_url}/assets",
            params={"asset_class": "us_equity", "status": "active"},
            headers={
                "APCA-API-KEY-ID": self.alpaca_provider.api_key or "",
                "APCA-API-SECRET-KEY": self.alpaca_provider.secret_key or "",
            },
            timeout=20,
        )
        if response.status_code in {401, 403}:
            raise RuntimeError("Alpaca credentials rejected.")
        if response.status_code == 429:
            raise RuntimeError("Alpaca rate limit reached.")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []


class MarketUniverseProvider:
    def __init__(
        self,
        *,
        alpaca_assets_provider: Any | None = None,
        nasdaq_fetcher: NasdaqFetcher | None = None,
    ) -> None:
        self.alpaca_assets_provider = alpaca_assets_provider or AlpacaAssetsProvider()
        self.nasdaq_fetcher = nasdaq_fetcher or fetch_nasdaq_trader_symbol_files

    def list_symbols(self, market: str = "us-listed") -> MarketUniverse:
        normalized = market.strip().lower()
        if normalized not in SUPPORTED_MARKETS:
            valid = ", ".join(sorted(SUPPORTED_MARKETS))
            raise ValueError(f"Unknown market universe: {market}. Valid markets: {valid}.")

        notes: list[str] = []
        if getattr(self.alpaca_assets_provider, "is_configured", False):
            try:
                raw_assets = self.alpaca_assets_provider.list_assets()
            except Exception as exc:
                notes.append(f"Alpaca assets lookup failed: {exc}; used Nasdaq Trader fallback.")
            else:
                symbols = filter_common_stock_symbols(_normalize_alpaca_assets(raw_assets))
                notes.extend(_filter_notes(len(raw_assets), len(symbols)))
                return MarketUniverse(
                    name=normalized,
                    symbols=symbols,
                    source="alpaca_assets",
                    notes=notes,
                )
        else:
            notes.append("Alpaca assets not configured; used Nasdaq Trader symbol files.")

        try:
            nasdaq_listed, other_listed = self.nasdaq_fetcher()
        except Exception as exc:
            raise ValueError(f"Market universe {normalized} unavailable: {exc}") from exc
        symbols = parse_nasdaq_trader_symbols(nasdaq_listed, other_listed)
        notes.extend(_filter_notes(_count_symbol_rows(nasdaq_listed, other_listed), len(symbols)))
        return MarketUniverse(
            name=normalized,
            symbols=symbols,
            source="nasdaq_trader",
            notes=notes,
        )


def fetch_nasdaq_trader_symbol_files() -> tuple[str, str]:
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("requests package is not installed.") from exc

    nasdaq = requests.get(NASDAQ_LISTED_URL, timeout=20)
    other = requests.get(OTHER_LISTED_URL, timeout=20)
    nasdaq.raise_for_status()
    other.raise_for_status()
    return nasdaq.text, other.text


def parse_nasdaq_trader_symbols(
    nasdaq_listed_text: str,
    other_listed_text: str,
) -> list[str]:
    rows = [
        *_parse_nasdaq_listed(nasdaq_listed_text),
        *_parse_other_listed(other_listed_text),
    ]
    return filter_common_stock_symbols(rows)


def filter_common_stock_symbols(rows: list[dict[str, Any]]) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        if not _is_common_stock_like(row, symbol):
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return sorted(symbols)


def _normalize_alpaca_assets(raw_assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for asset in raw_assets:
        if not isinstance(asset, dict):
            continue
        rows.append(
            {
                "symbol": asset.get("symbol"),
                "name": asset.get("name"),
                "exchange": asset.get("exchange"),
                "asset_class": asset.get("asset_class"),
                "status": asset.get("status"),
                "tradable": asset.get("tradable", True),
                "is_etf": _looks_like_etf(asset.get("name")),
                "is_test": False,
            }
        )
    return rows


def _parse_nasdaq_listed(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _pipe_rows(text):
        symbol = row.get("Symbol")
        if not symbol:
            continue
        rows.append(
            {
                "symbol": symbol,
                "name": row.get("Security Name"),
                "exchange": "NASDAQ",
                "is_etf": row.get("ETF") == "Y",
                "is_test": row.get("Test Issue") == "Y",
            }
        )
    return rows


def _parse_other_listed(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _pipe_rows(text):
        symbol = row.get("ACT Symbol")
        if not symbol:
            continue
        rows.append(
            {
                "symbol": symbol,
                "name": row.get("Security Name"),
                "exchange": row.get("Exchange"),
                "is_etf": row.get("ETF") == "Y",
                "is_test": row.get("Test Issue") == "Y",
            }
        )
    return rows


def _pipe_rows(text: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    headers = lines[0].split("|")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        if line.startswith("File Creation Time:"):
            continue
        values = line.split("|")
        if len(values) != len(headers):
            continue
        rows.append(dict(zip(headers, values, strict=True)))
    return rows


def _is_common_stock_like(row: dict[str, Any], symbol: str) -> bool:
    name = str(row.get("name") or "").upper()
    exchange = str(row.get("exchange") or "").upper()
    status = str(row.get("status") or "active").lower()
    asset_class = str(row.get("asset_class") or "us_equity").lower()

    if row.get("is_etf") or row.get("is_test"):
        return False
    if status and status != "active":
        return False
    if asset_class and asset_class != "us_equity":
        return False
    if row.get("tradable") is False:
        return False
    if exchange and exchange not in MAJOR_EXCHANGES:
        return False
    if any(marker in symbol for marker in (".", "$", "/", "^")):
        return False
    if any(marker in symbol for marker in EXCLUDED_SYMBOL_MARKERS):
        return False
    if any(term in f" {name} " for term in EXCLUDED_NAME_TERMS):
        return False
    if len(symbol) > 5:
        return False
    return True


def _looks_like_etf(name: Any) -> bool:
    upper = str(name or "").upper()
    return " ETF" in f" {upper} " or " EXCHANGE TRADED" in f" {upper} "


def _count_symbol_rows(nasdaq_listed_text: str, other_listed_text: str) -> int:
    return len(_parse_nasdaq_listed(nasdaq_listed_text)) + len(_parse_other_listed(other_listed_text))


def _filter_notes(raw_count: int, kept_count: int) -> list[str]:
    dropped = max(0, raw_count - kept_count)
    if dropped == 0:
        return []
    return [f"filtered {dropped} non-common-stock symbol(s)"]
