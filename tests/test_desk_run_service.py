from __future__ import annotations

from types import SimpleNamespace

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


class FakeUniverseService:
    def resolve_selection(self, **kwargs):
        assert kwargs["watchlist"] == "ACTIVE"
        assert kwargs["universe"] is None
        assert kwargs["tickers"] is None
        assert kwargs["all_universes"] is False
        return SimpleNamespace(
            tickers=["MRVL", "HOOD"],
            memberships={
                "MRVL": ["WATCHLIST:ACTIVE"],
                "HOOD": ["WATCHLIST:ACTIVE"],
            },
            label="WATCHLIST:ACTIVE",
        )


class FakeSmallCapCandidate:
    def __init__(self, ticker: str, score: int) -> None:
        self.ticker = ticker
        self.grade = "A_WATCH"
        self.score = score
        self.gap_basis = "premarket"
        self.confidence = "OK"
        self.missing_fields = ["short_interest"]
        self.risk_notes = []


class FakeSmallCapService:
    def scan(self, **kwargs):
        assert kwargs["preset_name"] == "sykes_small_cap_v0"
        assert kwargs["market"] == "us-listed"
        assert kwargs["market_limit"] == 50
        assert kwargs["max_workers"] == 4
        return SimpleNamespace(
            preset="sykes_small_cap_v0",
            run_ids=["run-1"],
            candidate_count=2,
            candidates=[
                FakeSmallCapCandidate("HOT", 90),
                FakeSmallCapCandidate("COOL", 75),
            ],
            notes=["market scan note"],
        )


class FakeEmptySmallCapService:
    def scan(self, **kwargs):
        return SimpleNamespace(
            preset=kwargs["preset_name"],
            run_ids=["empty-run"],
            candidate_count=0,
            candidates=[],
            notes=["no candidates"],
        )


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


def test_desk_run_resolves_watchlist_selection() -> None:
    context_service = FakeContextService()
    service = DeskRunService(
        context_service=context_service,
        universe_service=FakeUniverseService(),
    )

    out = service.run(
        tickers=None,
        watchlist="ACTIVE",
        trader_profiles=["lance_breitstein"],
    )

    assert out["selection"]["source"] == "universe_service"
    assert out["selection"]["label"] == "WATCHLIST:ACTIVE"
    assert out["selection"]["memberships"]["MRVL"] == ["WATCHLIST:ACTIVE"]
    assert out["ticker_count"] == 2
    assert [call["ticker"] for call in context_service.calls] == ["MRVL", "HOOD"]


def test_desk_run_uses_market_scan_candidates_as_tickers() -> None:
    context_service = FakeContextService()
    service = DeskRunService(
        context_service=context_service,
        small_cap_service=FakeSmallCapService(),
    )

    out = service.run(
        tickers=None,
        market="us-listed",
        market_limit=50,
        max_workers=4,
        trader_profiles=["timothy_sykes"],
    )

    assert out["selection"]["source"] == "market_scan"
    assert out["selection"]["market"] == "us-listed"
    assert out["selection"]["candidate_count"] == 2
    assert out["selection"]["run_ids"] == ["run-1"]
    assert out["selection"]["candidates"][0]["ticker"] == "HOT"
    assert out["selection"]["notes"] == ["market scan note"]
    assert out["ticker_count"] == 2
    assert [call["ticker"] for call in context_service.calls] == ["HOT", "COOL"]


def test_desk_run_market_scan_allows_zero_candidates() -> None:
    context_service = FakeContextService()
    service = DeskRunService(
        context_service=context_service,
        small_cap_service=FakeEmptySmallCapService(),
    )

    out = service.run(
        tickers=None,
        market="us-listed",
        market_limit=10,
        trader_profiles=["timothy_sykes"],
    )

    assert out["selection"]["source"] == "market_scan"
    assert out["selection"]["candidate_count"] == 0
    assert out["selection"]["run_ids"] == ["empty-run"]
    assert out["ticker_count"] == 0
    assert out["tickers"] == []
    assert context_service.calls == []


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

    with pytest.raises(ValueError, match="selection"):
        service.run(tickers=[], trader_profiles=["timothy_sykes"])
