from __future__ import annotations

from typing import Any

from app.models import CombinedSnapshot, IntradayBarSeries, model_to_dict
from services.scanner_service import (
    compute_gap_dollar,
    compute_gap_pct,
    compute_rel_volume,
    gap_basis_for,
    rel_volume_basis_for,
)
from services.session_time_service import data_caveat_for, format_et, session_mode_for


LANCE_RVOL_FLOOR = 3.0
LANCE_MOVE_FLOOR_PCT = 3.0
DISCLAIMER = (
    "Reference levels are not buy/sell advice. They are data-layer levels a "
    "Lance-style plan would monitor; verify before acting."
)


class LanceIntradayPlanService:
    def __init__(
        self,
        *,
        snapshot_service: Any | None = None,
        intraday_service: Any | None = None,
    ) -> None:
        self.snapshot_service = snapshot_service
        self.intraday_service = intraday_service

    def build_plan(self, ticker: str) -> dict[str, Any]:
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("ticker is required.")

        snapshot = self._snapshot_service().build_snapshot(normalized)
        series = self._fetch_intraday(normalized)
        intraday = self._intraday_service()

        vwap = intraday.compute_vwap(series) if series is not None else None
        signal = intraday.detect_entry_signal(series, vwap) if series is not None else None
        prior_high, prior_low = (
            intraday.compute_prior_bar_levels(series) if series is not None else (None, None)
        )
        pressure = self._pressure_before_last_bar(series)
        volume_2x = intraday.check_volume_2x(series) if series is not None else None
        rate_of_change = intraday.compute_rate_of_change(series) if series is not None else None
        bollinger_width = intraday.compute_bollinger_width(series) if series is not None else None
        target_20ma = intraday.compute_20_period_ma(series) if series is not None else None
        chop = intraday.detect_chop(series) if series is not None else None

        data_quality = _data_quality(snapshot)
        missing_fields = _missing_fields(
            data_quality=data_quality,
            series=series,
            vwap=vwap,
        )
        conditions = _conditions(
            data_quality=data_quality,
            series=series,
            vwap=vwap,
            pressure=pressure,
            volume_2x=volume_2x,
            signal=signal,
            chop=chop,
        )
        trigger_reference = _trigger_reference(
            signal=signal,
            pressure=pressure,
            prior_high=prior_high,
            prior_low=prior_low,
            series=series,
        )
        risk_reference = _risk_reference(
            signal=signal,
            pressure=pressure,
            prior_high=prior_high,
            prior_low=prior_low,
        )
        target_reference = (
            {"price": target_20ma, "source": "20_period_ma"} if target_20ma is not None else None
        )
        state = _state(
            conditions=conditions,
            signal=signal,
            series=series,
            chop=chop,
        )
        front_side_status = _front_side_status(state)
        waiting_for = _waiting_for(
            state=state,
            conditions=conditions,
            trigger_reference=trigger_reference,
            data_quality=data_quality,
        )
        invalidates_if = _policy_invalidates_if(
            state=state,
            data_quality=data_quality,
            risk_reference=risk_reference,
            trigger_reference=trigger_reference,
        )

        return {
            "ticker": normalized,
            "trader": "lance_breitstein",
            "setup_name": "mean_reversion_after_capitulation",
            "state": state,
            "state_reason": _state_reason(state),
            "front_side_status": front_side_status,
            "lance_quality_grade": _lance_quality_grade(
                state=state,
                conditions=conditions,
            ),
            "data_quality": data_quality,
            "conditions": conditions,
            "decision_sequence": _decision_sequence(
                state=state,
                conditions=conditions,
                front_side_status=front_side_status,
            ),
            "trigger_reference": trigger_reference,
            "risk_reference": risk_reference,
            "target_reference": target_reference,
            "intraday": {
                "bar_count": len(series.bars) if series is not None else 0,
                "source": series.source if series is not None else None,
                "fetched_at": series.fetched_at if series is not None else None,
                "latest_bar": _bar_dict(series.bars[-1]) if series and series.bars else None,
                "vwap": vwap,
                "volume_2x_confirmed": volume_2x,
                "consecutive_pressure_bars": pressure,
                "rate_of_change": rate_of_change,
                "bollinger_width": bollinger_width,
                "chop": chop,
            },
            "entry_signal": _signal_dict(signal),
            "missing_fields": missing_fields,
            "waiting_for": waiting_for,
            "invalidates_if": invalidates_if,
            "manual_review_questions": _manual_review_questions(state),
            "next_step": _next_step(state),
            "disclaimer": DISCLAIMER,
        }

    def _snapshot_service(self) -> Any:
        if self.snapshot_service is None:
            from services.snapshot_service import SnapshotService

            self.snapshot_service = SnapshotService.with_configured_providers()
        return self.snapshot_service

    def _intraday_service(self) -> Any:
        if self.intraday_service is None:
            from services.intraday_analysis_service import IntradayAnalysisService

            self.intraday_service = IntradayAnalysisService()
        return self.intraday_service

    def _fetch_intraday(self, ticker: str) -> IntradayBarSeries | None:
        try:
            return self._intraday_service().fetch_bars(ticker, limit=120)
        except Exception:
            return None

    def _pressure_before_last_bar(self, series: IntradayBarSeries | None) -> int | None:
        if series is None or len(series.bars) < 2:
            return None
        streak_series = IntradayBarSeries(
            ticker=series.ticker,
            timeframe=series.timeframe,
            bars=series.bars[:-1],
            source=series.source,
            fetched_at=series.fetched_at,
        )
        return self._intraday_service().compute_consecutive_bars(streak_series)


def _data_quality(snapshot: CombinedSnapshot) -> dict[str, Any]:
    price = snapshot.premarket_price if snapshot.premarket_price is not None else snapshot.latest_price
    gap_basis = gap_basis_for(snapshot)
    gap_pct = compute_gap_pct(snapshot.previous_close, price)
    gap_dollar = compute_gap_dollar(snapshot.previous_close, price)
    rel_volume = compute_rel_volume(snapshot.volume, snapshot.average_volume)
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
        "gap_pct": gap_pct,
        "gap_dollar": gap_dollar,
        "volume": snapshot.volume,
        "rel_volume": rel_volume,
        "rel_volume_basis": rel_volume_basis_for(snapshot.volume, snapshot.average_volume),
        "market_cap": snapshot.market_cap,
        "sources": list(snapshot.sources),
    }


def _conditions(
    *,
    data_quality: dict[str, Any],
    series: IntradayBarSeries | None,
    vwap: float | None,
    pressure: int | None,
    volume_2x: bool | None,
    signal: Any | None,
    chop: bool | None,
) -> dict[str, dict[str, Any]]:
    confidence = data_quality["confidence"]
    gap_basis = data_quality["gap_basis"]
    gap_pct = data_quality["gap_pct"]
    rel_volume = data_quality["rel_volume"]
    halt_status = (data_quality.get("halt_status") or {}).get("status")
    bar_count = len(series.bars) if series is not None else 0

    return {
        "data_quality": _condition(
            "BLOCKED"
            if halt_status == "HALTED"
            else ("PASS" if confidence == "OK" and gap_basis is not None else "BLOCKED"),
            "halt_status=HALTED."
            if halt_status == "HALTED"
            else f"gap_basis={gap_basis}, confidence={confidence}.",
        ),
        "abnormal_move": _threshold_condition(
            value=abs(gap_pct) if gap_pct is not None else None,
            floor=LANCE_MOVE_FLOOR_PCT,
            unit="%",
        ),
        "participation": _threshold_condition(
            value=rel_volume,
            floor=LANCE_RVOL_FLOOR,
            unit="x session-volume RVOL",
        ),
        "intraday_bars": _condition(
            "PASS" if bar_count >= 4 else "UNKNOWN",
            f"{bar_count} 2-minute bar(s) available.",
        ),
        "vwap": _condition(
            "PASS" if vwap is not None else "UNKNOWN",
            "VWAP available." if vwap is not None else "VWAP unavailable.",
            vwap,
        ),
        "consecutive_pressure": _condition(
            "PASS" if pressure is not None and abs(pressure) >= 3 else "WAITING",
            f"{pressure} consecutive pressure bar(s) before latest bar.",
            pressure,
        ),
        "volume_2x": _condition(
            "PASS" if volume_2x else "WAITING",
            "Latest bar volume is >= 2x prior bar." if volume_2x else "No 2x volume confirmation.",
        ),
        "prior_bar_break": _condition(
            "PASS" if signal is not None else "WAITING",
            "Prior 2-minute bar break confirmed."
            if signal is not None
            else "Waiting for prior 2-minute bar break.",
        ),
        "chop_filter": _condition(
            "FAIL" if chop else ("PASS" if chop is False else "UNKNOWN"),
            "Bollinger compression detected."
            if chop
            else ("Not in compression." if chop is False else "Compression unknown."),
        ),
    }


def _threshold_condition(*, value: float | None, floor: float, unit: str) -> dict[str, Any]:
    if value is None:
        return _condition("UNKNOWN", f"Required floor is {floor}{unit}; value unknown.")
    return _condition(
        "PASS" if value >= floor else "FAIL",
        f"{value} vs required {floor}{unit}.",
        value,
    )


def _condition(status: str, detail: str, value: Any | None = None) -> dict[str, Any]:
    output: dict[str, Any] = {"status": status, "detail": detail}
    if value is not None:
        output["value"] = value
    return output


def _state(
    *,
    conditions: dict[str, dict[str, Any]],
    signal: Any | None,
    series: IntradayBarSeries | None,
    chop: bool | None,
) -> str:
    if conditions["data_quality"]["status"] == "BLOCKED":
        return "blocked_data_quality"
    if series is None or not series.bars:
        return "waiting_for_intraday_data"
    if conditions["abnormal_move"]["status"] != "PASS" or conditions["participation"]["status"] != "PASS":
        return "not_in_play"
    if chop:
        return "invalidated"
    if signal is not None:
        return "triggered_reference"
    if conditions["consecutive_pressure"]["status"] == "PASS":
        return "waiting_for_turn"
    if conditions["volume_2x"]["status"] == "PASS":
        return "setup_forming"
    return "watching"


def _front_side_status(state: str) -> str:
    return {
        "blocked_data_quality": "blocked",
        "waiting_for_intraday_data": "unknown",
        "not_in_play": "not_in_play",
        "invalidated": "invalidated",
        "triggered_reference": "right_side_confirmed",
        "waiting_for_turn": "front_side_active",
        "setup_forming": "turn_developing",
        "watching": "no_turn_yet",
    }.get(state, "unknown")


def _state_reason(state: str) -> str:
    return {
        "blocked_data_quality": "Data quality blocks Lance evaluation.",
        "waiting_for_intraday_data": "Intraday bars are unavailable, so Lance cannot read the turn.",
        "not_in_play": "Move or RVOL is not abnormal enough for Lance.",
        "invalidated": "Chop/compression or failed structure invalidates Lance setup.",
        "triggered_reference": "Right-side prior 2-minute bar break is confirmed.",
        "waiting_for_turn": "Directional pressure exists, but Lance is still waiting for the turn.",
        "setup_forming": "Participation or volume expansion is developing, but right-side confirmation is missing.",
        "watching": "Candidate is relevant, but pressure and turn confirmation are not present.",
    }.get(state, "State is unknown.")


def _lance_quality_grade(
    *,
    state: str,
    conditions: dict[str, dict[str, Any]],
) -> str:
    if state in {"blocked_data_quality", "invalidated"}:
        return "REJECT"
    if state == "triggered_reference" and _core_conditions_pass(conditions):
        return "A_WATCH"
    if state in {"waiting_for_turn", "setup_forming"} and _core_conditions_pass(conditions):
        return "B_WATCH"
    return "C_CONTEXT"


def _core_conditions_pass(conditions: dict[str, dict[str, Any]]) -> bool:
    return (
        conditions["data_quality"]["status"] == "PASS"
        and conditions["abnormal_move"]["status"] == "PASS"
        and conditions["participation"]["status"] == "PASS"
        and conditions["chop_filter"]["status"] != "FAIL"
    )


def _decision_sequence(
    *,
    state: str,
    conditions: dict[str, dict[str, Any]],
    front_side_status: str,
) -> list[dict[str, Any]]:
    return [
        {
            "step": "data_gate",
            "status": conditions["data_quality"]["status"],
            "detail": conditions["data_quality"]["detail"],
        },
        {
            "step": "in_play_gate",
            "status": _in_play_status(conditions),
            "detail": "Requires abnormal move and RVOL participation.",
        },
        {
            "step": "structure_gate",
            "status": _structure_status(conditions),
            "detail": "Requires intraday bars, VWAP context, and no chop/compression.",
        },
        {
            "step": "right_side_gate",
            "status": _right_side_status(state),
            "detail": f"front_side_status={front_side_status}.",
        },
    ]


def _in_play_status(conditions: dict[str, dict[str, Any]]) -> str:
    if conditions["data_quality"]["status"] == "BLOCKED":
        return "BLOCKED"
    if (
        conditions["abnormal_move"]["status"] == "PASS"
        and conditions["participation"]["status"] == "PASS"
    ):
        return "PASS"
    return "WAITING"


def _structure_status(conditions: dict[str, dict[str, Any]]) -> str:
    if conditions["chop_filter"]["status"] == "FAIL":
        return "BLOCKED"
    if conditions["intraday_bars"]["status"] == "PASS" and conditions["vwap"]["status"] == "PASS":
        return "PASS"
    return "UNKNOWN"


def _right_side_status(state: str) -> str:
    if state == "triggered_reference":
        return "PASS"
    if state in {"blocked_data_quality", "invalidated"}:
        return "BLOCKED"
    return "WAITING"


def _waiting_for(
    *,
    state: str,
    conditions: dict[str, dict[str, Any]],
    trigger_reference: dict[str, Any] | None,
    data_quality: dict[str, Any],
) -> list[str]:
    if state == "triggered_reference":
        return []
    waiting = []
    halt_status = (data_quality.get("halt_status") or {}).get("status")
    if state == "blocked_data_quality":
        waiting.append("Data quality must return to OK with clear gap basis.")
        if halt_status == "HALTED":
            waiting.append("Active halt must resolve.")
    if conditions["abnormal_move"]["status"] != "PASS":
        waiting.append("Abnormal move must reach Lance's floor.")
    if conditions["participation"]["status"] != "PASS":
        waiting.append("RVOL participation is below Lance's floor.")
    if conditions["intraday_bars"]["status"] != "PASS":
        waiting.append("2-minute intraday bars must be available.")
    if conditions["vwap"]["status"] != "PASS":
        waiting.append("VWAP context must be available.")
    if conditions["chop_filter"]["status"] == "FAIL":
        waiting.append("Chop/compression must clear.")
    if state == "waiting_for_turn" and trigger_reference is not None:
        waiting.append(_waiting_for_turn_text(trigger_reference))
    elif conditions["prior_bar_break"]["status"] != "PASS":
        waiting.append("Prior 2-minute bar break must confirm right-side turn.")
    return _dedupe(waiting)


def _waiting_for_turn_text(trigger_reference: dict[str, Any]) -> str:
    source = str(trigger_reference.get("source") or "")
    if "high" in source:
        return "prior 2-minute bar high break"
    if "low" in source:
        return "prior 2-minute bar low break"
    return "prior 2-minute bar break"


def _policy_invalidates_if(
    *,
    state: str,
    data_quality: dict[str, Any],
    risk_reference: dict[str, Any] | None,
    trigger_reference: dict[str, Any] | None,
) -> list[str]:
    invalidations = [
        "data confidence degrades or provider failures appear",
        "active halt appears",
        "chop/compression develops",
    ]
    if state == "blocked_data_quality":
        invalidations.append("data quality remains blocked")
    if trigger_reference is not None:
        invalidations.append("prior 2-minute low/high reference fails")
    if risk_reference is None:
        invalidations.append("risk reference remains unknown")
    else:
        invalidations.append(f"risk reference fails ({risk_reference['source']})")
    if data_quality.get("gap_pct") is None:
        invalidations.append("gap/move context remains unknown")
    return _dedupe(invalidations)


def _manual_review_questions(state: str) -> list[str]:
    questions = [
        "Did the prior-bar reference produce follow-through, fail, chop, or reverse?",
        "Was the catalyst emotional/temporary or a fundamental repricing?",
        "Was there visible order-flow absorption/offering that the data layer cannot see?",
    ]
    if state in {"blocked_data_quality", "waiting_for_intraday_data"}:
        questions.insert(0, "Was missing or stale data resolved before making any judgment?")
    return questions


def _dedupe(values: list[str]) -> list[str]:
    output = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _trigger_reference(
    *,
    signal: Any | None,
    pressure: int | None,
    prior_high: float | None,
    prior_low: float | None,
    series: IntradayBarSeries | None,
) -> dict[str, Any] | None:
    timestamp = series.bars[-1].timestamp if series is not None and series.bars else None
    if signal is not None:
        source = (
            "prior_2min_bar_high_break"
            if signal.direction == "long"
            else "prior_2min_bar_low_break"
        )
        return {
            "direction": signal.direction,
            "price": signal.entry_price,
            "source": source,
            "timestamp": signal.timestamp,
        }
    if pressure is None or abs(pressure) < 3:
        return None
    if pressure < 0 and prior_high is not None:
        return {
            "direction": "long",
            "price": prior_high,
            "source": "waiting_for_prior_2min_bar_high_break",
            "timestamp": timestamp,
        }
    if pressure > 0 and prior_low is not None:
        return {
            "direction": "short",
            "price": prior_low,
            "source": "waiting_for_prior_2min_bar_low_break",
            "timestamp": timestamp,
        }
    return None


def _risk_reference(
    *,
    signal: Any | None,
    pressure: int | None,
    prior_high: float | None,
    prior_low: float | None,
) -> dict[str, Any] | None:
    if signal is not None:
        if signal.direction == "long":
            return {"price": signal.stop_price, "source": "prior_2min_bar_low"}
        return {"price": signal.stop_price, "source": "prior_2min_bar_high"}
    if pressure is None or abs(pressure) < 3:
        return None
    if pressure < 0 and prior_low is not None:
        return {"price": prior_low, "source": "prior_2min_bar_low_if_long_trigger"}
    if pressure > 0 and prior_high is not None:
        return {"price": prior_high, "source": "prior_2min_bar_high_if_short_trigger"}
    return None


def _missing_fields(
    *,
    data_quality: dict[str, Any],
    series: IntradayBarSeries | None,
    vwap: float | None,
) -> list[str]:
    missing = []
    if data_quality["gap_pct"] is None:
        missing.append("gap_pct")
    if data_quality["rel_volume"] is None:
        missing.append("rel_volume")
    if series is None or not series.bars:
        missing.append("intraday_bars")
    if vwap is None and series is not None and series.bars:
        missing.append("vwap")
    return missing


def _bar_dict(bar: Any) -> dict[str, Any]:
    return {
        "ticker": bar.ticker,
        "timestamp": bar.timestamp,
        "open": bar.open,
        "high": bar.high,
        "low": bar.low,
        "close": bar.close,
        "volume": bar.volume,
        "timeframe": bar.timeframe,
    }


def _signal_dict(signal: Any | None) -> dict[str, Any] | None:
    if signal is None:
        return None
    return {
        "ticker": signal.ticker,
        "direction": signal.direction,
        "entry_price": signal.entry_price,
        "stop_price": signal.stop_price,
        "target_price": signal.target_price,
        "prior_bar_high": signal.prior_bar_high,
        "prior_bar_low": signal.prior_bar_low,
        "vwap": signal.vwap,
        "vwap_filter_passed": signal.vwap_filter_passed,
        "volume_2x_confirmed": signal.volume_2x_confirmed,
        "consecutive_bars": signal.consecutive_bars,
        "rate_of_change": signal.rate_of_change,
        "bollinger_width": signal.bollinger_width,
        "timestamp": signal.timestamp,
        "confidence": signal.confidence,
        "missing_fields": list(signal.missing_fields),
    }


def _next_step(state: str) -> str:
    return {
        "blocked_data_quality": "Wait for OK confidence and a usable effective price.",
        "waiting_for_intraday_data": "Wait for 2-minute intraday bars before forming a Lance plan.",
        "not_in_play": "No Lance intraday plan until abnormal move and RVOL participation improve.",
        "invalidated": "Avoid Lance mean-reversion plan while compression/chop is active.",
        "triggered_reference": "A Lance-style reference trigger is present; verify manually before acting.",
        "waiting_for_turn": "Wait for the prior 2-minute bar break; do not fade the front side.",
        "setup_forming": "Monitor the prior 2-minute bar break reference and volume confirmation.",
        "watching": "Watching only; pressure/volume/trigger stack is not complete.",
    }[state]
