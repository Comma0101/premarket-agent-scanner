"""Snapshot service tests, including yfinance + Alpaca cross-validation.

Offline: both providers are fakes feeding deterministic ProviderPriceData into
the real SnapshotService, so the confidence/conflict logic is exercised exactly
as it would be with live providers.
"""

from __future__ import annotations

from app.models import HaltStatus, ProviderPriceData, utc_now_iso
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


def test_snapshot_provider_failures_are_structured_and_not_counted_as_sources():
    yf = ProviderPriceData(
        ticker="NVDA",
        source="yfinance",
        notes=["Failed to fetch yfinance quote: DNS failure"],
        error="DNS failure",
    )
    alpaca = ProviderPriceData(
        ticker="NVDA",
        source="alpaca",
        notes=["Alpaca latest trade unavailable: DNS failure"],
        error="no_usable_alpaca_snapshot",
    )

    snap = _service(yf, alpaca).build_snapshot("NVDA")

    assert snap.confidence == "ERROR"
    assert snap.data_status == "provider_failure"
    assert snap.provider_failures == {
        "yfinance": "DNS failure",
        "alpaca": "no_usable_alpaca_snapshot",
    }
    assert snap.sources == []


def test_snapshot_data_status_partial_when_single_source_missing_previous_close():
    yf = ProviderPriceData(
        ticker="NVDA",
        source="yfinance",
        previous_close=None,
        latest_price=105.0,
        timestamp=utc_now_iso(),
    )

    snap = SnapshotService(yf_provider=FakeProvider("yfinance", yf)).build_snapshot("NVDA")

    assert snap.confidence == "MISSING_PREVIOUS_CLOSE"
    assert snap.data_status == "partial"
    assert snap.provider_failures == {}


def test_with_configured_providers_is_yfinance_only_without_keys(monkeypatch):
    # No Alpaca keys available -> alpaca provider not attached. Use empty strings
    # rather than delenv so python-dotenv (override=False) cannot reload them
    # from a real .env file in the test environment.
    monkeypatch.setenv("ALPACA_API_KEY", "")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "")
    service = SnapshotService.with_configured_providers()
    assert service.alpaca_provider is None


def test_snapshot_carries_halt_status_without_changing_price_confidence():
    class FakeHaltProvider:
        def get_halt_status(self, ticker):
            return HaltStatus(
                ticker=ticker,
                status="HALTED",
                reason_code="LUDP",
                halt_time="07/01/2026 09:35:12",
                source="nasdaq_trader_halts",
            )

    service = SnapshotService(
        yf_provider=FakeProvider("yfinance", _yf(100.0, 105.0)),
        halt_provider=FakeHaltProvider(),
    )

    snap = service.build_snapshot("NVDA")

    assert snap.confidence == "OK"
    assert snap.halt_status is not None
    assert snap.halt_status.status == "HALTED"
    assert snap.halt_status.reason_code == "LUDP"
