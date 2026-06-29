from app.db import (
    get_cached_filings,
    get_cached_news,
    get_runner_history,
    insert_filing_event,
    insert_news_event,
    insert_runner_event,
)
from app.models import CatalystEvent, FilingEvent, FormerRunnerEvent, SmallCapEvidence


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
