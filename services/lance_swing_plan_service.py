from __future__ import annotations

from typing import Any

from app.models import CombinedSnapshot, IntradayBar, IntradayBarSeries, model_to_dict
from services.daily_bar_service import DailyBarService
from services.scanner_service import (
    compute_gap_dollar,
    compute_gap_pct,
    compute_rel_volume,
    gap_basis_for,
    rel_volume_basis_for,
)
from services.session_time_service import data_caveat_for, format_et, session_mode_for


DISCLAIMER = (
    "Swing plans are not buy/sell advice. They are daily-chart watch references "
    "from the data layer; verify before acting."
)
DEFAULT_LOOKBACK_DAYS = 60


class LanceSwingPlanService:
    """Build Lance-style daily/swing watch plans without adding execution logic."""

    def __init__(
        self,
        *,
        snapshot_service: Any | None = None,
        daily_bar_provider: Any | None = None,
        daily_service: DailyBarService | None = None,
    ) -> None:
        self.snapshot_service = snapshot_service
        self.daily_bar_provider = daily_bar_provider
        self.daily_service = daily_service or DailyBarService()
        self._benchmark_cache: dict[int, dict[str, dict[str, Any]]] = {}

    def build(
        self,
        *,
        tickers: list[str] | str,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        data_quality_overrides: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        resolved = _parse_tickers(tickers)
        overrides = _normalize_data_quality_overrides(data_quality_overrides)
        plans = [
            self.build_plan(
                ticker,
                lookback_days=lookback_days,
                data_quality_override=overrides.get(ticker),
            )
            for ticker in resolved
        ]
        plans.sort(key=lambda plan: (plan["score"], plan["ticker"]), reverse=True)
        return {
            "agent_name": "lance_swing",
            "strategy": "Lance Breitstein daily/swing planning",
            "timeframe": "daily_swing",
            "ticker_count": len(resolved),
            "plan_count": len(plans),
            "plans": plans,
            "groups": _group_plans(plans),
            "disclaimer": DISCLAIMER,
        }

    def build_plan(
        self,
        ticker: str,
        *,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        data_quality_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("ticker is required.")

        snapshot = (
            None
            if data_quality_override is not None
            else self._snapshot_service().build_snapshot(normalized)
        )
        series = self._fetch_daily_bars(normalized, lookback_days)
        completed_bars = self._completed_bars(series)
        benchmarks = self._benchmark_context(lookback_days)
        daily_context = _daily_context(series, completed_bars)
        relative_strength = _relative_strength(daily_context, benchmarks)
        data_quality = (
            dict(data_quality_override)
            if data_quality_override is not None
            else _data_quality(snapshot)
        )
        missing_fields = _missing_fields(
            completed_bars=completed_bars,
            data_quality=data_quality,
        )
        conditions = _conditions(
            data_quality=data_quality,
            daily_context=daily_context,
            relative_strength=relative_strength,
            missing_fields=missing_fields,
        )
        state = _state(
            data_quality=data_quality,
            daily_context=daily_context,
            relative_strength=relative_strength,
            missing_fields=missing_fields,
            conditions=conditions,
        )
        playbook = _playbook(state, daily_context, relative_strength)
        bias = _bias(state)
        score = _score(state, daily_context, relative_strength)

        return {
            "ticker": normalized,
            "trader": "lance_breitstein",
            "timeframe": "daily_swing",
            "state": state,
            "state_reason": _state_reason(state),
            "lance_quality_grade": _quality_grade(state),
            "playbook": playbook,
            "bias": bias,
            "bias_reason": _bias_reason(state),
            "score": score,
            "data_quality": data_quality,
            "daily_context": daily_context,
            "relative_strength": relative_strength,
            "conditions": conditions,
            "waiting_for": _waiting_for(state, daily_context, relative_strength),
            "invalidates_if": _invalidates_if(state, daily_context),
            "manual_review_questions": _manual_review_questions(state),
            "next_step": _next_step(state),
            "missing_fields": missing_fields,
            "disclaimer": DISCLAIMER,
        }

    def _snapshot_service(self) -> Any:
        if self.snapshot_service is None:
            from services.snapshot_service import SnapshotService

            self.snapshot_service = SnapshotService.with_configured_providers()
        return self.snapshot_service

    def _provider(self) -> Any:
        if self.daily_bar_provider is None:
            from providers.alpaca_provider import AlpacaProvider

            self.daily_bar_provider = AlpacaProvider()
        return self.daily_bar_provider

    def _fetch_daily_bars(self, ticker: str, lookback_days: int) -> IntradayBarSeries | None:
        try:
            return self._provider().get_bars(
                ticker,
                "1Day",
                "",
                "",
                max(1, int(lookback_days)),
            )
        except Exception:
            return None

    def _completed_bars(self, series: IntradayBarSeries | None) -> list[IntradayBar]:
        if series is None:
            return []
        return self.daily_service._get_completed_bars(series)

    def _benchmark_context(self, lookback_days: int) -> dict[str, dict[str, Any]]:
        cache_key = max(1, int(lookback_days))
        if cache_key in self._benchmark_cache:
            return _copy_benchmark_context(self._benchmark_cache[cache_key])

        context = {}
        for ticker in ["QQQ", "SPY"]:
            series = self._fetch_daily_bars(ticker, lookback_days)
            bars = self._completed_bars(series)
            context[ticker] = {
                "return_20d_pct": _return_pct(bars, 20),
                "source": series.source if series else None,
                "fetched_at": series.fetched_at if series else None,
                "bar_count": len(bars),
            }
        self._benchmark_cache[cache_key] = context
        return _copy_benchmark_context(context)


def _parse_tickers(tickers: list[str] | str) -> list[str]:
    raw = tickers.split(",") if isinstance(tickers, str) else tickers
    seen: set[str] = set()
    output: list[str] = []
    for value in raw:
        normalized = str(value or "").strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    if not output:
        raise ValueError("at least one ticker is required.")
    return output


def _normalize_data_quality_overrides(
    overrides: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if not overrides:
        return {}
    output = {}
    for ticker, data_quality in overrides.items():
        normalized = str(ticker or "").strip().upper()
        if normalized and isinstance(data_quality, dict):
            output[normalized] = dict(data_quality)
    return output


def _copy_benchmark_context(
    context: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {ticker: dict(values) for ticker, values in context.items()}


def _data_quality(snapshot: CombinedSnapshot) -> dict[str, Any]:
    price = snapshot.premarket_price if snapshot.premarket_price is not None else snapshot.latest_price
    gap_basis = gap_basis_for(snapshot)
    return {
        "confidence": snapshot.confidence,
        "data_status": snapshot.data_status,
        "provider_failures": dict(snapshot.provider_failures),
        "halt_status": model_to_dict(snapshot.halt_status) if snapshot.halt_status else None,
        "gap_basis": gap_basis,
        "as_of": snapshot.timestamp,
        "as_of_et": format_et(snapshot.timestamp),
        "session_mode": session_mode_for(snapshot.timestamp),
        "data_caveat": data_caveat_for(
            snapshot.timestamp,
            gap_basis=gap_basis,
            confidence=snapshot.confidence,
        ),
        "latest_price": price,
        "previous_close": snapshot.previous_close,
        "gap_pct": compute_gap_pct(snapshot.previous_close, price),
        "gap_dollar": compute_gap_dollar(snapshot.previous_close, price),
        "volume": snapshot.volume,
        "rel_volume": compute_rel_volume(snapshot.volume, snapshot.average_volume),
        "rel_volume_basis": rel_volume_basis_for(snapshot.volume, snapshot.average_volume),
        "market_cap": snapshot.market_cap,
        "sources": list(snapshot.sources),
    }


def _daily_context(
    series: IntradayBarSeries | None,
    bars: list[IntradayBar],
) -> dict[str, Any]:
    close = bars[-1].close if bars else None
    sma_20 = _sma(bars, 20)
    ema_9 = _ema_last(bars, 9)
    ema_20 = _ema_last(bars, 20)
    trend = _trend(close, sma_20, ema_9, ema_20)
    return_5d = _return_pct(bars, 5)
    return_20d = _return_pct(bars, 20)
    recent_range_pct = _recent_range_pct(bars, 10)
    distance_from_20d_high_pct = _distance_from_high_pct(bars, 20)
    prior = bars[-1] if bars else None
    return {
        "bar_count": len(bars),
        "source": series.source if series else None,
        "fetched_at": series.fetched_at if series else None,
        "latest_completed_bar": _bar_dict(prior) if prior else None,
        "prior_day_levels": (
            {"open": prior.open, "high": prior.high, "low": prior.low, "close": prior.close}
            if prior
            else {"open": None, "high": None, "low": None, "close": None}
        ),
        "sma_20": sma_20,
        "ema_9": ema_9,
        "ema_20": ema_20,
        "trend": trend,
        "return_5d_pct": return_5d,
        "return_20d_pct": return_20d,
        "recent_range_pct": recent_range_pct,
        "distance_from_20d_high_pct": distance_from_20d_high_pct,
        "structure": _structure(
            trend=trend,
            return_5d=return_5d,
            recent_range_pct=recent_range_pct,
            distance_from_20d_high_pct=distance_from_20d_high_pct,
        ),
    }


def _relative_strength(
    daily_context: dict[str, Any],
    benchmarks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    ticker_return = daily_context.get("return_20d_pct")
    qqq_return = (benchmarks.get("QQQ") or {}).get("return_20d_pct")
    spy_return = (benchmarks.get("SPY") or {}).get("return_20d_pct")
    vs_qqq = _spread(ticker_return, qqq_return)
    vs_spy = _spread(ticker_return, spy_return)
    classification = "unknown"
    if vs_qqq is not None and vs_spy is not None:
        if vs_qqq >= 2 and vs_spy >= 2:
            classification = "strong"
        elif vs_qqq <= -2 and vs_spy <= -2:
            classification = "weak"
        else:
            classification = "in_line"
    return {
        "lookback_days": 20,
        "return_20d_pct": ticker_return,
        "vs_QQQ": vs_qqq,
        "vs_SPY": vs_spy,
        "classification": classification,
        "benchmarks": benchmarks,
    }


def _missing_fields(
    *,
    completed_bars: list[IntradayBar],
    data_quality: dict[str, Any],
) -> list[str]:
    missing = []
    if not completed_bars:
        missing.append("daily_bars")
    if data_quality.get("latest_price") is None:
        missing.append("latest_price")
    if data_quality.get("previous_close") is None:
        missing.append("previous_close")
    return missing


def _conditions(
    *,
    data_quality: dict[str, Any],
    daily_context: dict[str, Any],
    relative_strength: dict[str, Any],
    missing_fields: list[str],
) -> dict[str, dict[str, Any]]:
    halt_status = (data_quality.get("halt_status") or {}).get("status")
    trend = daily_context.get("trend")
    rs_classification = relative_strength.get("classification")
    structure = daily_context.get("structure")
    mean_reversion_watch = _is_swing_mean_reversion_watch(
        data_quality=data_quality,
        daily_context=daily_context,
        relative_strength=relative_strength,
    )
    return {
        "data_quality": _condition(
            "BLOCKED"
            if halt_status == "HALTED" or "daily_bars" in missing_fields
            else ("PASS" if data_quality.get("confidence") == "OK" else "WARNING"),
            "halt_status=HALTED."
            if halt_status == "HALTED"
            else f"confidence={data_quality.get('confidence')}, daily_bars={daily_context.get('bar_count')}.",
        ),
        "daily_trend": _condition(
            "PASS" if trend in {"uptrend", "downtrend"} else "WAITING",
            f"daily trend is {trend}.",
        ),
        "relative_strength": _condition(
            "PASS"
            if rs_classification == "strong"
            else ("FAIL" if rs_classification == "weak" else "WAITING"),
            f"20-day relative strength is {rs_classification}.",
        ),
        "daily_structure": _condition(
            "PASS"
            if structure == "constructive_near_highs"
            else ("FAIL" if structure == "broken_down" else "WAITING"),
            f"daily structure is {structure}.",
        ),
        "swing_mean_reversion": _condition(
            "PASS" if mean_reversion_watch else "WAITING",
            _mean_reversion_detail(data_quality, daily_context, mean_reversion_watch),
        ),
    }


def _is_swing_mean_reversion_watch(
    *,
    data_quality: dict[str, Any],
    daily_context: dict[str, Any],
    relative_strength: dict[str, Any],
) -> bool:
    gap_pct = data_quality.get("gap_pct")
    latest_price = data_quality.get("latest_price")
    levels = daily_context.get("prior_day_levels") or {}
    prior_low = levels.get("low")
    trend = daily_context.get("trend")
    rs_classification = relative_strength.get("classification")
    distance_from_high = daily_context.get("distance_from_20d_high_pct")

    if not isinstance(gap_pct, int | float) or float(gap_pct) > -5:
        return False
    if trend == "downtrend" and rs_classification == "weak":
        return False
    if not isinstance(daily_context.get("bar_count"), int) or daily_context["bar_count"] <= 0:
        return False
    if isinstance(latest_price, int | float) and isinstance(prior_low, int | float):
        if float(latest_price) <= float(prior_low):
            return True
    return isinstance(distance_from_high, int | float) and float(distance_from_high) <= -10


def _mean_reversion_detail(
    data_quality: dict[str, Any],
    daily_context: dict[str, Any],
    is_watch: bool,
) -> str:
    levels = daily_context.get("prior_day_levels") or {}
    low = levels.get("low")
    gap_pct = data_quality.get("gap_pct")
    if is_watch and low is not None:
        return f"Large pullback ({gap_pct}%) is near/below prior-day low {low}; reclaim required."
    if is_watch:
        return f"Large pullback ({gap_pct}%) has mean-reversion context; reclaim required."
    return "No large pullback/reclaim context for Lance swing mean reversion."


def _state(
    *,
    data_quality: dict[str, Any],
    daily_context: dict[str, Any],
    relative_strength: dict[str, Any],
    missing_fields: list[str],
    conditions: dict[str, dict[str, Any]],
) -> str:
    if conditions["data_quality"]["status"] == "BLOCKED":
        return "blocked_data_quality"
    trend = daily_context.get("trend")
    structure = daily_context.get("structure")
    rs_classification = relative_strength.get("classification")
    if trend == "downtrend" and rs_classification == "weak":
        return "invalidated"
    if _is_swing_mean_reversion_watch(
        data_quality=data_quality,
        daily_context=daily_context,
        relative_strength=relative_strength,
    ):
        return "mean_reversion_watch"
    if trend == "uptrend" and rs_classification == "strong":
        return "active_watch"
    if structure == "constructive_near_highs":
        return "confirmation_needed"
    if not missing_fields and trend in {"uptrend", "downtrend", "mixed"}:
        return "watching"
    return "not_in_play"


def _playbook(
    state: str,
    daily_context: dict[str, Any],
    relative_strength: dict[str, Any],
) -> str:
    if state == "mean_reversion_watch":
        return "swing_mean_reversion_reclaim"
    if state == "active_watch" and relative_strength.get("classification") == "strong":
        return "relative_strength_continuation"
    if state == "confirmation_needed" and daily_context.get("structure") == "constructive_near_highs":
        return "range_expansion_watch"
    if state == "invalidated":
        return "no_valid_swing_setup"
    return "daily_context_watch"


def _score(
    state: str,
    daily_context: dict[str, Any],
    relative_strength: dict[str, Any],
) -> float:
    score = {
        "active_watch": 80.0,
        "mean_reversion_watch": 55.0,
        "confirmation_needed": 60.0,
        "watching": 35.0,
        "not_in_play": 0.0,
        "invalidated": -40.0,
        "blocked_data_quality": -100.0,
    }.get(state, 0.0)
    if relative_strength.get("classification") == "strong":
        score += 10
    if daily_context.get("structure") == "constructive_near_highs":
        score += 5
    return score


def _quality_grade(state: str) -> str:
    return {
        "active_watch": "ACTIVE_DAILY_WATCH",
        "mean_reversion_watch": "REVERSION_WATCH",
        "confirmation_needed": "WATCH",
        "watching": "CONTEXT",
        "not_in_play": "C_CONTEXT",
        "invalidated": "REJECT",
        "blocked_data_quality": "REJECT",
    }.get(state, "CONTEXT")


def _bias(state: str) -> str:
    if state in {"active_watch", "mean_reversion_watch", "confirmation_needed"}:
        return "long_bias"
    return "neutral"


def _bias_reason(state: str) -> str:
    return {
        "active_watch": "relative strength continuation is a long-bias swing watch.",
        "mean_reversion_watch": "Mean-reversion reclaim is a long-bias watch only after reclaim/stabilization.",
        "confirmation_needed": "Constructive daily structure is long-bias only after confirmation.",
        "invalidated": "No valid Lance swing setup; neutral until structure repairs.",
        "blocked_data_quality": "Data quality blocks directional bias.",
    }.get(state, "No clean Lance swing bias is present.")


def _state_reason(state: str) -> str:
    return {
        "active_watch": "Daily trend and relative strength are aligned.",
        "mean_reversion_watch": (
            "Large daily pullback has Lance mean-reversion context, but still needs reclaim."
        ),
        "confirmation_needed": "Daily structure is constructive but still needs confirmation.",
        "watching": "Daily context exists, but the swing playbook is not clean yet.",
        "not_in_play": "No clean Lance daily/swing setup is present.",
        "invalidated": "Daily trend and relative strength are both failing.",
        "blocked_data_quality": "Daily bars or halt/data quality block evaluation.",
    }.get(state, "Lance swing state is unknown.")


def _waiting_for(
    state: str,
    daily_context: dict[str, Any],
    relative_strength: dict[str, Any],
) -> list[str]:
    levels = daily_context.get("prior_day_levels") or {}
    if state == "blocked_data_quality":
        return ["Daily bars and data quality must be available before swing judgment."]
    if state == "active_watch":
        return [
            "daily close confirmation above prior-day high or recent range high",
            f"relative strength stays {relative_strength.get('classification')} versus QQQ/SPY",
        ]
    if state == "mean_reversion_watch":
        low = levels.get("low")
        reclaim = "prior-day low reclaim"
        if low is not None:
            reclaim = f"prior-day low reclaim above {low}"
        return [
            f"{reclaim} before upgrading the swing mean-reversion watch",
            "stabilization/base instead of continued liquidation",
            "intraday confirmation before treating it as actionable",
        ]
    if state == "confirmation_needed":
        return ["daily range expansion with volume participation before upgrading the watch"]
    if state == "invalidated":
        return ["fresh base or reclaim before Lance carries this forward"]
    if state == "watching":
        return ["cleaner daily structure, relative strength, or catalyst before upgrading"]
    high = levels.get("high")
    return [f"daily structure must form; prior-day high reference is {high}"] if high else []


def _invalidates_if(state: str, daily_context: dict[str, Any]) -> list[str]:
    levels = daily_context.get("prior_day_levels") or {}
    low = levels.get("low")
    if state == "active_watch":
        base = "daily close loses the referenced support level"
        if low is not None:
            base = f"daily close loses prior-day low reference {low}"
        return [base, "relative strength turns weak versus QQQ/SPY"]
    if state == "mean_reversion_watch":
        if low is not None:
            return [
                f"daily close remains below prior-day low reference {low}",
                "relative strength turns weak versus QQQ/SPY",
            ]
        return ["pullback continues without reclaim or stabilization"]
    if state == "confirmation_needed":
        return ["range contracts without follow-through", "relative strength turns weak"]
    if state == "invalidated":
        return ["already invalidated until the daily structure repairs"]
    if state == "blocked_data_quality":
        return ["data quality remains blocked"]
    return ["setup remains unclear or fails to build daily structure"]


def _manual_review_questions(state: str) -> list[str]:
    if state == "active_watch":
        return [
            "Is the move supported by a real theme, catalyst, or market-relative strength?",
            "Is the daily idea still valid if the market opens weak?",
        ]
    if state == "mean_reversion_watch":
        return [
            "Is the pullback exhaustion or still active liquidation?",
            "Did price reclaim a real daily level, or only bounce below resistance?",
        ]
    if state == "invalidated":
        return ["Did the failed structure come from broad-market weakness or ticker-specific selling?"]
    return ["Is this ticker part of a current theme, or is the move isolated noise?"]


def _next_step(state: str) -> str:
    return {
        "active_watch": "Carry as a Lance daily/swing watch and require intraday confirmation.",
        "mean_reversion_watch": (
            "Track as a Lance swing mean-reversion watch; require reclaim plus intraday confirmation."
        ),
        "confirmation_needed": "Keep on watch, but do not upgrade without daily confirmation.",
        "watching": "Keep as context only until a cleaner daily playbook appears.",
        "not_in_play": "No Lance swing plan until structure improves.",
        "invalidated": "Remove from active swing watch until structure repairs.",
        "blocked_data_quality": "Fix the data path before evaluating this ticker.",
    }.get(state, "Review manually.")


def _group_plans(plans: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {
        "active_watch": [],
        "mean_reversion_watch": [],
        "confirmation_needed": [],
        "watching": [],
        "not_in_play": [],
        "invalidated": [],
        "blocked": [],
    }
    for plan in plans:
        state = plan.get("state")
        key = "blocked" if state == "blocked_data_quality" else str(state)
        groups.setdefault(key, []).append(_plan_summary(plan))
    return groups


def _plan_summary(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": plan["ticker"],
        "state": plan["state"],
        "lance_quality_grade": plan["lance_quality_grade"],
        "playbook": plan["playbook"],
        "bias": plan["bias"],
        "bias_reason": plan["bias_reason"],
        "score": plan["score"],
        "state_reason": plan["state_reason"],
        "waiting_for": plan["waiting_for"],
        "invalidates_if": plan["invalidates_if"],
        "data_quality": plan["data_quality"],
    }


def _bar_dict(bar: IntradayBar) -> dict[str, Any]:
    return {
        "timestamp": bar.timestamp,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "timeframe": bar.timeframe,
    }


def _condition(status: str, detail: str) -> dict[str, Any]:
    return {"status": status, "detail": detail}


def _sma(bars: list[IntradayBar], period: int) -> float | None:
    if len(bars) < period:
        return None
    return round(sum(bar.close for bar in bars[-period:]) / period, 4)


def _ema_last(bars: list[IntradayBar], period: int) -> float | None:
    if len(bars) < period:
        return None
    closes = [bar.close for bar in bars]
    initial = sum(closes[:period]) / period
    ema = initial
    multiplier = 2 / (period + 1)
    for close in closes[period:]:
        ema = (close - ema) * multiplier + ema
    return round(ema, 4)


def _return_pct(bars: list[IntradayBar], days: int) -> float | None:
    if len(bars) < 2:
        return None
    current = bars[-1].close
    start_index = max(0, len(bars) - 1 - days)
    start = bars[start_index].close
    if start == 0:
        return None
    return round((current - start) / start * 100, 2)


def _recent_range_pct(bars: list[IntradayBar], days: int) -> float | None:
    if len(bars) < days:
        return None
    recent = bars[-days:]
    low = min(bar.low for bar in recent)
    high = max(bar.high for bar in recent)
    if low == 0:
        return None
    return round((high - low) / low * 100, 2)


def _distance_from_high_pct(bars: list[IntradayBar], days: int) -> float | None:
    if len(bars) < days:
        return None
    high = max(bar.high for bar in bars[-days:])
    close = bars[-1].close
    if high == 0:
        return None
    return round((close - high) / high * 100, 2)


def _trend(
    close: float | None,
    sma_20: float | None,
    ema_9: float | None,
    ema_20: float | None,
) -> str:
    if close is None or sma_20 is None or ema_9 is None or ema_20 is None:
        return "unknown"
    if close > sma_20 and ema_9 > ema_20:
        return "uptrend"
    if close < sma_20 and ema_9 < ema_20:
        return "downtrend"
    return "mixed"


def _structure(
    *,
    trend: str,
    return_5d: float | None,
    recent_range_pct: float | None,
    distance_from_20d_high_pct: float | None,
) -> str:
    if trend == "downtrend":
        return "broken_down"
    if return_5d is not None and abs(return_5d) >= 20:
        return "extended"
    if (
        trend == "uptrend"
        and recent_range_pct is not None
        and recent_range_pct <= 12
        and distance_from_20d_high_pct is not None
        and distance_from_20d_high_pct >= -5
    ):
        return "constructive_near_highs"
    if trend == "uptrend":
        return "uptrend_needs_base"
    return "mixed_range"


def _spread(value: Any, benchmark: Any) -> float | None:
    if isinstance(value, int | float) and isinstance(benchmark, int | float):
        return round(float(value) - float(benchmark), 2)
    return None
