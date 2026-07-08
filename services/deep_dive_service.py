from __future__ import annotations

from typing import Any

from app.models import model_to_dict, utc_now_iso
from services.desk_explainer import DISCLAIMER


GUARDRAILS = [
    "Reference levels are scanner facts, not order instructions.",
    "Every market number is data-layer sourced; unknown fields remain unknown.",
    DISCLAIMER,
]

SCANNER_PRIORITY_BY_PROFILE = {
    "lance_breitstein": [
        "breitstein_intraday",
        "temiz_first_red_day",
        "grittani_morning_panic",
    ],
    "alex_temiz": [
        "temiz_first_red_day",
        "grittani_morning_panic",
        "breitstein_intraday",
    ],
    "tim_grittani": [
        "grittani_morning_panic",
        "temiz_first_red_day",
        "breitstein_intraday",
    ],
}

DEFAULT_SCANNER_PRIORITY = [
    "grittani_morning_panic",
    "temiz_first_red_day",
    "breitstein_intraday",
]


class DeepDiveService:
    def __init__(
        self,
        *,
        context_service: Any | None = None,
        bar_provider: Any | None = None,
        breitstein_intraday_service: Any | None = None,
        temiz_service: Any | None = None,
        grittani_service: Any | None = None,
    ) -> None:
        self.context_service = context_service
        self.bar_provider = bar_provider
        self.breitstein_intraday_service = breitstein_intraday_service
        self.temiz_service = temiz_service
        self.grittani_service = grittani_service

    def run(
        self,
        *,
        ticker: str,
        trader_profile: str = "default",
        include_intraday: bool = True,
        include_daily: bool = True,
        refresh_catalysts: bool = False,
    ) -> dict[str, Any]:
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("ticker is required.")

        try:
            context = self._context_service().build_context(
                ticker=normalized,
                trader_profile=trader_profile,
                include_intraday=include_intraday,
                include_daily=include_daily,
                refresh_catalysts=refresh_catalysts,
            )
        except Exception as exc:
            return _context_error_packet(normalized, trader_profile, exc)

        snapshot = context.get("snapshot") or {}
        technicals = context.get("technicals") or {}
        missing_fields = list(context.get("missing_fields") or [])
        scanner_results = self._scanner_results(normalized, snapshot, missing_fields)
        warnings = _scanner_warnings(scanner_results)

        return {
            "ticker": normalized,
            "trader_profile": trader_profile,
            "status": "OK",
            "generated_at": utc_now_iso(),
            "snapshot": snapshot,
            "data_quality": _data_quality(snapshot),
            "daily_context": _daily_context(technicals.get("daily")),
            "technicals": technicals,
            "levels": _levels(technicals.get("daily")),
            "scanner_results": scanner_results,
            "evidence": context.get("evidence"),
            "trade_context": _trade_context(scanner_results, trader_profile),
            "missing_fields": missing_fields,
            "sources": list(context.get("sources") or []),
            "notes": list(context.get("notes") or []),
            "warnings": warnings,
            "guardrails": list(GUARDRAILS),
            "disclaimer": DISCLAIMER,
        }

    def _context_service(self) -> Any:
        if self.context_service is not None:
            return self.context_service
        from services.trader_context_service import TraderContextService

        self.context_service = TraderContextService(bar_provider=self.bar_provider)
        return self.context_service

    def _scanner_results(
        self,
        ticker: str,
        snapshot: dict[str, Any],
        context_missing_fields: list[str],
    ) -> dict[str, dict[str, Any]]:
        results = {
            "breitstein_intraday": self._breitstein_intraday_result(ticker),
            "temiz_first_red_day": self._temiz_result(ticker),
            "grittani_morning_panic": self._grittani_result(
                ticker,
                rvol=snapshot.get("rel_volume"),
            ),
        }
        return _apply_missing_bar_context(results, context_missing_fields)

    def _breitstein_intraday_result(self, ticker: str) -> dict[str, Any]:
        service = self.breitstein_intraday_service
        if service is None:
            if self.bar_provider is None:
                return _not_run("bar_provider_unavailable", ["intraday_bars"])
            from services.intraday_analysis_service import IntradayAnalysisService

            service = IntradayAnalysisService(self.bar_provider)

        try:
            series = service.fetch_bars(ticker)
            vwap = service.compute_vwap(series)
            signal = service.detect_entry_signal(series, vwap)
        except Exception as exc:
            return _scanner_error("breitstein_intraday", exc)

        if signal is None:
            return _no_signal()
        return _triggered(signal)

    def _temiz_result(self, ticker: str) -> dict[str, Any]:
        service = self.temiz_service
        if service is None:
            if self.bar_provider is None:
                return _not_run("bar_provider_unavailable", ["bar_data"])
            from services.temiz_analysis_service import TemizAnalysisService

            service = TemizAnalysisService(provider=self.bar_provider)

        try:
            signal = service.detect_first_red_day(ticker)
        except Exception as exc:
            return _scanner_error("temiz_first_red_day", exc)

        if signal is None:
            return _no_signal()
        return _triggered(signal)

    def _grittani_result(
        self,
        ticker: str,
        *,
        rvol: float | None,
    ) -> dict[str, Any]:
        if rvol is None:
            return _not_run("missing_rvol", ["rvol"])

        service = self.grittani_service
        if service is None:
            if self.bar_provider is None:
                return _not_run("bar_provider_unavailable", ["bar_data"])
            from services.grittani_analysis_service import GrittaniAnalysisService

            service = GrittaniAnalysisService(provider=self.bar_provider)

        try:
            signal = service.detect_morning_panic(ticker, rvol=rvol)
        except Exception as exc:
            return _scanner_error("grittani_morning_panic", exc)

        if signal is None:
            return _no_signal()
        return _triggered(signal)


def _data_quality(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "gap_basis": snapshot.get("gap_basis"),
        "confidence": snapshot.get("confidence"),
        "as_of": snapshot.get("timestamp"),
        "sources": list(snapshot.get("sources") or []),
    }


def _daily_context(daily: dict[str, Any] | None) -> dict[str, Any]:
    if not daily:
        return {
            "run_up_pct": None,
            "consecutive_green_days": None,
            "prior_day": None,
            "confidence": "UNKNOWN",
            "missing_fields": ["daily_bars"],
        }
    return {
        "run_up_pct": daily.get("run_up_pct"),
        "consecutive_green_days": daily.get("consecutive_green_days"),
        "prior_day": daily.get("prior_day") or daily.get("latest_bar"),
        "source": daily.get("source"),
        "fetched_at": daily.get("fetched_at"),
        "confidence": daily.get("confidence"),
        "missing_fields": list(daily.get("missing_fields") or []),
    }


def _levels(daily: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not daily:
        return []
    return list(daily.get("pivots") or [])


def _not_run(reason: str, missing_fields: list[str]) -> dict[str, Any]:
    return {
        "triggered": False,
        "signal": None,
        "reason": reason,
        "confidence": "LOW_CONFIDENCE",
        "missing_fields": list(missing_fields),
    }


def _apply_missing_bar_context(
    scanner_results: dict[str, dict[str, Any]],
    context_missing_fields: list[str],
) -> dict[str, dict[str, Any]]:
    requirements = {
        "breitstein_intraday": ["intraday_bars"],
        "temiz_first_red_day": ["daily_bars", "intraday_bars"],
        "grittani_morning_panic": ["daily_bars", "intraday_bars"],
    }
    output: dict[str, dict[str, Any]] = {}
    for scanner_name, result in scanner_results.items():
        missing = [
            field
            for field in requirements.get(scanner_name, [])
            if field in context_missing_fields
        ]
        if result.get("reason") == "no_signal" and missing:
            output[scanner_name] = _not_run("missing_bar_data", missing)
        else:
            output[scanner_name] = result
    return output


def _no_signal() -> dict[str, Any]:
    return {
        "triggered": False,
        "signal": None,
        "reason": "no_signal",
        "confidence": "OK",
        "missing_fields": [],
    }


def _triggered(signal: Any) -> dict[str, Any]:
    signal_dict = model_to_dict(signal)
    return {
        "triggered": True,
        "signal": signal_dict,
        "reason": None,
        "confidence": signal_dict.get("confidence"),
        "missing_fields": list(signal_dict.get("missing_fields") or []),
    }


def _scanner_error(scanner_name: str, exc: Exception) -> dict[str, Any]:
    return {
        "triggered": False,
        "signal": None,
        "reason": "error",
        "confidence": "ERROR",
        "missing_fields": ["bar_data"],
        "error": str(exc),
        "scanner": scanner_name,
    }


def _scanner_warnings(scanner_results: dict[str, dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for name, result in scanner_results.items():
        if result.get("confidence") == "ERROR":
            warnings.append(f"{name}: {result.get('error')}")
    return warnings


def _trade_context(
    scanner_results: dict[str, dict[str, Any]],
    trader_profile: str,
) -> dict[str, Any] | None:
    priority = SCANNER_PRIORITY_BY_PROFILE.get(trader_profile, DEFAULT_SCANNER_PRIORITY)
    for scanner_name in priority:
        result = scanner_results.get(scanner_name) or {}
        if not result.get("triggered"):
            continue
        signal = result.get("signal") or {}
        return _reference_context(scanner_name, signal)
    return None


def _reference_context(scanner_name: str, signal: dict[str, Any]) -> dict[str, Any]:
    if scanner_name == "breitstein_intraday":
        return {
            "reference_source": scanner_name,
            "entry_reference": signal.get("entry_price"),
            "risk_reference": signal.get("stop_price"),
            "target_reference": signal.get("target_price"),
            "confidence": signal.get("confidence"),
            "notes": list(signal.get("notes") or []),
        }
    if scanner_name == "temiz_first_red_day":
        return {
            "reference_source": scanner_name,
            "entry_reference": signal.get("breakdown_reference_price"),
            "risk_reference": signal.get("risk_reference_price"),
            "target_reference": None,
            "confidence": signal.get("confidence"),
            "notes": list(signal.get("notes") or []),
        }
    return {
        "reference_source": scanner_name,
        "entry_reference": signal.get("bounce_reference_price"),
        "risk_reference": signal.get("risk_reference_price"),
        "target_reference": None,
        "confidence": signal.get("confidence"),
        "notes": list(signal.get("notes") or []),
    }


def _context_error_packet(
    ticker: str,
    trader_profile: str,
    exc: Exception,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "trader_profile": trader_profile,
        "status": "ERROR",
        "generated_at": utc_now_iso(),
        "snapshot": None,
        "data_quality": {
            "gap_basis": None,
            "confidence": "ERROR",
            "as_of": utc_now_iso(),
            "sources": [],
        },
        "daily_context": None,
        "technicals": {"intraday": None, "daily": None},
        "levels": [],
        "scanner_results": {},
        "evidence": None,
        "trade_context": None,
        "missing_fields": ["context"],
        "sources": [],
        "notes": [],
        "warnings": [f"context: {exc}"],
        "guardrails": list(GUARDRAILS),
        "disclaimer": DISCLAIMER,
    }
