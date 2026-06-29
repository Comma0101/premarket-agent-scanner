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
        bar_provider: Any | None = None,
    ) -> None:
        self.context_service = context_service
        self.bar_provider = bar_provider

    def run(
        self,
        *,
        tickers: list[str],
        trader_profiles: list[str] | None = None,
        include_intraday: bool = False,
        include_daily: bool = False,
        refresh_catalysts: bool = False,
    ) -> dict[str, Any]:
        normalized_tickers = _normalize_tickers(tickers)
        if not normalized_tickers:
            raise ValueError("tickers is required and must be non-empty.")

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
