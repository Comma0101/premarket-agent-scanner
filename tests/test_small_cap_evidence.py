from app.db import (
    get_cached_filings,
    get_cached_news,
    get_runner_history,
    insert_filing_event,
    insert_news_event,
    insert_runner_event,
)
from app.models import (
    AssetProfile,
    CatalystEvent,
    FormerRunnerEvent,
    SmallCapCandidate,
    SmallCapEvidence,
)
from providers.sec_provider import FilingEvent, classify_filing_risk
from services.small_cap_evidence_service import SmallCapEvidenceService


def test_evidence_models_default_to_unknown_fields():
    evidence = SmallCapEvidence(ticker="HOT", missing_fields=["float", "catalyst"])

    assert evidence.ticker == "HOT"
    assert evidence.float_shares is None
    assert evidence.filings == []
    assert evidence.catalysts == []
    assert evidence.missing_fields == ["float", "catalyst"]


def test_evidence_cache_round_trips_filings_news_and_runner_history(tmp_path):
    db_path = tmp_path / "evidence.sqlite"

    insert_filing_event(
        db_path,
        FilingEvent(
            ticker="HOT",
            form_type="S-1",
            filed_at="2026-06-28",
            accession_number="0000000000-26-000001",
            description="Registration statement",
            source_url="https://www.sec.gov/Archives/example",
            risk_tags=["offering"],
        ),
    )
    insert_news_event(
        db_path,
        CatalystEvent(
            ticker="HOT",
            headline="HOT announces contract",
            published_at="2026-06-28T12:00:00Z",
            source="fake-news",
            url="https://example.test/hot",
            summary="Contract headline",
            confidence="OK",
        ),
    )
    insert_runner_event(
        db_path,
        FormerRunnerEvent(
            ticker="HOT",
            event_date="2026-06-01",
            max_gap_pct=180.0,
            max_volume=12_000_000,
            source_run_id="run123",
            notes=["prior large gap"],
        ),
    )

    filings = get_cached_filings(db_path, "HOT")
    news = get_cached_news(db_path, "HOT")
    runners = get_runner_history(db_path, "HOT")

    assert filings[0].form_type == "S-1"
    assert filings[0].risk_tags == ["offering"]
    assert news[0].headline == "HOT announces contract"
    assert runners[0].max_gap_pct == 180.0


def test_news_cache_updates_existing_row_by_url(tmp_path):
    db_path = tmp_path / "evidence.sqlite"

    insert_news_event(
        db_path,
        CatalystEvent(
            ticker="HOT",
            headline="HOT announces contract",
            published_at="2026-06-28T12:00:00Z",
            source="fake-news",
            url="https://example.test/hot-contract",
            summary="Original headline",
            confidence="LOW_CONFIDENCE",
        ),
    )
    insert_news_event(
        db_path,
        CatalystEvent(
            ticker="HOT",
            headline="HOT announces larger contract",
            published_at="2026-06-28T12:05:00Z",
            source="fake-news",
            url="https://example.test/hot-contract",
            summary="Updated headline",
            confidence="OK",
        ),
    )

    news = get_cached_news(db_path, "HOT")

    assert len(news) == 1
    assert news[0].headline == "HOT announces larger contract"
    assert news[0].summary == "Updated headline"
    assert news[0].confidence == "OK"


def test_news_cache_keeps_distinct_urls_with_same_headline_and_published_at(tmp_path):
    db_path = tmp_path / "evidence.sqlite"

    insert_news_event(
        db_path,
        CatalystEvent(
            ticker="HOT",
            headline="HOT announces contract",
            published_at="2026-06-28T12:00:00Z",
            source="fake-news",
            url="https://example.test/hot-contract-a",
            summary="First URL",
            confidence="OK",
        ),
    )
    insert_news_event(
        db_path,
        CatalystEvent(
            ticker="HOT",
            headline="HOT announces contract",
            published_at="2026-06-28T12:00:00Z",
            source="fake-news",
            url="https://example.test/hot-contract-b",
            summary="Second URL",
            confidence="OK",
        ),
    )

    news = get_cached_news(db_path, "HOT")

    assert len(news) == 2
    assert {event.url for event in news} == {
        "https://example.test/hot-contract-a",
        "https://example.test/hot-contract-b",
    }


def test_news_cache_updates_existing_row_without_url_by_headline_and_published_at(tmp_path):
    db_path = tmp_path / "evidence.sqlite"

    insert_news_event(
        db_path,
        CatalystEvent(
            ticker="HOT",
            headline="HOT announces contract",
            published_at="2026-06-28T12:00:00Z",
            source="first-wire",
            url=None,
            summary="Original summary",
            confidence="LOW_CONFIDENCE",
        ),
    )
    insert_news_event(
        db_path,
        CatalystEvent(
            ticker="HOT",
            headline="HOT announces contract",
            published_at="2026-06-28T12:00:00Z",
            source="second-wire",
            url=None,
            summary="Updated summary",
            confidence="OK",
        ),
    )

    news = get_cached_news(db_path, "HOT")

    assert len(news) == 1
    assert news[0].source == "second-wire"
    assert news[0].summary == "Updated summary"
    assert news[0].confidence == "OK"


class FakeProfileService:
    def get_profile(self, ticker: str):
        if ticker == "HOT":
            return AssetProfile(
                ticker="HOT",
                exchange="NASDAQ",
                shares_outstanding=20_000_000,
                float_shares=8_000_000,
                source="fake-profile",
            )
        return None


class RaisingProfileService:
    def get_profile(self, ticker: str):
        raise RuntimeError("profile offline")


class FakeFilingProvider:
    def get_recent_filings(self, ticker: str):
        return [
            FilingEvent(
                ticker=ticker,
                form_type="S-1",
                filed_at="2026-06-27",
                accession_number="0000000000-26-000002",
                description="Securities registration statement",
                source_url="https://www.sec.gov/Archives/example",
                risk_tags=["offering"],
            )
        ]


class RaisingFilingProvider:
    def get_recent_filings(self, ticker: str):
        raise RuntimeError("sec offline")


def _candidate(ticker="HOT"):
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
        missing_fields=["float", "catalyst", "filings", "former_runner"],
    )


def test_evidence_service_populates_float_from_profile():
    service = SmallCapEvidenceService(profile_service=FakeProfileService())

    enriched = service.enrich_candidates([_candidate()])[0]

    assert enriched.evidence is not None
    assert enriched.evidence.float_shares == 8_000_000
    assert enriched.evidence.is_low_float is True
    assert "float" not in enriched.evidence.missing_fields
    assert "float_known" in enriched.matched_signals
    assert "fake-profile" in enriched.evidence.sources


def test_evidence_service_computes_float_rotation():
    class RotatingProfileService:
        def get_profile(self, ticker: str):
            return AssetProfile(
                ticker=ticker,
                exchange="NASDAQ",
                shares_outstanding=20_000_000,
                float_shares=5_000_000,
                source="fake-profile",
            )

    service = SmallCapEvidenceService(profile_service=RotatingProfileService())
    candidate = _candidate()
    candidate.volume = 10_000_000
    enriched = service.enrich_candidates([candidate])[0]

    assert enriched.evidence is not None
    assert enriched.evidence.float_shares == 5_000_000
    assert enriched.evidence.float_rotation == 2.0
    assert enriched.evidence.is_low_float is True


def test_evidence_service_keeps_float_unknown_when_profile_missing():
    service = SmallCapEvidenceService(profile_service=FakeProfileService())

    enriched = service.enrich_candidates([_candidate("MISS")])[0]

    assert enriched.evidence is not None
    assert enriched.evidence.float_shares is None
    assert "float" in enriched.evidence.missing_fields
    assert any("float is unknown" in note for note in enriched.evidence.risk_notes)


def test_evidence_service_keeps_float_unknown_when_profile_lookup_fails():
    service = SmallCapEvidenceService(profile_service=RaisingProfileService())

    enriched = service.enrich_candidates([_candidate()])[0]

    assert enriched.evidence is not None
    assert enriched.evidence.float_shares is None
    assert "float" in enriched.evidence.missing_fields
    assert any(
        "profile lookup" in note or "profile offline" in note
        for note in enriched.evidence.risk_notes
    )


def test_classify_filing_risk_tags_offering_forms():
    assert classify_filing_risk("S-1", "Registration statement") == ["offering"]
    assert classify_filing_risk("8-K", "Entry into a Material Definitive Agreement") == []


def test_evidence_service_attaches_recent_filings_and_removes_missing_field():
    service = SmallCapEvidenceService(
        profile_service=FakeProfileService(),
        filing_provider=FakeFilingProvider(),
    )

    enriched = service.enrich_candidates([_candidate()])[0]

    assert enriched.evidence is not None
    assert enriched.evidence.filings[0].form_type == "S-1"
    assert "filings" not in enriched.evidence.missing_fields
    assert any("offering" in note.lower() for note in enriched.evidence.risk_notes)


def test_evidence_service_uses_cached_filings_news_and_runner_history(tmp_path):
    db_path = tmp_path / "evidence.sqlite"
    insert_filing_event(
        db_path,
        FilingEvent(
            ticker="HOT",
            form_type="S-3",
            filed_at="2026-06-26",
            accession_number="0000000000-26-000003",
            description="Shelf registration statement",
            source_url="https://www.sec.gov/Archives/example-s3",
            risk_tags=["offering"],
        ),
    )
    insert_news_event(
        db_path,
        CatalystEvent(
            ticker="HOT",
            headline="HOT wins supply deal",
            published_at="2026-06-28T11:45:00Z",
            source="fake-wire",
            url="https://example.test/news/hot",
            summary="Supply deal",
            confidence="OK",
        ),
    )
    insert_runner_event(
        db_path,
        FormerRunnerEvent(
            ticker="HOT",
            event_date="2026-06-01",
            max_gap_pct=120.0,
            max_volume=9_000_000,
            source_run_id="prior-run",
            notes=["prior runner"],
        ),
    )
    service = SmallCapEvidenceService(
        profile_service=FakeProfileService(),
        filing_provider=None,
        db_path=str(db_path),
    )

    enriched = service.enrich_candidates([_candidate()])[0]

    assert enriched.evidence is not None
    assert enriched.evidence.filings[0].form_type == "S-3"
    assert enriched.evidence.catalysts[0].headline == "HOT wins supply deal"
    assert enriched.evidence.former_runner is not None
    assert "filings" not in enriched.evidence.missing_fields
    assert "catalyst" not in enriched.evidence.missing_fields
    assert "former_runner" not in enriched.evidence.missing_fields


def test_evidence_service_surfaces_filing_provider_failure_as_unknown():
    service = SmallCapEvidenceService(
        profile_service=FakeProfileService(),
        filing_provider=RaisingFilingProvider(),
    )

    enriched = service.enrich_candidates([_candidate()])[0]

    assert enriched.evidence is not None
    assert enriched.evidence.filings == []
    assert "filings" in enriched.evidence.missing_fields
    assert any("sec offline" in note for note in enriched.evidence.risk_notes)


def test_evidence_service_syncs_candidate_missing_fields_after_enrichment():
    service = SmallCapEvidenceService(
        profile_service=FakeProfileService(),
        filing_provider=FakeFilingProvider(),
    )

    enriched = service.enrich_candidates([_candidate()])[0]

    assert enriched.evidence is not None
    assert enriched.missing_fields == enriched.evidence.missing_fields
    assert "float" not in enriched.missing_fields
    assert "filings" not in enriched.missing_fields
