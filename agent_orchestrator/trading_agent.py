from __future__ import annotations

from typing import Any, Callable

from agent_tools.definitions import dispatch
from agent_orchestrator.models import (
    AgentRunPacket,
    AgentToolCall,
    AgentWatchCandidate,
    WatchBucket,
)


Dispatcher = Callable[..., dict[str, Any]]

AGENT_NAME = "sykes_style_small_cap_agent"
STRATEGY = "sykes_small_cap_watchlist"

GUARDRAILS = [
    "Use only scanner/data-layer values; never invent prices, float, market cap, gap, volume, filings, catalysts, short interest, or borrow data.",
    "Do not output buy/sell/short recommendations or position sizing.",
    "Treat missing evidence as unknown and call it out directly.",
    "Do not claim to be Timothy Sykes; this is a Sykes-style small-cap watchlist agent built from public criteria.",
]


class TradingAgentOrchestrator:
    def __init__(self, dispatcher: Dispatcher | None = None) -> None:
        self.dispatcher = dispatcher or dispatch

    def run_sykes_small_cap_watchlist(
        self,
        *,
        preset_name: str = "sykes_small_cap_v0",
        universe: str | None = None,
        watchlist: str | None = None,
        tickers: str | None = None,
        market: str | None = None,
        market_limit: int | None = None,
        all_universes: bool = False,
        user_query: str | None = None,
        db_path: str | None = None,
    ) -> AgentRunPacket:
        selection = _selection_input(
            universe=universe,
            watchlist=watchlist,
            tickers=tickers,
            market=market,
            all_universes=all_universes,
        )
        if not selection:
            return _error_packet(
                "Pick a selection: tickers, universe, watchlist, market, or all_universes."
            )

        tool_input = {"preset_name": preset_name, **selection}
        if market_limit is not None:
            tool_input["market_limit"] = market_limit
        result = self.dispatcher(
            "scan_small_caps",
            tool_input,
            user_query=user_query,
            db_path=db_path,
        )
        if "error" in result:
            message = str(result["error"])
            return _error_packet(
                message,
                tool_call=AgentToolCall(
                    name="scan_small_caps",
                    tool_input=tool_input,
                    result_summary=message,
                ),
            )

        candidates = list(result.get("candidates") or [])
        candidate_count = result.get("candidate_count", len(candidates))
        packet_watchlist = _empty_watchlist()
        warnings: list[str] = []

        for raw_candidate in candidates:
            bucket = _bucket_for_grade(str(raw_candidate.get("grade", "")))
            if bucket is None:
                continue

            candidate = _agent_candidate(raw_candidate, bucket)
            packet_watchlist[bucket].append(candidate)
            if candidate.missing_fields:
                warnings.append(
                    f"{candidate.ticker} missing evidence: {', '.join(candidate.missing_fields)}"
                )

        if not candidates:
            warnings.append("No candidates matched the small-cap scanner criteria.")

        return AgentRunPacket(
            agent_name=AGENT_NAME,
            strategy=STRATEGY,
            status="OK",
            tool_calls=[
                AgentToolCall(
                    name="scan_small_caps",
                    tool_input=tool_input,
                    result_summary=f"{candidate_count} candidate(s)",
                )
            ],
            watchlist=packet_watchlist,
            guardrails=list(GUARDRAILS),
            warnings=_dedupe(warnings),
            notes=list(result.get("notes") or []),
            handoff_prompt=_handoff_prompt(),
        )


def _selection_input(
    *,
    universe: str | None,
    watchlist: str | None,
    tickers: str | None,
    market: str | None,
    all_universes: bool,
) -> dict[str, Any]:
    selection: dict[str, Any] = {}
    if universe:
        selection["universe"] = universe
    if watchlist:
        selection["watchlist"] = watchlist
    if tickers:
        selection["tickers"] = tickers
    if market:
        selection["market"] = market
    if all_universes:
        selection["all_universes"] = True
    return selection


def _empty_watchlist() -> dict[WatchBucket, list[AgentWatchCandidate]]:
    return {
        "primary_watch": [],
        "secondary_watch": [],
        "context_watch": [],
    }


def _bucket_for_grade(grade: str) -> WatchBucket | None:
    if grade == "A_WATCH":
        return "primary_watch"
    if grade == "B_WATCH":
        return "secondary_watch"
    if grade == "C_WATCH":
        return "context_watch"
    return None


def _agent_candidate(raw: dict[str, Any], bucket: WatchBucket) -> AgentWatchCandidate:
    evidence = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else None
    missing_fields = _string_list(
        evidence.get("missing_fields") if evidence is not None else raw.get("missing_fields")
    )
    gap_basis = _optional_string(raw.get("gap_basis"))
    return AgentWatchCandidate(
        ticker=str(raw.get("ticker") or "").upper(),
        name=raw.get("name"),
        bucket=bucket,
        grade=str(raw.get("grade") or ""),
        score=_optional_int(raw.get("score")),
        gap_pct=_optional_float(raw.get("gap_pct")),
        gap_dollar=_optional_float(raw.get("gap_dollar")),
        volume=_optional_float(raw.get("volume")),
        rel_volume=_optional_float(raw.get("rel_volume")),
        market_cap=_optional_float(raw.get("market_cap")),
        confidence=raw.get("confidence"),
        matched_signals=_string_list(raw.get("matched_signals")),
        missing_fields=missing_fields,
        risk_notes=_string_list(raw.get("risk_notes")),
        sources=_string_list(raw.get("sources")),
        evidence_summary=_evidence_summary(evidence, gap_basis=gap_basis),
        gap_basis=gap_basis,
    )


def _evidence_summary(
    evidence: dict[str, Any] | None,
    *,
    gap_basis: str | None = None,
) -> str:
    parts: list[str] = []
    if gap_basis:
        parts.append(f"gap_basis={gap_basis}")

    if evidence is None:
        parts.append("evidence=unknown")
        return "; ".join(parts)

    float_shares = _optional_float(evidence.get("float_shares"))
    if float_shares is not None:
        label = _format_share_count(float_shares)
        if evidence.get("is_low_float") is True:
            label = f"{label} low"
        rotation = _optional_float(evidence.get("float_rotation"))
        if rotation is not None:
            label = f"{label} rot={rotation:.1f}x"
        parts.append(f"float={label}")

    catalysts = evidence.get("catalysts")
    if isinstance(catalysts, list) and catalysts:
        first = catalysts[0] if isinstance(catalysts[0], dict) else {}
        headline = str(first.get("headline") or "").strip()
        source = str(first.get("source") or "").strip()
        catalyst_context = _catalyst_context(first)
        if headline and source:
            parts.append(f"catalyst={catalyst_context}{source}: {headline}")
        elif headline:
            parts.append(f"catalyst={catalyst_context}{headline}")

    risk_tags = _filing_risk_tags(evidence)
    if risk_tags:
        parts.append(f"filing_risk={', '.join(risk_tags)}")

    if evidence.get("former_runner"):
        parts.append("former_runner=yes")

    return "; ".join(parts) if parts else "evidence=unknown"


def _catalyst_context(catalyst: dict[str, Any]) -> str:
    parts: list[str] = []
    quality = str(catalyst.get("catalyst_quality") or "").strip()
    recency_minutes = _optional_float(catalyst.get("recency_minutes"))
    if quality:
        parts.append(quality)
    if recency_minutes is not None:
        parts.append(_format_recency_minutes(recency_minutes))
    return f"{' '.join(parts)} " if parts else ""


def _format_recency_minutes(value: float) -> str:
    return f"{int(round(value))}m"


def _filing_risk_tags(evidence: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    filings = evidence.get("filings")
    if not isinstance(filings, list):
        return tags

    for filing in filings:
        if not isinstance(filing, dict):
            continue
        for tag in _string_list(filing.get("risk_tags")):
            if tag not in tags:
                tags.append(tag)
    return tags


def _format_share_count(value: float) -> str:
    if abs(value) >= 1e9:
        return f"{value / 1e9:.1f}B"
    if abs(value) >= 1e6:
        return f"{value / 1e6:.1f}M"
    if abs(value) >= 1e3:
        return f"{value / 1e3:.1f}K"
    return f"{value:,.0f}"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _error_packet(
    message: str,
    *,
    tool_call: AgentToolCall | None = None,
) -> AgentRunPacket:
    return AgentRunPacket(
        agent_name=AGENT_NAME,
        strategy=STRATEGY,
        status="ERROR",
        tool_calls=[tool_call] if tool_call is not None else [],
        watchlist=_empty_watchlist(),
        guardrails=list(GUARDRAILS),
        warnings=[message],
        notes=[],
        handoff_prompt=_handoff_prompt(),
    )


def _handoff_prompt() -> str:
    return (
        "Use only the scanner packet and cited evidence. Present candidates as "
        "watchlist context, call out missing data, and do not provide execution "
        "instructions, price targets, or position sizing."
    )
