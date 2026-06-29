from __future__ import annotations

from app.models import AssetProfile, SmallCapCandidate
from providers.sec_provider import SECProvider
from services.small_cap_evidence_service import SmallCapEvidenceService


class FakeProfileService:
    def get_profile(self, ticker: str):
        return AssetProfile(
            ticker=ticker.upper(),
            exchange="NASDAQ",
            shares_outstanding=20_000_000,
            float_shares=8_000_000,
            source="fake-profile",
        )


def _candidate(ticker: str = "HOT") -> SmallCapCandidate:
    return SmallCapCandidate(
        ticker=ticker,
        name=None,
        market_cap=100_000_000,
        gap_pct=12.0,
        gap_dollar=1.2,
        volume=2_000_000,
        rel_volume=5.0,
        confidence="OK",
        score=90,
        grade="A_WATCH",
        missing_fields=["float", "filings"],
    )


def test_sec_provider_caches_company_ticker_map(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "premarket-agent-scanner dev@example.com")
    calls: list[str] = []

    def fake_json_fetcher(url: str):
        calls.append(url)
        if url == SECProvider.company_tickers_url:
            return {
                "0": {"ticker": "AAA", "cik_str": 1},
                "1": {"ticker": "BBB", "cik_str": 2},
            }
        return {
            "filings": {
                "recent": {
                    "form": [],
                    "filingDate": [],
                    "accessionNumber": [],
                    "primaryDocDescription": [],
                    "primaryDocument": [],
                }
            }
        }

    provider = SECProvider(json_fetcher=fake_json_fetcher)

    assert provider.get_recent_filings("AAA") == []
    assert provider.get_recent_filings("BBB") == []
    assert calls.count(SECProvider.company_tickers_url) == 1


def test_sec_placeholder_user_agent_surfaces_as_unknown_filings(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)

    def forbidden_json_fetcher(url: str):
        raise AssertionError(f"unexpected SEC request: {url}")

    provider = SECProvider(json_fetcher=forbidden_json_fetcher)
    service = SmallCapEvidenceService(
        profile_service=FakeProfileService(),
        filing_provider=provider,
    )

    enriched = service.enrich_candidates([_candidate()])[0]

    assert enriched.evidence is not None
    assert enriched.evidence.filings == []
    assert "filings" in enriched.evidence.missing_fields
    assert any("SEC_USER_AGENT" in note for note in enriched.evidence.risk_notes)
