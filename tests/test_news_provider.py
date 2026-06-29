from __future__ import annotations

from providers.news_provider import NewsFeed, RSSNewsProvider


def _rss_item(
    *,
    title: str,
    description: str = "",
    link: str = "https://example.test/hot",
    pub_date: str = "Mon, 29 Jun 2026 12:00:00 GMT",
) -> str:
    return f"""<?xml version="1.0"?>
<rss>
  <channel>
    <item>
      <title>{title}</title>
      <link>{link}</link>
      <pubDate>{pub_date}</pubDate>
      <description>{description}</description>
    </item>
  </channel>
</rss>
"""


def test_news_provider_parses_matching_rss_item():
    xml = _rss_item(
        title="HOT announces FDA clearance",
        description="HOT today announced FDA clearance.",
    )
    provider = RSSNewsProvider(
        feeds=[NewsFeed(name="fake-wire", url="https://example.test/rss")],
        fetcher=lambda url: xml,
    )

    events = provider.get_recent_news("HOT")

    assert len(events) == 1
    assert events[0].ticker == "HOT"
    assert events[0].headline == "HOT announces FDA clearance"
    assert events[0].published_at == "2026-06-29T12:00:00+00:00"
    assert events[0].source == "fake-wire"
    assert events[0].url == "https://example.test/hot"
    assert events[0].summary == "HOT today announced FDA clearance."
    assert events[0].catalyst_quality == "hard"
    assert events[0].confidence == "OK"


def test_news_provider_ignores_non_matching_item():
    xml = _rss_item(
        title="COOL announces FDA clearance",
        description="COOL today announced FDA clearance.",
    )
    provider = RSSNewsProvider(
        feeds=[NewsFeed(name="fake-wire", url="https://example.test/rss")],
        fetcher=lambda url: xml,
    )

    assert provider.get_recent_news("HOT") == []


def test_news_provider_classifies_soft_catalyst():
    xml = _rss_item(
        title="HOT to present at investor conference",
        description="HOT will present at a conference.",
    )
    provider = RSSNewsProvider(
        feeds=[NewsFeed(name="fake-wire", url="https://example.test/rss")],
        fetcher=lambda url: xml,
    )

    events = provider.get_recent_news("HOT")

    assert events[0].catalyst_quality == "soft"


def test_news_provider_returns_empty_on_fetch_or_parse_error():
    bad_xml_provider = RSSNewsProvider(
        feeds=[NewsFeed(name="fake-wire", url="https://example.test/rss")],
        fetcher=lambda url: "<rss>",
    )
    raising_provider = RSSNewsProvider(
        feeds=[NewsFeed(name="fake-wire", url="https://example.test/rss")],
        fetcher=lambda url: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    assert bad_xml_provider.get_recent_news("HOT") == []
    assert raising_provider.get_recent_news("HOT") == []
