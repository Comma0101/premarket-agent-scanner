from __future__ import annotations

from typing import Any

from app.models import AssetProfile, FilingEvent, SmallCapCandidate, SmallCapEvidence
from services.profile_service import ProfileService


class SmallCapEvidenceService:
    def __init__(
        self,
        *,
        profile_service: Any | None = None,
        filing_provider: Any | None = None,
        news_provider: Any | None = None,
        db_path: str | None = None,
        low_float_threshold: float = 10_000_000,
    ) -> None:
        self.profile_service = (
            profile_service
            if profile_service is not None
            else ProfileService(db_path=db_path)
        )
        self.filing_provider = filing_provider
        self.news_provider = news_provider
        self.db_path = db_path
        self.low_float_threshold = low_float_threshold
        self._profile_error_by_ticker: dict[str, str] = {}
        self._filing_error_by_ticker: dict[str, str] = {}

    def enrich_candidates(self, candidates: list[SmallCapCandidate]) -> list[SmallCapCandidate]:
        for candidate in candidates:
            candidate.evidence = self._build_evidence(candidate)
        return candidates

    def _build_evidence(self, candidate: SmallCapCandidate) -> SmallCapEvidence:
        missing_fields = list(candidate.missing_fields)
        evidence = SmallCapEvidence(ticker=candidate.ticker, missing_fields=missing_fields)
        profile = self._get_profile(candidate.ticker)
        profile_error = self._profile_error_by_ticker.get(candidate.ticker.upper())
        filings = self._get_recent_filings(candidate.ticker)
        filing_error = self._filing_error_by_ticker.get(candidate.ticker.upper())

        if profile is not None:
            evidence.float_shares = profile.float_shares
            evidence.shares_outstanding = profile.shares_outstanding
            evidence.exchange = profile.exchange
            evidence.float_source = profile.source
            if profile.source:
                _append_unique(evidence.sources, profile.source)

        if filings:
            evidence.filings = filings
            evidence.missing_fields = [
                field for field in evidence.missing_fields if field != "filings"
            ]
            self._append_filing_risk_notes(evidence, filings)
        elif filing_error:
            _append_unique(
                evidence.risk_notes,
                f"filings lookup failed: {filing_error}; filing risk is unknown.",
            )

        if evidence.float_shares is None:
            if profile_error:
                _append_unique(
                    evidence.risk_notes,
                    f"profile lookup failed: {profile_error}",
                )
            _append_unique(
                evidence.risk_notes,
                "float is unknown; do not infer it from price or volume.",
            )
            return evidence

        evidence.is_low_float = evidence.float_shares <= self.low_float_threshold
        evidence.missing_fields = [
            field for field in evidence.missing_fields if field != "float"
        ]
        _append_unique(candidate.matched_signals, "float_known")
        if evidence.is_low_float:
            _append_unique(candidate.matched_signals, "low_float_context")
        return evidence

    def _append_filing_risk_notes(
        self,
        evidence: SmallCapEvidence,
        filings: list[FilingEvent],
    ) -> None:
        for filing in filings:
            if filing.source_url:
                _append_unique(evidence.sources, filing.source_url)
            for tag in filing.risk_tags:
                _append_unique(
                    evidence.risk_notes,
                    (
                        "recent SEC filing risk: "
                        f"{filing.form_type} {tag} filed {filing.filed_at}."
                    ),
                )

    def _get_profile(self, ticker: str) -> AssetProfile | None:
        normalized = ticker.upper()
        self._profile_error_by_ticker.pop(normalized, None)
        get_profile = getattr(self.profile_service, "get_profile", None)
        if not callable(get_profile):
            return None
        try:
            return get_profile(ticker)
        except Exception as exc:
            self._profile_error_by_ticker[normalized] = str(exc)
            return None

    def _get_recent_filings(self, ticker: str) -> list[FilingEvent]:
        normalized = ticker.upper()
        self._filing_error_by_ticker.pop(normalized, None)
        get_recent_filings = getattr(self.filing_provider, "get_recent_filings", None)
        if not callable(get_recent_filings):
            return []
        try:
            filings = get_recent_filings(ticker)
        except Exception as exc:
            self._filing_error_by_ticker[normalized] = str(exc)
            return []
        return filings if isinstance(filings, list) else []


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
