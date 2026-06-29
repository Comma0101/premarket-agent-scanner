from __future__ import annotations

import pytest

from services.desk_run_service import DeskRunService


class FakeContextService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def build_context(self, **kwargs):
        self.calls.append(kwargs)
        ticker = kwargs["ticker"]
        if ticker == "BAD":
            raise RuntimeError("snapshot unavailable")
        return {
            "ticker": ticker,
            "trader_profile": kwargs["trader_profile"],
            "snapshot": {
                "ticker": ticker,
                "previous_close": 10.0,
                "premarket_price": 11.0,
                "latest_price": 11.0,
                "gap_pct": 10.0,
                "gap_dollar": 1.0,
                "gap_basis": "premarket",
                "market_cap": 100_000_000.0,
                "volume": 2_000_000.0,
                "rel_volume": 4.0,
                "confidence": "OK",
                "sources": ["fake"],
                "timestamp": "2026-06-29T13:30:00Z",
            },
            "evidence": {
                "float_shares": 5_000_000.0,
                "is_low_float": True,
                "catalysts": [{"headline": "HOT wins supply deal"}],
                "filings": [],
                "missing_fields": ["short_interest"],
            },
            "technicals": {"intraday": None, "daily": None},
            "missing_fields": ["short_interest"],
            "sources": ["fake"],
            "notes": ["context note"],
        }


def test_desk_run_builds_one_context_and_multiple_trader_views() -> None:
    context_service = FakeContextService()
    service = DeskRunService(context_service=context_service)

    out = service.run(
        tickers=["hot"],
        trader_profiles=["timothy_sykes", "lance_breitstein"],
        include_intraday=True,
        include_daily=False,
    )

    assert out["ticker_count"] == 1
    assert out["trader_profiles"] == ["timothy_sykes", "lance_breitstein"]
    assert len(context_service.calls) == 1
    assert context_service.calls[0]["ticker"] == "HOT"
    assert context_service.calls[0]["trader_profile"] == "desk"
    assert context_service.calls[0]["include_intraday"] is True
    assert out["tickers"][0]["ticker"] == "HOT"
    assert out["tickers"][0]["data_quality"] == {
        "gap_basis": "premarket",
        "confidence": "OK",
        "as_of": "2026-06-29T13:30:00Z",
        "sources": ["fake"],
    }
    assert set(out["tickers"][0]["views"]) == {"timothy_sykes", "lance_breitstein"}
    assert out["tickers"][0]["views"]["timothy_sykes"]["trader"] == "timothy_sykes"
    assert out["tickers"][0]["views"]["lance_breitstein"]["trader"] == "lance_breitstein"
    assert out["tickers"][0]["errors"] == []
    assert out["disclaimer"].startswith("Matches your filter")


def test_desk_run_surfaces_per_ticker_context_errors() -> None:
    service = DeskRunService(context_service=FakeContextService())

    out = service.run(tickers=["BAD"], trader_profiles=["timothy_sykes"])

    assert out["ticker_count"] == 1
    assert out["tickers"][0]["ticker"] == "BAD"
    assert out["tickers"][0]["views"] == {}
    assert out["tickers"][0]["errors"][0]["confidence"] == "ERROR"
    assert out["tickers"][0]["errors"][0]["missing_fields"] == ["context"]
    assert "snapshot unavailable" in out["tickers"][0]["errors"][0]["error"]


def test_desk_run_requires_tickers() -> None:
    service = DeskRunService(context_service=FakeContextService())

    with pytest.raises(ValueError, match="tickers"):
        service.run(tickers=[], trader_profiles=["timothy_sykes"])
