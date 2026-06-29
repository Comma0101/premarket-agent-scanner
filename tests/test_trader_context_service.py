from __future__ import annotations

from app.models import (
    CatalystEvent,
    CombinedSnapshot,
    IntradayBar,
    IntradayBarSeries,
    ProviderPriceData,
    SmallCapEvidence,
)
from services.trader_context_service import TraderContextService


def _snapshot() -> CombinedSnapshot:
    return CombinedSnapshot(
        ticker="HOT",
        timestamp="2026-06-29T14:00:00Z",
        previous_close=10.0,
        premarket_price=11.0,
        latest_price=10.8,
        open_price=None,
        high=None,
        low=None,
        volume=2_000_000,
        source_primary="fake",
        source_secondary=None,
        confidence="OK",
        sources=["fake"],
        market_cap=100_000_000,
        average_volume=1_000_000,
        yfinance_data=ProviderPriceData(
            ticker="HOT",
            source="fake",
            previous_close=10.0,
            premarket_price=11.0,
        ),
    )


class FakeSnapshotService:
    def build_snapshot(self, ticker):
        assert ticker == "HOT"
        return _snapshot()


class FakeEvidenceService:
    def enrich_candidates(self, candidates):
        candidate = candidates[0]
        assert candidate.ticker == "HOT"
        assert candidate.gap_pct == 10.0
        candidate.evidence = SmallCapEvidence(
            ticker="HOT",
            float_shares=5_000_000,
            is_low_float=True,
            float_rotation=0.4,
            catalysts=[
                CatalystEvent(
                    ticker="HOT",
                    headline="HOT wins supply deal",
                    published_at="2026-06-29T13:30:00Z",
                    source="fake-news",
                    url="https://example.test/hot",
                    confidence="OK",
                    catalyst_quality="hard",
                    recency_minutes=30,
                )
            ],
            missing_fields=["short_interest"],
            sources=["fake-news"],
        )
        candidate.missing_fields = ["short_interest"]
        return candidates


def _bar(close: float, timestamp: str, timeframe: str = "2Min") -> IntradayBar:
    return IntradayBar(
        ticker="HOT",
        timestamp=timestamp,
        open=close - 0.1,
        high=close + 0.5,
        low=close - 0.5,
        close=close,
        volume=1_000,
        timeframe=timeframe,
    )


class FakeBarProvider:
    source_name = "fake-bars"

    def get_bars(
        self,
        ticker,
        timeframe="2Min",
        start=None,
        end=None,
        limit=100,
    ):
        assert ticker == "HOT"
        if timeframe == "1Day":
            closes = [9, 10, 11, 15, 11, 12, 13]
            bars = [
                IntradayBar(
                    ticker="HOT",
                    timestamp=f"2026-06-{20 + index:02d}T20:00:00Z",
                    open=close,
                    high=close + (5 if index == 3 else 1),
                    low=close - (10 if index == 3 else 1),
                    close=close,
                    volume=10_000,
                    timeframe="1Day",
                )
                for index, close in enumerate(closes)
            ]
            return IntradayBarSeries("HOT", timeframe, bars, self.source_name, "daily-fetch")

        bars = [
            _bar(float(index), f"2026-06-29T14:{index:02d}:00Z")
            for index in range(1, 22)
        ]
        return IntradayBarSeries("HOT", timeframe, bars, self.source_name, "intra-fetch")


class EmptyBarProvider:
    source_name = "empty-bars"

    def get_bars(
        self,
        ticker,
        timeframe="2Min",
        start=None,
        end=None,
        limit=100,
    ):
        return IntradayBarSeries("HOT", timeframe, [], self.source_name, "empty-fetch")


def test_trader_context_includes_snapshot_and_evidence():
    service = TraderContextService(
        snapshot_service=FakeSnapshotService(),
        evidence_service=FakeEvidenceService(),
    )

    context = service.build_context("HOT", trader_profile="timothy_sykes")

    assert context["ticker"] == "HOT"
    assert context["trader_profile"] == "timothy_sykes"
    assert context["snapshot"]["gap_pct"] == 10.0
    assert context["snapshot"]["gap_basis"] == "premarket"
    assert context["snapshot"]["confidence"] == "OK"
    assert context["evidence"]["float_shares"] == 5_000_000
    assert context["evidence"]["catalysts"][0]["catalyst_quality"] == "hard"
    assert context["missing_fields"] == ["short_interest"]


def test_trader_context_can_include_technical_packet():
    service = TraderContextService(
        snapshot_service=FakeSnapshotService(),
        evidence_service=FakeEvidenceService(),
        bar_provider=FakeBarProvider(),
    )

    context = service.build_context(
        "HOT",
        include_intraday=True,
        include_daily=True,
    )

    intraday = context["technicals"]["intraday"]
    assert intraday["source"] == "fake-bars"
    assert intraday["bar_count"] == 21
    assert intraday["vwap"] is not None
    assert intraday["ema_9"] is not None
    assert intraday["ema_20"] is not None

    daily = context["technicals"]["daily"]
    assert daily["source"] == "fake-bars"
    assert daily["bar_count"] == 7
    assert {pivot["pivot_type"] for pivot in daily["pivots"]} == {
        "support",
        "resistance",
    }
    assert daily["prior_day"]["close"] == 13
    assert daily["consecutive_green_days"] == 2
    assert round(daily["run_up_pct"], 2) == 44.44


def test_trader_context_surfaces_missing_optional_technicals_without_inference():
    service = TraderContextService(
        snapshot_service=FakeSnapshotService(),
        evidence_service=FakeEvidenceService(),
    )

    context = service.build_context(
        "HOT",
        include_intraday=True,
        include_daily=True,
    )

    assert context["technicals"]["intraday"] is None
    assert context["technicals"]["daily"] is None
    assert "intraday_bars" in context["missing_fields"]
    assert "daily_bars" in context["missing_fields"]


def test_trader_context_bubbles_empty_bar_missing_fields_to_top_level():
    service = TraderContextService(
        snapshot_service=FakeSnapshotService(),
        evidence_service=FakeEvidenceService(),
        bar_provider=EmptyBarProvider(),
    )

    context = service.build_context(
        "HOT",
        include_intraday=True,
        include_daily=True,
    )

    assert context["technicals"]["intraday"]["confidence"] == "LOW_CONFIDENCE"
    assert context["technicals"]["daily"]["confidence"] == "LOW_CONFIDENCE"
    assert "intraday_bars" in context["missing_fields"]
    assert "daily_bars" in context["missing_fields"]
