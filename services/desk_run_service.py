from __future__ import annotations

from typing import Any

from app.models import utc_now_iso
from services.desk_explainer import DISCLAIMER, build_trader_context_explanation


DEFAULT_TRADER_PROFILES = [
    "timothy_sykes",
    "lance_breitstein",
    "alex_temiz",
    "tim_grittani",
]


class DeskRunService:
    def __init__(
        self,
        *,
        context_service: Any | None = None,
        universe_service: Any | None = None,
        small_cap_service: Any | None = None,
        bar_provider: Any | None = None,
    ) -> None:
        self.context_service = context_service
        self.universe_service = universe_service
        self.small_cap_service = small_cap_service
        self.bar_provider = bar_provider

    def run(
        self,
        *,
        tickers: list[str] | None,
        universe: str | list[str] | None = None,
        watchlist: str | list[str] | None = None,
        all_universes: bool = False,
        market: str | None = None,
        market_limit: int | None = None,
        max_workers: int | None = None,
        scan_preset_name: str = "sykes_small_cap_v0",
        trader_profiles: list[str] | None = None,
        include_intraday: bool = False,
        include_daily: bool = False,
        refresh_catalysts: bool = False,
    ) -> dict[str, Any]:
        selection = self._resolve_selection(
            tickers=tickers,
            universe=universe,
            watchlist=watchlist,
            all_universes=all_universes,
            market=market,
            market_limit=market_limit,
            max_workers=max_workers,
            scan_preset_name=scan_preset_name,
        )
        normalized_tickers = selection["tickers"]
        if not normalized_tickers and not selection["allow_empty"]:
            raise ValueError("selection resolved no tickers.")

        profiles = _normalize_profiles(trader_profiles)
        context_service = self._context_service(
            include_intraday=include_intraday,
            include_daily=include_daily,
        )
        ticker_packets = [
            self._ticker_packet(
                context_service=context_service,
                ticker=ticker,
                trader_profiles=profiles,
                include_intraday=include_intraday,
                include_daily=include_daily,
                refresh_catalysts=refresh_catalysts,
            )
            for ticker in normalized_tickers
        ]

        return {
            "generated_at": utc_now_iso(),
            "ticker_count": len(normalized_tickers),
            "selection": selection["summary"],
            "trader_profiles": profiles,
            "tickers": ticker_packets,
            "notes": [
                "Desk run is a read-only aggregation of data-layer context and trader-profile explainers."
            ],
            "disclaimer": DISCLAIMER,
        }

    def _context_service(
        self,
        *,
        include_intraday: bool,
        include_daily: bool,
    ) -> Any:
        if self.context_service is not None:
            return self.context_service

        bar_provider = self.bar_provider
        if bar_provider is None and (include_intraday or include_daily):
            from providers.alpaca_provider import AlpacaProvider

            bar_provider = AlpacaProvider()

        from services.trader_context_service import TraderContextService

        return TraderContextService(bar_provider=bar_provider)

    def _resolve_selection(
        self,
        *,
        tickers: list[str] | None,
        universe: str | list[str] | None,
        watchlist: str | list[str] | None,
        all_universes: bool,
        market: str | None,
        market_limit: int | None,
        max_workers: int | None,
        scan_preset_name: str,
    ) -> dict[str, Any]:
        if market:
            if any([tickers, universe, watchlist, all_universes]):
                raise ValueError(
                    "Use market by itself; do not combine it with universe/watchlist/tickers/all_universes."
                )
            return self._resolve_market_scan(
                market=market,
                market_limit=market_limit,
                max_workers=max_workers,
                scan_preset_name=scan_preset_name,
            )

        if not any([tickers, universe, watchlist, all_universes]):
            raise ValueError(
                "Provide at least one selection: tickers, universe, watchlist, market, or all_universes."
            )

        selection = self._universe_service().resolve_selection(
            universe=universe,
            watchlist=watchlist,
            tickers=tickers,
            all_universes=all_universes,
        )
        return {
            "tickers": list(selection.tickers),
            "allow_empty": False,
            "summary": {
                "source": "universe_service",
                "label": selection.label,
                "memberships": dict(selection.memberships),
            },
        }

    def _resolve_market_scan(
        self,
        *,
        market: str,
        market_limit: int | None,
        max_workers: int | None,
        scan_preset_name: str,
    ) -> dict[str, Any]:
        output = self._small_cap_service().scan(
            preset_name=scan_preset_name,
            market=market,
            market_limit=market_limit,
            max_workers=max_workers,
        )
        candidates = [_candidate_summary(candidate) for candidate in output.candidates]
        return {
            "tickers": [candidate["ticker"] for candidate in candidates],
            "allow_empty": True,
            "summary": {
                "source": "market_scan",
                "market": market,
                "preset": output.preset,
                "run_ids": list(output.run_ids),
                "candidate_count": output.candidate_count,
                "candidates": candidates,
                "notes": list(output.notes),
            },
        }

    def _universe_service(self) -> Any:
        if self.universe_service is not None:
            return self.universe_service
        from services.universe_service import UniverseService

        self.universe_service = UniverseService()
        return self.universe_service

    def _small_cap_service(self) -> Any:
        if self.small_cap_service is not None:
            return self.small_cap_service
        from services.small_cap_scanner_service import SmallCapScannerService

        self.small_cap_service = SmallCapScannerService()
        return self.small_cap_service

    def _ticker_packet(
        self,
        *,
        context_service: Any,
        ticker: str,
        trader_profiles: list[str],
        include_intraday: bool,
        include_daily: bool,
        refresh_catalysts: bool,
    ) -> dict[str, Any]:
        try:
            context = context_service.build_context(
                ticker=ticker,
                trader_profile="desk",
                include_intraday=include_intraday,
                include_daily=include_daily,
                refresh_catalysts=refresh_catalysts,
            )
        except Exception as exc:
            return {
                "ticker": ticker,
                "data_quality": {
                    "gap_basis": None,
                    "confidence": "ERROR",
                    "as_of": utc_now_iso(),
                    "sources": [],
                },
                "views": {},
                "missing_fields": ["context"],
                "errors": [_context_error(ticker, exc)],
            }

        views = {}
        for profile in trader_profiles:
            profile_context = dict(context)
            profile_context["trader_profile"] = profile
            views[profile] = build_trader_context_explanation(profile_context)

        return {
            "ticker": ticker,
            "data_quality": _data_quality(context),
            "views": views,
            "missing_fields": list(context.get("missing_fields") or []),
            "errors": [],
        }


def _normalize_tickers(tickers: list[str]) -> list[str]:
    normalized: list[str] = []
    seen = set()
    for ticker in tickers:
        value = str(ticker).strip().upper()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def _candidate_summary(candidate: Any) -> dict[str, Any]:
    return {
        "ticker": candidate.ticker,
        "grade": getattr(candidate, "grade", None),
        "score": getattr(candidate, "score", None),
        "gap_basis": getattr(candidate, "gap_basis", None),
        "confidence": getattr(candidate, "confidence", None),
        "missing_fields": list(getattr(candidate, "missing_fields", []) or []),
        "risk_notes": list(getattr(candidate, "risk_notes", []) or []),
    }


def _normalize_profiles(trader_profiles: list[str] | None) -> list[str]:
    if not trader_profiles:
        return list(DEFAULT_TRADER_PROFILES)

    normalized: list[str] = []
    seen = set()
    for profile in trader_profiles:
        value = str(profile).strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized or list(DEFAULT_TRADER_PROFILES)


def _data_quality(context: dict[str, Any]) -> dict[str, Any]:
    snapshot = context.get("snapshot") or {}
    return {
        "gap_basis": snapshot.get("gap_basis"),
        "confidence": snapshot.get("confidence"),
        "as_of": snapshot.get("timestamp"),
        "sources": list(snapshot.get("sources") or []),
    }


def _context_error(ticker: str, exc: Exception) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "confidence": "ERROR",
        "missing_fields": ["context"],
        "error": str(exc),
        "timestamp": utc_now_iso(),
        "notes": [
            "Desk context build failed for this ticker; no trader view was inferred."
        ],
    }
