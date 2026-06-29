from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Callable

from app.models import CatalystEvent


@dataclass
class NewsFeed:
    name: str
    url: str


DEFAULT_NEWS_FEEDS = [
    NewsFeed(
        name="prnewswire",
        url="https://www.prnewswire.com/rss/news-releases-list.rss",
    ),
    NewsFeed(
        name="globenewswire",
        url=(
            "https://www.globenewswire.com/RssFeed/orgclass/1/feedTitle/"
            "GlobeNewswire%20-%20News%20about%20Public%20Companies"
        ),
    ),
    NewsFeed(
        name="businesswire",
        url="https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEFpQWQ==",
    ),
]

HARD_CATALYST_TERMS = (
    "fda",
    "clearance",
    "approval",
    "contract",
    "award",
    "earnings",
    "merger",
    "acquisition",
    "uplist",
    "patent",
    "partnership",
)
SOFT_CATALYST_TERMS = (
    "conference",
    "presentation",
    "letter to shareholders",
    "provides update",
    "webinar",
)


class RSSNewsProvider:
    source_name = "rss-news"

    def __init__(
        self,
        *,
        feeds: list[NewsFeed] | None = None,
        fetcher: Callable[[str], str] | None = None,
        timeout: int = 15,
    ) -> None:
        self.feeds = feeds if feeds is not None else list(DEFAULT_NEWS_FEEDS)
        self.fetcher = fetcher or self._fetch_url
        self.timeout = timeout

    def get_recent_news(self, ticker: str, limit: int = 10) -> list[CatalystEvent]:
        normalized = ticker.upper().strip()
        if not normalized or limit <= 0:
            return []

        events: list[CatalystEvent] = []
        for feed in self.feeds:
            for item in self._feed_items(feed.url):
                event = _event_from_item(normalized, feed.name, item)
                if event is None:
                    continue
                events.append(event)
                if len(events) >= limit:
                    return events
        return events

    def _feed_items(self, url: str) -> list[ET.Element]:
        try:
            payload = self.fetcher(url)
            root = ET.fromstring(payload)
        except Exception:
            return []
        return list(root.findall(".//item"))

    def _fetch_url(self, url: str) -> str:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "premarket-agent-scanner/0.1"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return response.read().decode("utf-8", errors="replace")


def _event_from_item(
    ticker: str,
    source: str,
    item: ET.Element,
) -> CatalystEvent | None:
    title = _text(item, "title")
    description = _text(item, "description")
    text = f"{title} {description}"
    if not title or not _mentions_ticker(text, ticker):
        return None

    return CatalystEvent(
        ticker=ticker,
        headline=title,
        published_at=_parse_pub_date(_text(item, "pubDate")),
        source=source,
        url=_text(item, "link"),
        summary=description,
        confidence="OK",
        catalyst_quality=_classify_quality(text),
    )


def _text(item: ET.Element, tag: str) -> str | None:
    value = item.findtext(tag)
    if value is None:
        return None
    clean = " ".join(value.split())
    return clean or None


def _mentions_ticker(text: str, ticker: str) -> bool:
    escaped = re.escape(ticker.upper())
    patterns = [
        rf"\${escaped}\b",
        rf"\b(?:NASDAQ|NYSE|NYSEAMERICAN|NYSE AMERICAN|AMEX|OTC)\s*:\s*{escaped}\b",
        rf"\({escaped}\)",
        rf"\b{escaped}\b",
    ]
    normalized = text.upper()
    return any(re.search(pattern, normalized) for pattern in patterns)


def _classify_quality(text: str) -> str:
    normalized = text.lower()
    if any(term in normalized for term in HARD_CATALYST_TERMS):
        return "hard"
    if any(term in normalized for term in SOFT_CATALYST_TERMS):
        return "soft"
    return "unknown"


def _parse_pub_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return None
