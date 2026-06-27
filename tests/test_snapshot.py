"""Snapshot service tests, including yfinance + Alpaca cross-validation.

Offline: both providers are fakes feeding deterministic ProviderPriceData into
the real SnapshotService, so the confidence/conflict logic is exercised exactly
as it would be with live providers.
"""

from __future__ import annotations

from app.models import ProviderPriceData, utc_now_iso
from services.snapshot_service import SnapshotService


class FakeProvider:
    def __init__(self, source_name, data):
        self.source_name = source_name
        self._data = data

    def get_snapshot(self, ticker):
        return self._data


def _yf(prev, pre, cap=3.0e12):
    return ProviderPriceData(
        ticker="NVDA",
        source="yfinance",
        previous_close=prev,
        premarket_price=pre,
        latest_price=pre,
        volume=1_000_000,
        timestamp=utc_now_iso(),
        raw={"marketCap": cap},
    )


def _alpaca(prev=None, pre=None, error=None):
    return ProviderPriceData(
        ticker="NVDA",
        source="alpaca",
        previous_close=prev,
        premarket_price=pre,
        latest_price=pre,
        timestamp=utc_now_iso() if pre is not None else None,
        error=error,
    )


def _service(yf_data, alpaca_data):
    return SnapshotService(
        yf_provider=FakeProvider("yfinance", yf_data),
        alpaca_provider=FakeProvider("alpaca", alpaca_data),
    )


def test_agreeing_sources_are_ok_with_two_sources():
    snap = _service(_yf(100.0, 105.0), _alpaca(prev=100.0, pre=105.1)).build_snapshot("NVDA")
    assert snap.confidence == "OK"
    assert snap.sources == ["yfinance", "alpaca"]
    assert snap.source_secondary == "alpaca"


def test_disagreeing_sources_flag_conflict():
    # 105 vs 120 is well beyond the 3% conflict threshold.
    snap = _service(_yf(100.0, 105.0), _alpaca(prev=100.0, pre=120.0)).build_snapshot("NVDA")
    assert snap.confidence == "CONFLICT"
    # The note should explain the divergence for the agent to surface.
    assert any("apart" in n for n in snap.notes)


def test_alpaca_backfills_missing_previous_close():
    # yfinance has no previous close; Alpaca supplies it.
    yf = _yf(None, 105.0)
    snap = _service(yf, _alpaca(prev=100.0, pre=105.2)).build_snapshot("NVDA")
    assert snap.previous_close == 100.0
    assert snap.confidence == "OK"


def test_missing_alpaca_credentials_falls_back_to_yfinance_only():
    snap = _service(_yf(100.0, 105.0), _alpaca(error="missing_credentials")).build_snapshot("NVDA")
    assert snap.confidence == "OK"
    assert snap.sources == ["yfinance"]
    assert snap.source_secondary is None


def test_with_configured_providers_is_yfinance_only_without_keys(monkeypatch):
    # No Alpaca env keys in the test environment -> alpaca provider not attached.
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    service = SnapshotService.with_configured_providers()
    assert service.alpaca_provider is None
