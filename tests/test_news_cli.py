from __future__ import annotations

from typer.testing import CliRunner

from app.db import get_cached_news
from app.models import CatalystEvent


def test_refresh_news_cli_fetches_and_caches_events(tmp_path, monkeypatch):
    import cli.refresh_news as module

    class FakeNewsProvider:
        def get_recent_news(self, ticker: str):
            return [
                CatalystEvent(
                    ticker=ticker,
                    headline=f"{ticker} announces FDA clearance",
                    published_at="2026-06-29T12:00:00Z",
                    source="fake-wire",
                    url=f"https://example.test/{ticker.lower()}",
                    confidence="OK",
                    catalyst_quality="hard",
                )
            ]

    db_path = tmp_path / "market.sqlite"
    monkeypatch.setattr(module, "RSSNewsProvider", FakeNewsProvider)

    result = CliRunner().invoke(
        module.app,
        ["--tickers", "hot,COOL", "--db-path", str(db_path)],
    )

    assert result.exit_code == 0
    assert "HOT: 1 catalyst(s)" in result.output
    assert "COOL: 1 catalyst(s)" in result.output
    assert "2 catalyst(s) cached." in result.output
    hot_news = get_cached_news(db_path, "HOT")
    cool_news = get_cached_news(db_path, "COOL")
    assert hot_news[0].headline == "HOT announces FDA clearance"
    assert hot_news[0].catalyst_quality == "hard"
    assert cool_news[0].source == "fake-wire"


def test_refresh_news_cli_reports_provider_errors_cleanly(tmp_path, monkeypatch):
    import cli.refresh_news as module

    class RaisingNewsProvider:
        def get_recent_news(self, ticker: str):
            raise RuntimeError("rss offline")

    db_path = tmp_path / "market.sqlite"
    monkeypatch.setattr(module, "RSSNewsProvider", RaisingNewsProvider)

    result = CliRunner().invoke(
        module.app,
        ["--tickers", "HOT", "--db-path", str(db_path)],
    )

    assert result.exit_code == 0
    assert "HOT: error: rss offline" in result.output
    assert "0 catalyst(s) cached." in result.output
    assert get_cached_news(db_path, "HOT") == []


def test_refresh_news_cli_requires_tickers():
    import cli.refresh_news as module

    result = CliRunner().invoke(module.app, ["--tickers", " , "])

    assert result.exit_code != 0
    assert "Provide at least one ticker." in result.output
