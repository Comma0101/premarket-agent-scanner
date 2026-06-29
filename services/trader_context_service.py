from __future__ import annotations

from typing import Any

from app.models import (
    CatalystEvent,
    CombinedSnapshot,
    FilingEvent,
    FormerRunnerEvent,
    IntradayBar,
    SmallCapCandidate,
    SmallCapEvidence,
    utc_now_iso,
)
from services.scanner_service import (
    compute_gap_dollar,
    compute_gap_pct,
    compute_rel_volume,
    gap_basis_for,
)
from services.snapshot_service import SnapshotService


DEFAULT_EVIDENCE_FIELDS = [
    "float",
    "catalyst",
    "filings",
    "former_runner",
    "short_interest",
]


class TraderContextService:
    def __init__(
        self,
        *,
        snapshot_service: Any | None = None,
        evidence_service: Any | None = None,
        bar_provider: Any | None = None,
    ) -> None:
        self.snapshot_service = snapshot_service
        self.evidence_service = evidence_service
        self.bar_provider = bar_provider

    def build_context(
        self,
        ticker: str,
        trader_profile: str = "default",
        *,
        include_intraday: bool = False,
        include_daily: bool = False,
        refresh_catalysts: bool = False,
    ) -> dict[str, Any]:
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("ticker is required.")

        snapshot_service = self.snapshot_service or SnapshotService.with_configured_providers()
        snapshot = snapshot_service.build_snapshot(normalized)
        snapshot_card = _snapshot_to_dict(snapshot)
        evidence_candidate = _candidate_from_snapshot(snapshot, snapshot_card)
        evidence_service = self.evidence_service or _default_evidence_service(
            refresh_catalysts=refresh_catalysts
        )
        enriched = evidence_service.enrich_candidates([evidence_candidate])[0]
        evidence = _small_cap_evidence_to_dict(enriched.evidence)

        technicals = {"intraday": None, "daily": None}
        missing_fields = list(enriched.missing_fields)

        if include_intraday:
            intraday = self._build_intraday_packet(normalized)
            technicals["intraday"] = intraday
            if intraday is None:
                _append_unique(missing_fields, "intraday_bars")
            else:
                for field in intraday.get("missing_fields") or []:
                    _append_unique(missing_fields, field)

        if include_daily:
            daily = self._build_daily_packet(normalized)
            technicals["daily"] = daily
            if daily is None:
                _append_unique(missing_fields, "daily_bars")
            else:
                for field in daily.get("missing_fields") or []:
                    _append_unique(missing_fields, field)

        return {
            "ticker": normalized,
            "trader_profile": trader_profile,
            "generated_at": utc_now_iso(),
            "snapshot": snapshot_card,
            "evidence": evidence,
            "technicals": technicals,
            "missing_fields": _dedupe(missing_fields),
            "sources": _context_sources(snapshot_card, evidence, technicals),
            "notes": _context_notes(refresh_catalysts),
        }

    def _build_intraday_packet(self, ticker: str) -> dict[str, Any] | None:
        if self.bar_provider is None:
            return None
        try:
            series = self.bar_provider.get_bars(ticker, timeframe="2Min", limit=120)
            from services.intraday_analysis_service import IntradayAnalysisService
            from services.intraday_technicals_service import IntradayTechnicalsService

            analysis = IntradayAnalysisService(self.bar_provider)
            technicals = IntradayTechnicalsService()
            ema_9 = technicals.compute_ema(series, 9)
            ema_20 = technicals.compute_ema(series, 20)
            return {
                "source": series.source,
                "fetched_at": series.fetched_at,
                "timeframe": series.timeframe,
                "bar_count": len(series.bars),
                "latest_bar": (
                    _intraday_bar_to_dict(series.bars[-1]) if series.bars else None
                ),
                "vwap": analysis.compute_vwap(series),
                "ema_9": _last_value(ema_9),
                "ema_20": _last_value(ema_20),
                "confidence": "OK" if series.bars else "LOW_CONFIDENCE",
                "missing_fields": [] if series.bars else ["intraday_bars"],
            }
        except Exception as exc:
            return {
                "confidence": "ERROR",
                "error": str(exc),
                "missing_fields": ["intraday_bars"],
            }

    def _build_daily_packet(self, ticker: str) -> dict[str, Any] | None:
        if self.bar_provider is None:
            return None
        try:
            series = self.bar_provider.get_bars(ticker, timeframe="1Day", limit=120)
            from services.support_resistance_service import SupportResistanceService

            pivots = SupportResistanceService().detect_daily_pivots(series)
            return {
                "source": series.source,
                "fetched_at": series.fetched_at,
                "timeframe": series.timeframe,
                "bar_count": len(series.bars),
                "latest_bar": (
                    _intraday_bar_to_dict(series.bars[-1]) if series.bars else None
                ),
                "pivots": [
                    {
                        "price": pivot.price,
                        "pivot_type": pivot.pivot_type,
                        "timestamp": pivot.timestamp,
                    }
                    for pivot in pivots
                ],
                "confidence": "OK" if series.bars else "LOW_CONFIDENCE",
                "missing_fields": [] if series.bars else ["daily_bars"],
            }
        except Exception as exc:
            return {
                "confidence": "ERROR",
                "error": str(exc),
                "missing_fields": ["daily_bars"],
            }


def _default_evidence_service(*, refresh_catalysts: bool):
    from services.small_cap_evidence_service import SmallCapEvidenceService

    if not refresh_catalysts:
        return SmallCapEvidenceService()

    from providers.news_provider import RSSNewsProvider

    return SmallCapEvidenceService(news_provider=RSSNewsProvider())


def _snapshot_to_dict(snapshot: CombinedSnapshot) -> dict[str, Any]:
    price = (
        snapshot.premarket_price
        if snapshot.premarket_price is not None
        else snapshot.latest_price
    )
    return {
        "ticker": snapshot.ticker,
        "previous_close": snapshot.previous_close,
        "premarket_price": snapshot.premarket_price,
        "latest_price": snapshot.latest_price,
        "gap_pct": compute_gap_pct(snapshot.previous_close, price),
        "gap_dollar": compute_gap_dollar(snapshot.previous_close, price),
        "gap_basis": gap_basis_for(snapshot),
        "market_cap": snapshot.market_cap,
        "volume": snapshot.volume,
        "rel_volume": compute_rel_volume(snapshot.volume, snapshot.average_volume),
        "confidence": snapshot.confidence,
        "sources": list(snapshot.sources),
        "timestamp": snapshot.timestamp,
        "notes": list(snapshot.notes),
    }


def _candidate_from_snapshot(
    snapshot: CombinedSnapshot,
    snapshot_card: dict[str, Any],
) -> SmallCapCandidate:
    return SmallCapCandidate(
        ticker=snapshot.ticker,
        name=None,
        market_cap=snapshot.market_cap,
        gap_pct=snapshot_card["gap_pct"],
        gap_dollar=snapshot_card["gap_dollar"],
        volume=snapshot.volume,
        rel_volume=snapshot_card["rel_volume"],
        confidence=snapshot.confidence,
        score=0,
        grade="REJECT",
        gap_basis=snapshot_card["gap_basis"],
        missing_fields=list(DEFAULT_EVIDENCE_FIELDS),
        sources=list(snapshot.sources),
        timestamp=snapshot.timestamp,
    )


def _small_cap_evidence_to_dict(
    evidence: SmallCapEvidence | None,
) -> dict[str, Any] | None:
    if evidence is None:
        return None
    return {
        "ticker": evidence.ticker,
        "float_shares": evidence.float_shares,
        "shares_outstanding": evidence.shares_outstanding,
        "float_source": evidence.float_source,
        "exchange": evidence.exchange,
        "is_low_float": evidence.is_low_float,
        "float_rotation": evidence.float_rotation,
        "filings": [_filing_event_to_dict(filing) for filing in evidence.filings],
        "catalysts": [
            _catalyst_event_to_dict(catalyst) for catalyst in evidence.catalysts
        ],
        "former_runner": (
            _former_runner_event_to_dict(evidence.former_runner)
            if evidence.former_runner is not None
            else None
        ),
        "missing_fields": list(evidence.missing_fields),
        "risk_notes": list(evidence.risk_notes),
        "sources": list(evidence.sources),
        "updated_at": evidence.updated_at,
    }


def _filing_event_to_dict(filing: FilingEvent) -> dict[str, Any]:
    return {
        "ticker": filing.ticker,
        "form_type": filing.form_type,
        "filed_at": filing.filed_at,
        "accession_number": filing.accession_number,
        "description": filing.description,
        "source_url": filing.source_url,
        "risk_tags": list(filing.risk_tags),
    }


def _catalyst_event_to_dict(catalyst: CatalystEvent) -> dict[str, Any]:
    return {
        "ticker": catalyst.ticker,
        "headline": catalyst.headline,
        "published_at": catalyst.published_at,
        "source": catalyst.source,
        "url": catalyst.url,
        "summary": catalyst.summary,
        "confidence": catalyst.confidence,
        "catalyst_quality": catalyst.catalyst_quality,
        "recency_minutes": catalyst.recency_minutes,
    }


def _former_runner_event_to_dict(event: FormerRunnerEvent) -> dict[str, Any]:
    return {
        "ticker": event.ticker,
        "event_date": event.event_date,
        "max_gap_pct": event.max_gap_pct,
        "max_volume": event.max_volume,
        "source_run_id": event.source_run_id,
        "notes": list(event.notes),
    }


def _intraday_bar_to_dict(bar: IntradayBar) -> dict[str, Any]:
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


def _last_value(values: list[float | None]) -> float | None:
    for value in reversed(values):
        if value is not None:
            return value
    return None


def _context_sources(
    snapshot: dict[str, Any],
    evidence: dict[str, Any] | None,
    technicals: dict[str, Any],
) -> list[str]:
    sources = list(snapshot.get("sources") or [])
    if evidence is not None:
        sources.extend(evidence.get("sources") or [])
    for packet in technicals.values():
        if isinstance(packet, dict) and packet.get("source"):
            sources.append(packet["source"])
    return _dedupe([str(source) for source in sources if source])


def _context_notes(refresh_catalysts: bool) -> list[str]:
    notes = ["Trader context is a read-only data packet, not execution advice."]
    if refresh_catalysts:
        notes.append(
            "Live RSS catalyst refresh was requested; unavailable catalysts remain unknown."
        )
    return notes


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
