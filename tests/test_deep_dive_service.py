from __future__ import annotations

from app.models import (
    BreitsteinEntrySignal,
    FirstRedDaySignal,
    IntradayBarSeries,
    utc_now_iso,
)
from services.deep_dive_service import DeepDiveService


class FakeContextService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build_context(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "ticker": "HOT",
            "trader_profile": kwargs["trader_profile"],
            "generated_at": "2026-06-30T12:28:15Z",
            "snapshot": {
                "ticker": "HOT",
                "previous_close": 2.0,
                "premarket_price": 2.5,
                "latest_price": 2.5,
                "gap_pct": 25.0,
                "gap_dollar": 0.5,
                "gap_basis": "premarket",
                "market_cap": 75_000_000.0,
                "volume": 3_000_000.0,
                "rel_volume": 6.5,
                "confidence": "OK",
                "sources": ["fake_snapshot"],
                "timestamp": "2026-06-30T12:28:00Z",
            },
            "evidence": {
                "ticker": "HOT",
                "float_shares": 8_000_000.0,
                "float_rotation": 0.375,
                "catalysts": [{"headline": "HOT signs distribution deal"}],
                "filings": [],
                "former_runner": None,
                "missing_fields": ["short_interest"],
                "risk_notes": [],
                "sources": ["fake_evidence"],
            },
            "technicals": {
                "intraday": {
                    "source": "fake_bars",
                    "fetched_at": "2026-06-30T12:29:00Z",
                    "timeframe": "2Min",
                    "bar_count": 20,
                    "latest_bar": {"close": 2.42},
                    "vwap": 2.38,
                    "ema_9": 2.36,
                    "ema_20": 2.28,
                    "confidence": "OK",
                    "missing_fields": [],
                },
                "daily": {
                    "source": "fake_daily",
                    "fetched_at": "2026-06-30T12:29:00Z",
                    "timeframe": "1Day",
                    "bar_count": 40,
                    "latest_bar": {"open": 1.8, "high": 2.1, "low": 1.7, "close": 2.0},
                    "pivots": [
                        {
                            "pivot_type": "resistance",
                            "price": 3.25,
                            "timestamp": "2026-06-25T20:00:00Z",
                        },
                        {
                            "pivot_type": "support",
                            "price": 1.75,
                            "timestamp": "2026-06-24T20:00:00Z",
                        },
                    ],
                    "confidence": "OK",
                    "missing_fields": [],
                },
            },
            "missing_fields": ["short_interest"],
            "sources": ["fake_snapshot", "fake_evidence", "fake_bars", "fake_daily"],
            "notes": ["Trader context is a read-only data packet, not execution advice."],
        }


class FakeBreitsteinIntradayService:
    def fetch_bars(self, ticker, timeframe="2Min", start="", end="", limit=100):
        return IntradayBarSeries(
            ticker=ticker,
            timeframe=timeframe,
            bars=[],
            source="fake_bars",
            fetched_at=utc_now_iso(),
        )

    def compute_vwap(self, series):
        return 2.38

    def detect_entry_signal(self, series, vwap):
        return BreitsteinEntrySignal(
            ticker=series.ticker,
            direction="long",
            entry_price=2.46,
            stop_price=2.31,
            target_price=2.8,
            prior_bar_high=2.45,
            prior_bar_low=2.31,
            vwap=vwap,
            vwap_filter_passed=True,
            volume_2x_confirmed=True,
            consecutive_bars=-3,
            rate_of_change=-4.2,
            bollinger_width=0.18,
            timestamp="2026-06-30T14:08:00Z",
            confidence="OK",
        )


class FakeTemizService:
    def detect_first_red_day(self, ticker):
        return FirstRedDaySignal(
            ticker=ticker,
            consecutive_green_days=4,
            breakdown_reference_price=2.0,
            risk_reference_price=2.62,
            prior_day_close=2.0,
            hod_before_breakdown=2.62,
            breakdown_bar_low=1.96,
            vwap=2.3,
            vwap_filter_passed=True,
            timestamp="2026-06-30T14:12:00Z",
            source="fake_bars",
            fetched_at="2026-06-30T14:13:00Z",
            confidence="OK",
            notes=["reference only"],
        )


class FakeGrittaniService:
    def __init__(self) -> None:
        self.rvol_seen: float | None = None

    def detect_morning_panic(self, ticker, rvol=None):
        self.rvol_seen = rvol
        return None


class FakeNoSignalBreitsteinService:
    def fetch_bars(self, ticker, timeframe="2Min", start="", end="", limit=100):
        return IntradayBarSeries(
            ticker=ticker,
            timeframe=timeframe,
            bars=[],
            source="fake_bars",
            fetched_at=utc_now_iso(),
        )

    def compute_vwap(self, series):
        return None

    def detect_entry_signal(self, series, vwap):
        return None


class FakeNoSignalTemizService:
    def detect_first_red_day(self, ticker):
        return None


def test_deep_dive_builds_context_scanner_results_and_trade_references() -> None:
    context_service = FakeContextService()
    grittani_service = FakeGrittaniService()
    service = DeepDiveService(
        context_service=context_service,
        breitstein_intraday_service=FakeBreitsteinIntradayService(),
        temiz_service=FakeTemizService(),
        grittani_service=grittani_service,
    )

    out = service.run(
        ticker=" hot ",
        trader_profile="alex_temiz",
        include_intraday=True,
        include_daily=True,
    )

    assert context_service.calls[0]["ticker"] == "HOT"
    assert context_service.calls[0]["trader_profile"] == "alex_temiz"
    assert out["ticker"] == "HOT"
    assert out["status"] == "OK"
    assert out["snapshot"]["gap_basis"] == "premarket"
    assert out["data_quality"] == {
        "gap_basis": "premarket",
        "confidence": "OK",
        "as_of": "2026-06-30T12:28:00Z",
        "sources": ["fake_snapshot"],
    }
    assert out["evidence"]["float_shares"] == 8_000_000.0
    assert out["technicals"]["intraday"]["vwap"] == 2.38
    assert out["levels"][0]["pivot_type"] == "resistance"
    assert out["daily_context"]["prior_day"]["close"] == 2.0
    assert out["scanner_results"]["breitstein_intraday"]["triggered"] is True
    assert out["scanner_results"]["temiz_first_red_day"]["triggered"] is True
    assert out["scanner_results"]["grittani_morning_panic"]["triggered"] is False
    assert out["scanner_results"]["grittani_morning_panic"]["reason"] == "no_signal"
    assert grittani_service.rvol_seen == 6.5
    assert out["trade_context"] == {
        "reference_source": "temiz_first_red_day",
        "entry_reference": 2.0,
        "risk_reference": 2.62,
        "target_reference": None,
        "confidence": "OK",
        "notes": ["reference only"],
    }
    assert "not buy/sell advice" in out["disclaimer"]
    assert "Reference levels" in out["guardrails"][0]


def test_deep_dive_surfaces_scanner_errors_as_data() -> None:
    class RaisingTemizService:
        def detect_first_red_day(self, ticker):
            raise RuntimeError("bars unavailable")

    service = DeepDiveService(
        context_service=FakeContextService(),
        temiz_service=RaisingTemizService(),
    )

    out = service.run(ticker="HOT", include_intraday=False, include_daily=False)

    assert out["scanner_results"]["temiz_first_red_day"]["triggered"] is False
    assert out["scanner_results"]["temiz_first_red_day"]["confidence"] == "ERROR"
    assert out["scanner_results"]["temiz_first_red_day"]["missing_fields"] == [
        "bar_data"
    ]
    assert "bars unavailable" in out["scanner_results"]["temiz_first_red_day"]["error"]
    assert out["warnings"] == ["temiz_first_red_day: bars unavailable"]


def test_deep_dive_marks_no_signal_as_missing_data_when_context_lacks_bars() -> None:
    class MissingBarsContextService(FakeContextService):
        def build_context(self, **kwargs):
            context = super().build_context(**kwargs)
            context["missing_fields"] = ["intraday_bars", "daily_bars"]
            context["technicals"]["intraday"] = {
                "confidence": "LOW_CONFIDENCE",
                "missing_fields": ["intraday_bars"],
            }
            context["technicals"]["daily"] = {
                "confidence": "LOW_CONFIDENCE",
                "missing_fields": ["daily_bars"],
            }
            return context

    service = DeepDiveService(
        context_service=MissingBarsContextService(),
        breitstein_intraday_service=FakeNoSignalBreitsteinService(),
        temiz_service=FakeNoSignalTemizService(),
        grittani_service=FakeGrittaniService(),
    )

    out = service.run(ticker="HOT")

    assert out["scanner_results"]["breitstein_intraday"]["reason"] == "missing_bar_data"
    assert out["scanner_results"]["breitstein_intraday"]["confidence"] == "LOW_CONFIDENCE"
    assert out["scanner_results"]["breitstein_intraday"]["missing_fields"] == [
        "intraday_bars"
    ]
    assert out["scanner_results"]["temiz_first_red_day"]["reason"] == "missing_bar_data"
    assert out["scanner_results"]["temiz_first_red_day"]["missing_fields"] == [
        "daily_bars",
        "intraday_bars",
    ]
    assert out["scanner_results"]["grittani_morning_panic"]["reason"] == "missing_bar_data"
    assert out["scanner_results"]["grittani_morning_panic"]["missing_fields"] == [
        "daily_bars",
        "intraday_bars",
    ]
