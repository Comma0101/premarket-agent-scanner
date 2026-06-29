from __future__ import annotations

import os
from typing import Any

from app.models import FilingEvent


DEFAULT_USER_AGENT = "premarket-agent-scanner/0.1 contact@example.com"
OFFERING_FORMS = {"S-1", "S-3", "424B", "424B3", "424B5"}
OFFERING_DESCRIPTION_TERMS = ("offering", "registration", "prospectus")
DILUTION_DESCRIPTION_TERMS = ("warrant", "convertible", "purchase agreement")


class SECProvider:
    company_tickers_url = "https://www.sec.gov/files/company_tickers.json"
    submissions_url_template = "https://data.sec.gov/submissions/CIK{cik}.json"

    def __init__(self, user_agent: str | None = None, timeout: int = 15) -> None:
        self.user_agent = (
            user_agent
            or os.getenv("SEC_USER_AGENT")
            or DEFAULT_USER_AGENT
        )
        self.timeout = timeout
        self._cik_by_ticker: dict[str, str] = {}

    def get_recent_filings(self, ticker: str, limit: int = 10) -> list[FilingEvent]:
        normalized = ticker.upper().strip()
        if not normalized or limit <= 0:
            return []

        cik = self._resolve_cik(normalized)
        if cik is None:
            return []
        payload = self._request_json(self.submissions_url_template.format(cik=cik))
        return self._parse_recent_filings(normalized, cik, payload, limit)

    def _resolve_cik(self, ticker: str) -> str | None:
        if ticker in self._cik_by_ticker:
            return self._cik_by_ticker[ticker]

        payload = self._request_json(self.company_tickers_url)
        records = payload.values() if isinstance(payload, dict) else []
        for record in records:
            if not isinstance(record, dict):
                continue
            if str(record.get("ticker", "")).upper() != ticker:
                continue
            try:
                cik = f"{int(record['cik_str']):010d}"
            except (KeyError, TypeError, ValueError):
                return None
            self._cik_by_ticker[ticker] = cik
            return cik
        return None

    def _request_json(self, url: str) -> dict[str, Any]:
        import requests

        response = requests.get(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": _host_for_url(url),
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def _parse_recent_filings(
        self,
        ticker: str,
        cik: str,
        payload: dict[str, Any],
        limit: int,
    ) -> list[FilingEvent]:
        recent = payload.get("filings", {}).get("recent", {})
        if not isinstance(recent, dict):
            return []

        forms = _list(recent.get("form"))
        filed_dates = _list(recent.get("filingDate"))
        accessions = _list(recent.get("accessionNumber"))
        descriptions = _list(recent.get("primaryDocDescription"))
        primary_documents = _list(recent.get("primaryDocument"))

        filings: list[FilingEvent] = []
        for index in range(min(limit, len(accessions))):
            accession_number = _text_at(accessions, index)
            form_type = _text_at(forms, index)
            filed_at = _text_at(filed_dates, index)
            if not accession_number or not form_type or not filed_at:
                continue

            description = _text_at(descriptions, index)
            filings.append(
                FilingEvent(
                    ticker=ticker,
                    form_type=form_type,
                    filed_at=filed_at,
                    accession_number=accession_number,
                    description=description,
                    source_url=_source_url(
                        cik,
                        accession_number,
                        _text_at(primary_documents, index),
                    ),
                    risk_tags=classify_filing_risk(form_type, description),
                )
            )
        return filings


def classify_filing_risk(form_type: str, description: str | None) -> list[str]:
    tags: list[str] = []
    normalized_form = form_type.upper().strip().removesuffix("/A")
    normalized_description = (description or "").lower()

    if normalized_form in OFFERING_FORMS or any(
        term in normalized_description for term in OFFERING_DESCRIPTION_TERMS
    ):
        _append_unique(tags, "offering")
    if any(term in normalized_description for term in DILUTION_DESCRIPTION_TERMS):
        _append_unique(tags, "dilution_context")
    if "reverse split" in normalized_description:
        _append_unique(tags, "reverse_split")
    return tags


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _host_for_url(url: str) -> str:
    if url.startswith("https://data.sec.gov/"):
        return "data.sec.gov"
    return "www.sec.gov"


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text_at(values: list[Any], index: int) -> str | None:
    if index >= len(values):
        return None
    value = values[index]
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _source_url(
    cik: str,
    accession_number: str,
    primary_document: str | None,
) -> str:
    cik_without_padding = str(int(cik))
    accession_path = accession_number.replace("-", "")
    base_url = (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik_without_padding}/{accession_path}"
    )
    if primary_document:
        return f"{base_url}/{primary_document}"
    return f"{base_url}/"


__all__ = ["FilingEvent", "SECProvider", "classify_filing_risk"]
