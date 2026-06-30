from __future__ import annotations

from datetime import datetime, timezone

from providers.nasdaq_halt_provider import NasdaqHaltProvider


RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Trade Halt - HALT</title>
      <description><![CDATA[
        Issue Symbol: HALT<br/>
        Issue Name: Halted Biotech Inc<br/>
        Reason Code: T1<br/>
        Halt Date: 06/30/2026<br/>
        Halt Time: 09:35:00
      ]]></description>
      <pubDate>Tue, 30 Jun 2026 13:35:00 GMT</pubDate>
    </item>
    <item>
      <title>Trade Halt - BACK</title>
      <description><![CDATA[
        Issue Symbol: BACK<br/>
        Reason Code: T5<br/>
        Halt Date: 06/30/2026<br/>
        Halt Time: 09:40:00<br/>
        Resume Date: 06/30/2026<br/>
        Resume Time: 09:55:00
      ]]></description>
      <pubDate>Tue, 30 Jun 2026 13:40:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


NAMESPACED_RSS_FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:ndaq="http://www.nasdaqtrader.com/">
  <channel>
    <item>
      <title>HCWB</title>
      <pubDate>Mon, 29 Jun 2026 04:00:00 GMT</pubDate>
      <ndaq:HaltDate>06/29/2026</ndaq:HaltDate>
      <ndaq:HaltTime>19:50:00.000</ndaq:HaltTime>
      <ndaq:IssueSymbol>HCWB</ndaq:IssueSymbol>
      <ndaq:IssueName>HCW Biologics Inc. Cm</ndaq:IssueName>
      <ndaq:Market>NASDAQ</ndaq:Market>
      <ndaq:ReasonCode>T1</ndaq:ReasonCode>
      <ndaq:ResumptionDate />
      <ndaq:ResumptionQuoteTime />
      <ndaq:ResumptionTradeTime />
    </item>
  </channel>
</rss>
"""


def test_nasdaq_halt_provider_parses_active_and_resumed_items() -> None:
    provider = NasdaqHaltProvider(
        fetcher=lambda: RSS_FIXTURE,
        now_provider=lambda: datetime(2026, 6, 30, 14, 0, tzinfo=timezone.utc),
    )

    active = provider.get_halt_status("HALT")
    resumed = provider.get_halt_status("BACK")
    unknown = provider.get_halt_status("MISS")

    assert active.ticker == "HALT"
    assert active.status == "HALTED_REGULATORY"
    assert active.is_active is True
    assert active.reason_code == "T1"
    assert active.halt_time == "2026-06-30T13:35:00+00:00"
    assert resumed.status == "RESUMED"
    assert resumed.is_active is False
    assert unknown.status == "UNKNOWN"
    assert unknown.is_active is False


def test_nasdaq_halt_provider_caches_feed_for_sixty_seconds() -> None:
    calls = {"count": 0}

    def fetch():
        calls["count"] += 1
        return RSS_FIXTURE

    provider = NasdaqHaltProvider(fetcher=fetch)

    provider.get_halt_status("HALT")
    provider.get_halt_status("BACK")

    assert calls["count"] == 1


def test_nasdaq_halt_provider_parses_current_namespaced_rss_shape() -> None:
    provider = NasdaqHaltProvider(
        fetcher=lambda: NAMESPACED_RSS_FIXTURE,
        now_provider=lambda: datetime(2026, 6, 30, 2, 0, tzinfo=timezone.utc),
    )

    status = provider.get_halt_status("HCWB")

    assert status.status == "HALTED_REGULATORY"
    assert status.is_active is True
    assert status.reason_code == "T1"
    assert status.halt_time == "2026-06-29T23:50:00+00:00"
