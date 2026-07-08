from __future__ import annotations

import sys
from types import SimpleNamespace

from providers.yfinance_provider import YFinanceProvider


class FakeTicker:
    fast_info = {
        "previous_close": 100.0,
        "last_price": 104.0,
        "market_cap": 1_500_000_000.0,
        "ten_day_average_volume": 2_500_000.0,
    }

    def get_info(self):
        raise RuntimeError("DNS failure for guce.yahoo.com")


def test_yfinance_snapshot_falls_back_to_fast_info_when_info_endpoint_fails(monkeypatch):
    fake_yfinance = SimpleNamespace(Ticker=lambda ticker: FakeTicker())
    monkeypatch.setitem(sys.modules, "yfinance", fake_yfinance)

    out = YFinanceProvider().get_snapshot("TEST")

    assert out.error is None
    assert out.previous_close == 100.0
    assert out.latest_price == 104.0
    assert out.raw["marketCap"] == 1_500_000_000.0
    assert out.raw["averageVolume"] == 2_500_000.0
    assert any("get_info failed" in note for note in out.notes)
