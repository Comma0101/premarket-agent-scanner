from datetime import datetime

from app.models import IntradayBarSeries, utc_now_iso
from providers.alpaca_provider import AlpacaProvider


class FakeBarProvider:
    source_name = "fake"

    def __init__(self, series_map: dict[str, IntradayBarSeries]) -> None:
        self._map = series_map

    def get_bars(
        self, ticker: str, timeframe: str, start: str, end: str, limit: int = 100
    ) -> IntradayBarSeries:
        key = ticker.upper()
        if key in self._map:
            return self._map[key]
        return IntradayBarSeries(
            ticker=key,
            timeframe=timeframe,
            bars=[],
            source=self.source_name,
            fetched_at=utc_now_iso(),
        )


def test_get_bars_returns_empty_when_unconfigured():
    provider = AlpacaProvider(api_key="", secret_key="")
    series = provider.get_bars("AAPL")
    assert series.ticker == "AAPL"
    assert series.bars == []
    assert series.source == "alpaca"


def test_get_bars_parses_alpaca_response(monkeypatch):
    provider = AlpacaProvider(api_key="key", secret_key="secret")

    fake_payload = {
        "bars": [
            {
                "t": "2026-06-29T14:00:00Z",
                "o": 100.0,
                "h": 101.0,
                "l": 99.5,
                "c": 100.5,
                "v": 5000,
            },
            {
                "t": "2026-06-29T14:02:00Z",
                "o": 100.5,
                "h": 102.0,
                "l": 100.0,
                "c": 101.5,
                "v": 8000,
            },
        ]
    }

    monkeypatch.setattr(provider, "_request", lambda endpoint, params: fake_payload)

    series = provider.get_bars("AAPL", timeframe="2Min")
    assert series.ticker == "AAPL"
    assert series.timeframe == "2Min"
    assert len(series.bars) == 2
    assert series.bars[0].open == 100.0
    assert series.bars[0].high == 101.0
    assert series.bars[0].low == 99.5
    assert series.bars[0].close == 100.5
    assert series.bars[0].volume == 5000
    assert series.bars[1].close == 101.5
    assert series.bars[1].volume == 8000


def test_get_bars_handles_empty_payload(monkeypatch):
    provider = AlpacaProvider(api_key="key", secret_key="secret")
    monkeypatch.setattr(provider, "_request", lambda endpoint, params: {"bars": []})
    series = provider.get_bars("AAPL")
    assert series.bars == []


def test_get_bars_handles_null_bars_payload(monkeypatch):
    provider = AlpacaProvider(api_key="key", secret_key="secret")
    monkeypatch.setattr(provider, "_request", lambda endpoint, params: {"bars": None})

    series = provider.get_bars("AAPL")

    assert series.bars == []


def test_get_daily_bars_default_uses_daily_scale_window(monkeypatch):
    provider = AlpacaProvider(api_key="key", secret_key="secret")
    captured = {}

    def fake_request(endpoint, params):
        captured.update(params)
        return {"bars": []}

    monkeypatch.setattr(provider, "_request", fake_request)

    provider.get_bars("AAPL", timeframe="1Day", limit=20)

    start = datetime.fromisoformat(captured["start"])
    end = datetime.fromisoformat(captured["end"])
    assert (end - start).days >= 30


def test_get_bars_treats_empty_start_end_as_default(monkeypatch):
    provider = AlpacaProvider(api_key="key", secret_key="secret")
    captured = {}

    def fake_request(endpoint, params):
        captured.update(params)
        return {"bars": []}

    monkeypatch.setattr(provider, "_request", fake_request)

    provider.get_bars("AAPL", timeframe="2Min", start="", end="", limit=20)

    assert captured["start"]
    assert captured["end"]


def test_get_bars_skips_malformed_bars(monkeypatch):
    provider = AlpacaProvider(api_key="key", secret_key="secret")
    monkeypatch.setattr(
        provider,
        "_request",
        lambda endpoint, params: {
            "bars": [
                "not_a_dict",
                {"t": "2026-06-29T14:00:00Z", "o": 100, "h": 101, "l": 99, "c": 100, "v": 5000},
            ]
        },
    )
    series = provider.get_bars("AAPL")
    assert len(series.bars) == 1
