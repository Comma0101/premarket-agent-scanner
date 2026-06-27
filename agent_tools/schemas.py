from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ScanPremarketGapsInput(BaseModel):
    universe: str | None = None
    watchlist: str | None = None
    tickers: list[str] | None = None
    min_market_cap: float | None = None
    max_market_cap: float | None = None
    min_gap_abs: float | None = None
    direction: Literal["up", "down", "both"] = "both"
    limit: int = 50
    include_low_confidence: bool = True


class PremarketGapResult(BaseModel):
    ticker: str
    name: str | None
    universe: str | None
    market_cap: float | None
    previous_close: float | None
    premarket_price: float | None
    latest_price: float | None
    gap_pct: float | None
    confidence: str
    notes: str | None
    sources: list[str]
    timestamp: str | None = None


class ExplainPremarketMoverInput(BaseModel):
    ticker: str


class ExplainPremarketMoverOutput(BaseModel):
    ticker: str
    name: str | None
    market_cap: float | None
    previous_close: float | None
    premarket_price: float | None
    gap_pct: float | None
    confidence: str
    theme_memberships: list[str]
    notes: list[str]


class CompareUniverseGapsInput(BaseModel):
    universes: list[str]
    min_market_cap: float | None = None


class UniverseGapSummary(BaseModel):
    universe: str
    count_total: int
    count_gap_up: int
    count_gap_down: int
    avg_gap_pct: float | None
    max_gap_up_ticker: str | None
    max_gap_up_pct: float | None
    max_gap_down_ticker: str | None
    max_gap_down_pct: float | None
