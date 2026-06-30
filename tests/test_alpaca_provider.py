from __future__ import annotations

from providers.alpaca_provider import AlpacaProvider


def test_alpaca_snapshot_reports_error_when_all_requests_fail(monkeypatch) -> None:
    provider = AlpacaProvider(api_key="key", secret_key="secret")

    def raise_dns_failure(endpoint, params):
        raise RuntimeError("DNS failure for data.alpaca.markets")

    monkeypatch.setattr(provider, "_request", raise_dns_failure)

    out = provider.get_snapshot("MRVL")

    assert out.error is not None
    assert "data.alpaca.markets" in out.error
    assert out.previous_close is None
    assert out.premarket_price is None
    assert out.latest_price is None
