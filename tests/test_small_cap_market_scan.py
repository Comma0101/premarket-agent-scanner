from __future__ import annotations

from app.models import ScannerResult, ScanRunOutput, SmallCapEvidence
from services.small_cap_scanner_service import SmallCapScannerService


class FakeMarketUniverse:
    source = "fake_market"
    symbols = ["HOT", "COOL", "WARM"]
    notes = ["fake market universe"]


class FakeMarketProvider:
    def list_symbols(self, market: str):
        assert market == "us-listed"
        return FakeMarketUniverse()


class FakeScanner:
    def scan(self, **kwargs):
        assert kwargs["tickers"] == ["HOT", "COOL", "WARM"]
        return ScanRunOutput(
            run_id="run-1",
            universe=None,
            started_at="2026-06-28T12:00:00Z",
            completed_at="2026-06-28T12:01:00Z",
            status="OK",
            results=[
                ScannerResult(
                    ticker="HOT",
                    name=None,
                    universe=None,
                    market_cap=100_000_000,
                    previous_close=1.0,
                    premarket_price=1.2,
                    latest_price=1.2,
                    gap_pct=20.0,
                    gap_dollar=0.2,
                    volume=2_000_000,
                    rel_volume=5.0,
                    confidence="OK",
                    notes=None,
                    sources=["fake"],
                    timestamp="2026-06-28T12:00:00Z",
                )
            ],
            notes=[],
        )


class FakeEvidence:
    def enrich_candidates(self, candidates):
        candidates[0].evidence = SmallCapEvidence(
            ticker="HOT",
            float_shares=8_000_000,
            missing_fields=["catalyst"],
        )
        return candidates


def test_small_cap_scanner_can_scan_market_universe():
    output = SmallCapScannerService(
        scanner_service=FakeScanner(),
        market_universe_provider=FakeMarketProvider(),
        evidence_service=FakeEvidence(),
    ).scan(market="us-listed", preset_name="sykes_small_cap_v0")

    assert output.candidate_count == 1
    assert output.candidates[0].ticker == "HOT"
    assert output.notes[:2] == [
        "Market universe us-listed resolved 3 symbol(s) from fake_market.",
        "fake market universe",
    ]


def test_small_cap_scanner_can_limit_market_universe_for_smoke_tests():
    class LimitedFakeScanner(FakeScanner):
        def scan(self, **kwargs):
            assert kwargs["tickers"] == ["HOT", "COOL"]
            return ScanRunOutput(
                run_id="run-1",
                universe=None,
                started_at="2026-06-28T12:00:00Z",
                completed_at="2026-06-28T12:01:00Z",
                status="OK",
                results=[],
                notes=[],
            )

    output = SmallCapScannerService(
        scanner_service=LimitedFakeScanner(),
        market_universe_provider=FakeMarketProvider(),
        evidence_service=FakeEvidence(),
    ).scan(market="us-listed", market_limit=2, preset_name="sykes_small_cap_v0")

    assert "Limited market universe to 2 symbol(s) for testing." in output.notes
