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


class FakeHaltProvider:
    def get_halt_status(self, ticker):
        return HaltStatus(
            ticker=ticker,
            status="HALTED_REGULATORY",
            is_active=True,
            reason_code="T1",
            halt_time="2026-06-30T13:35:00+00:00",
            source="fake_halts",
            fetched_at="2026-06-30T13:36:00+00:00",
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
    # No Alpaca keys available -> alpaca provider not attached. Use empty strings
    # rather than delenv so python-dotenv (override=False) cannot reload them
    # from a real .env file in the test environment.
    monkeypatch.setenv("ALPACA_API_KEY", "")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "")
    service = SnapshotService.with_configured_providers()
    assert service.alpaca_provider is None


def _yf_error(message: str) -> ProviderPriceData:
    return ProviderPriceData(
        ticker="NVDA",
        source="yfinance",
        error=message,
        notes=[f"yfinance failure detail: {message}"],
    )


def _alpaca_error(message: str) -> ProviderPriceData:
    return ProviderPriceData(
        ticker="NVDA",
        source="alpaca",
        error=message,
        notes=[f"alpaca failure detail: {message}"],
    )


def test_snapshot_provider_failure_includes_provider_failures_indexed_by_source():
    # Both providers errored -> snapshot cannot construct any field. The provider
    # failures must be surfaced in a structured form so the desk can tell which
    # sources failed without parsing the free-text notes list.
    snap = _service(
        _yf_error("DNS failure for guce.yahoo.com"),
        _alpaca_error("missing_credentials"),
    ).build_snapshot("NVDA")

    assert snap.confidence == "ERROR"
    assert snap.provider_failures == {
        "yfinance": "DNS failure for guce.yahoo.com",
        "alpaca": "missing_credentials",
    }
    assert snap.data_status == "provider_failure"


def test_snapshot_data_status_is_live_on_clean_data():
    snap = _service(_yf(100.0, 105.0), _alpaca(prev=100.0, pre=105.1)).build_snapshot("NVDA")
    assert snap.confidence == "OK"
    assert snap.data_status == "live"
    assert snap.provider_failures == {}


def test_snapshot_data_status_is_partial_when_yfinance_only_with_missing_premarket():
    # Single source (yfinance) but no premarket price: live quote is OK but the
    # snapshot is partial because we cannot establish a premarket gap.
    yf = ProviderPriceData(
        ticker="NVDA",
        source="yfinance",
        previous_close=100.0,
        premarket_price=None,
        latest_price=104.0,
        volume=1_000_000,
        timestamp=utc_now_iso(),
        raw={"marketCap": 3.0e12},
    )
    snap = _service(yf, _alpaca(error="missing_credentials")).build_snapshot("NVDA")
    assert snap.confidence == "LOW_CONFIDENCE"
    assert snap.data_status == "partial"
    # Alpaca contributes nothing here, so its missing_credentials shows up in
    # provider_failures — that is the desk's signal that Alpaca is offline.
    assert snap.provider_failures == {"alpaca": "missing_credentials"}


def test_snapshot_yfinance_only_provider_failure_no_alpaca_attached():
    # Reproduces the desk workflow: Alpaca not configured, yfinance DNS-fails.
    svc = SnapshotService(
        yf_provider=FakeProvider("yfinance", _yf_error("DNS failure for guce.yahoo.com")),
        alpaca_provider=None,
    )
    snap = svc.build_snapshot("MRVL")

    assert snap.confidence == "ERROR"
    assert snap.provider_failures == {"yfinance": "DNS failure for guce.yahoo.com"}
    assert snap.data_status == "provider_failure"
    assert "yfinance: DNS failure for guce.yahoo.com" in snap.notes


def test_snapshot_provider_failures_preserve_existing_confidence_label():
    # yfinance errors but Alpaca returned a clean quote — the snapshot should
    # still report the provider failure in provider_failures so the desk knows
    # to triage, but the confidence label must NOT be silently flipped. The
    # prime directive is "preserve confidence labels".
    snap = _service(
        _yf_error("DNS failure for guce.yahoo.com"),
        _alpaca(prev=100.0, pre=105.0),
    ).build_snapshot("NVDA")
    assert snap.confidence == "OK"
    assert snap.data_status == "partial"
    assert snap.provider_failures == {"yfinance": "DNS failure for guce.yahoo.com"}


def test_snapshot_attaches_halt_status_without_changing_price_confidence():
    service = SnapshotService(
        yf_provider=FakeProvider("yfinance", _yf(100.0, 105.0)),
        alpaca_provider=None,
        halt_provider=FakeHaltProvider(),
    )

    snap = service.build_snapshot("HALT")

    assert snap.confidence == "OK"
    assert snap.halt_status is not None
    assert snap.halt_status.is_active is True
    assert snap.halt_status.reason_code == "T1"
    assert any("halt" in note.lower() for note in snap.notes)
