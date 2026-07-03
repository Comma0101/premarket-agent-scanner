from __future__ import annotations

from typing import Any

from app.db import get_cached_news, get_lance_outcomes
from app.models import CatalystEvent
from services.lance_market_scan_service import LanceMarketScanService
from services.scanner_service import compute_gap_pct, gap_basis_for
from services.snapshot_service import SnapshotService
from services.universe_service import UniverseService


class LanceAdvancedContextService:
    """Advanced Lance layer: market context, playbook fit, and memory hooks."""

    def __init__(
        self,
        *,
        market_scan_service: Any | None = None,
        universe_service: Any | None = None,
        benchmark_service: Any | None = None,
        catalyst_service: Any | None = None,
        db_path: str | None = None,
    ) -> None:
        self.market_scan_service = market_scan_service or LanceMarketScanService(db_path=db_path)
        self.universe_service = universe_service or UniverseService()
        self.benchmark_service = benchmark_service or BenchmarkMoveService(db_path=db_path)
        self.catalyst_service = catalyst_service or CachedCatalystService(db_path=db_path)
        self.db_path = db_path

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        base = self.market_scan_service.scan(**kwargs)
        benchmarks = self.benchmark_service.benchmark_moves()
        watchlist = [
            self._enrich_candidate(candidate, benchmarks)
            for candidate in base.get("watchlist", [])
        ]
        return {
            **base,
            "mode": "advanced",
            "strategy": "Advanced Lance intraday co-pilot",
            "watchlist": watchlist,
            "market_context": {
                "benchmarks": benchmarks,
                "theme_rotation": _theme_rotation(watchlist, self.universe_service),
            },
            "playbook_library": _playbook_library(),
        }

    def _enrich_candidate(
        self,
        candidate: dict[str, Any],
        benchmarks: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        ticker = str(candidate.get("ticker") or "").upper()
        memberships = self.universe_service.memberships_for_ticker(ticker)
        catalysts = self.catalyst_service.get_recent_catalysts(ticker)
        catalyst_context = _classify_catalysts(catalysts)
        opening_range_regime = _opening_range_regime(candidate)
        relative_strength = _relative_strength(candidate, benchmarks, memberships)
        playbook_fit = _playbook_fit(
            candidate,
            catalyst_context=catalyst_context,
            opening_range_regime=opening_range_regime,
            relative_strength=relative_strength,
        )
        market_memory = _market_memory(self.db_path, ticker)
        return {
            **candidate,
            "memberships": memberships,
            "relative_strength": relative_strength,
            "catalyst": catalyst_context,
            "opening_range_regime": opening_range_regime,
            "playbook_fit": playbook_fit,
            "market_memory": market_memory,
        }


class BenchmarkMoveService:
    def __init__(self, *, snapshot_service: Any | None = None, db_path: str | None = None) -> None:
        self.snapshot_service = snapshot_service or SnapshotService.with_configured_providers(db_path)

    def benchmark_moves(self) -> dict[str, dict[str, Any]]:
        output = {}
        for ticker in ["SPY", "QQQ", "SMH", "XLK", "IWM"]:
            snapshot = self.snapshot_service.build_snapshot(ticker)
            price = (
                snapshot.premarket_price
                if snapshot.premarket_price is not None
                else snapshot.latest_price
            )
            basis = gap_basis_for(snapshot)
            output[ticker] = {
                "gap_pct": compute_gap_pct(snapshot.previous_close, price),
                "gap_basis": basis,
                "confidence": snapshot.confidence,
                "as_of": snapshot.timestamp,
                "sources": list(snapshot.sources),
            }
        return output


class CachedCatalystService:
    def __init__(self, *, db_path: str | None = None) -> None:
        self.db_path = db_path

    def get_recent_catalysts(self, ticker: str) -> list[CatalystEvent]:
        return get_cached_news(self.db_path, ticker, limit=5)


def _relative_strength(
    candidate: dict[str, Any],
    benchmarks: dict[str, dict[str, Any]],
    memberships: list[str],
) -> dict[str, Any]:
    gap_pct = (candidate.get("data_quality") or {}).get("gap_pct")
    qqq_gap = (benchmarks.get("QQQ") or {}).get("gap_pct")
    spy_gap = (benchmarks.get("SPY") or {}).get("gap_pct")
    sector_etf = _sector_etf_for_memberships(memberships)
    sector_gap = (benchmarks.get(sector_etf) or {}).get("gap_pct") if sector_etf else None
    vs_qqq = _spread(gap_pct, qqq_gap)
    vs_spy = _spread(gap_pct, spy_gap)
    vs_sector_etf = _spread(gap_pct, sector_gap)
    classification = "unknown"
    if vs_qqq is not None:
        if vs_qqq >= 2:
            classification = "strong"
        elif vs_qqq <= -2:
            classification = "weak"
        else:
            classification = "in_line"
    return {
        "vs_QQQ": vs_qqq,
        "vs_SPY": vs_spy,
        "sector_etf": sector_etf,
        "vs_sector_etf": vs_sector_etf,
        "classification": classification,
        "benchmark": "QQQ",
    }


def _spread(value: Any, benchmark: Any) -> float | None:
    if isinstance(value, int | float) and isinstance(benchmark, int | float):
        return round(float(value) - float(benchmark), 2)
    return None


def _sector_etf_for_memberships(memberships: list[str]) -> str | None:
    ordered_map = [
        ("AI_SEMIS_MEMORY", "SMH"),
        ("AI_WAVE_1_COMPUTE", "SMH"),
        ("AI_WAVE_2_MEMORY_OPTICAL", "SMH"),
        ("AI_WAVE_3_EQUIPMENT", "SMH"),
        ("SERVER_INFRA", "XLK"),
        ("AI_INFRA_POWER", "XLK"),
        ("AI_WAVE_4_POWER_COOLING", "XLK"),
        ("SPECULATIVE_ACTIVE", "IWM"),
        ("MAG7", "QQQ"),
    ]
    membership_set = {str(membership).replace("WATCHLIST:", "") for membership in memberships}
    for theme, etf in ordered_map:
        if theme in membership_set:
            return etf
    return None


def _market_memory(db_path: str | None, ticker: str) -> dict[str, Any]:
    recent = get_lance_outcomes(db_path, ticker=ticker, limit=5)
    return {
        "recent_outcomes_available": bool(recent),
        "recent_outcomes": recent,
        "note": (
            "Recent Lance outcomes are journaled observations."
            if recent
            else "No recent Lance outcomes found; do not infer setup history."
        ),
    }


def _theme_rotation(
    watchlist: list[dict[str, Any]],
    universe_service: Any,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for candidate in watchlist:
        ticker = str(candidate.get("ticker") or "").upper()
        memberships = candidate.get("memberships") or universe_service.memberships_for_ticker(ticker)
        for membership in memberships:
            if str(membership).startswith("WATCHLIST:"):
                continue
            grouped.setdefault(str(membership), []).append(candidate)

    rows = []
    for theme, candidates in grouped.items():
        gap_values = [
            (candidate.get("data_quality") or {}).get("gap_pct")
            for candidate in candidates
            if isinstance((candidate.get("data_quality") or {}).get("gap_pct"), int | float)
        ]
        rvol_values = [
            (candidate.get("data_quality") or {}).get("rel_volume")
            for candidate in candidates
            if isinstance((candidate.get("data_quality") or {}).get("rel_volume"), int | float)
        ]
        rows.append({
            "theme": theme,
            "ticker_count": len(candidates),
            "avg_gap_pct": _average(gap_values),
            "avg_rel_volume": _average(rvol_values),
            "tickers": [candidate["ticker"] for candidate in candidates],
        })
    rows.sort(
        key=lambda row: (
            row["ticker_count"],
            row["avg_gap_pct"] if row["avg_gap_pct"] is not None else -999,
        ),
        reverse=True,
    )
    return rows


def _average(values: list[Any]) -> float | None:
    if not values:
        return None
    return round(sum(float(value) for value in values) / len(values), 2)


def _classify_catalysts(catalysts: list[CatalystEvent]) -> dict[str, Any]:
    if not catalysts:
        return {
            "primary_type": "no_known_catalyst",
            "events": [],
            "sources": [],
        }
    events = [_catalyst_to_dict(event) for event in catalysts]
    primary_type = _catalyst_type(catalysts[0].headline)
    return {
        "primary_type": primary_type,
        "events": events,
        "sources": [event.source for event in catalysts if event.source],
    }


def _catalyst_to_dict(event: CatalystEvent) -> dict[str, Any]:
    return {
        "ticker": event.ticker,
        "headline": event.headline,
        "published_at": event.published_at,
        "source": event.source,
        "url": event.url,
        "confidence": event.confidence,
        "catalyst_quality": event.catalyst_quality,
    }


def _catalyst_type(headline: str) -> str:
    lower = headline.lower()
    if any(token in lower for token in ["earnings", "guidance", "revenue", "eps"]):
        return "earnings"
    if any(token in lower for token in ["fda", "phase", "clinical", "trial"]):
        return "biotech"
    if any(token in lower for token in ["offering", "s-3", "atm", "warrant"]):
        return "financing_risk"
    if any(token in lower for token in ["recall", "regulator", "investigation"]):
        return "regulatory_risk"
    if any(token in lower for token in ["contract", "partnership", "customer", "order"]):
        return "business_update"
    return "other_news"


def _opening_range_regime(candidate: dict[str, Any]) -> str:
    plan = candidate.get("plan") or {}
    intraday = plan.get("intraday") or {}
    conditions = candidate.get("conditions") or {}
    if candidate.get("trigger_reference") is not None:
        return "range_break"
    if intraday.get("chop") is True or (conditions.get("chop_filter") or {}).get("status") == "FAIL":
        return "compressed_chop"
    bar_count = intraday.get("bar_count")
    if isinstance(bar_count, int | float) and bar_count < 15:
        return "opening_range_forming"
    return "inside_opening_range"


def _playbook_fit(
    candidate: dict[str, Any],
    *,
    catalyst_context: dict[str, Any],
    opening_range_regime: str,
    relative_strength: dict[str, Any],
) -> dict[str, Any]:
    gap_pct = (candidate.get("data_quality") or {}).get("gap_pct")
    rel_volume = (candidate.get("data_quality") or {}).get("rel_volume")
    state = candidate.get("state")
    primary = "watchlist_context"
    reasons = []

    if (
        catalyst_context["primary_type"] == "earnings"
        and isinstance(gap_pct, int | float)
        and gap_pct > 0
        and relative_strength.get("classification") == "strong"
    ):
        primary = "earnings_continuation"
        reasons.append("positive earnings catalyst with relative strength")
    elif state == "triggered_reference" or (
        isinstance(gap_pct, int | float)
        and gap_pct < 0
        and isinstance(rel_volume, int | float)
        and rel_volume >= 3
    ):
        primary = "mean_reversion_after_capitulation"
        reasons.append("large move with Lance trigger/participation context")
    elif opening_range_regime == "inside_opening_range" and state in {"setup_forming", "watching"}:
        primary = "consolidation_breakout"
        reasons.append("inside opening range while Lance conditions are forming")

    return {
        "primary": primary,
        "secondary": _secondary_playbooks(primary),
        "reasons": reasons,
    }


def _secondary_playbooks(primary: str) -> list[str]:
    playbooks = [
        "mean_reversion_after_capitulation",
        "consolidation_breakout",
        "earnings_continuation",
    ]
    return [playbook for playbook in playbooks if playbook != primary]


def _playbook_library() -> list[dict[str, str]]:
    return [
        {
            "name": "mean_reversion_after_capitulation",
            "waits_for": "extended move, RVOL participation, pressure, and a reference break",
            "invalidates_if": "chop/compression or failed reference break",
        },
        {
            "name": "consolidation_breakout",
            "waits_for": "inside opening range or consolidation with pressure building",
            "invalidates_if": "range loses structure or RVOL fades",
        },
        {
            "name": "earnings_continuation",
            "waits_for": "earnings catalyst plus relative strength versus QQQ/SPY",
            "invalidates_if": "relative strength fails or catalyst reaction reverses",
        },
    ]
