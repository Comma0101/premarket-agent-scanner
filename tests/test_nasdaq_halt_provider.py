from __future__ import annotations

from providers.nasdaq_halt_provider import NasdaqHaltProvider


HALT_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss>
  <channel>
    <item>
      <title>Trade Halt - ABCD</title>
      <description>
        Symbol: ABCD
        Name: ABCD Corp
        Market: NASDAQ
        Reason Code: LUDP
        Halt Date: 07/01/2026
        Halt Time: 09:35:12
      </description>
      <pubDate>Wed, 01 Jul 2026 13:35:12 GMT</pubDate>
    </item>
    <item>
      <title>Trade Halt - WXYZ</title>
      <description>
        Symbol: WXYZ
        Reason Code: T1
        Halt Date: 07/01/2026
        Halt Time: 10:01:00
        Resumption Date: 07/01/2026
        Resumption Quote Time: 10:11:00
        Resumption Trade Time: 10:16:00
      </description>
      <pubDate>Wed, 01 Jul 2026 14:16:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

NAMESPACED_HALT_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:ndaq="http://www.nasdaqtrader.com/">
  <channel>
    <item>
      <title>MWHS</title>
      <ndaq:HaltDate>07/02/2026</ndaq:HaltDate>
      <ndaq:HaltTime>15:39:42.716</ndaq:HaltTime>
      <ndaq:IssueSymbol>MWHS</ndaq:IssueSymbol>
      <ndaq:IssueName>Skylar Electricity Futures ETF</ndaq:IssueName>
      <ndaq:Market>NYSE Arca</ndaq:Market>
      <ndaq:ReasonCode>M</ndaq:ReasonCode>
      <ndaq:ResumptionDate>07/02/2026</ndaq:ResumptionDate>
      <ndaq:ResumptionQuoteTime>15:44:42</ndaq:ResumptionQuoteTime>
      <ndaq:ResumptionTradeTime>15:44:42</ndaq:ResumptionTradeTime>
      <description><![CDATA[<table><tr><td>MWHS</td></tr></table>]]></description>
    </item>
    <item>
      <title>MAGH</title>
      <ndaq:HaltDate>12/04/2025</ndaq:HaltDate>
      <ndaq:HaltTime>19:50:00</ndaq:HaltTime>
      <ndaq:IssueSymbol>MAGH</ndaq:IssueSymbol>
      <ndaq:IssueName>Magnitude International Ltd OS</ndaq:IssueName>
      <ndaq:Market>NASDAQ</ndaq:Market>
      <ndaq:ReasonCode>T12</ndaq:ReasonCode>
      <ndaq:ResumptionDate />
      <ndaq:ResumptionQuoteTime />
      <ndaq:ResumptionTradeTime />
    </item>
  </channel>
</rss>
"""


def test_nasdaq_halt_provider_parses_active_halt_from_rss():
    provider = NasdaqHaltProvider(fetcher=lambda: HALT_RSS)

    status = provider.get_halt_status("abcd")

    assert status.ticker == "ABCD"
    assert status.status == "HALTED"
    assert status.reason_code == "LUDP"
    assert status.halt_time == "07/01/2026 09:35:12"
    assert status.resume_time is None
    assert status.source == "nasdaq_trader_halts"


def test_nasdaq_halt_provider_parses_resumed_halt_from_rss():
    provider = NasdaqHaltProvider(fetcher=lambda: HALT_RSS)

    status = provider.get_halt_status("WXYZ")

    assert status.status == "RESUMED"
    assert status.reason_code == "T1"
    assert status.halt_time == "07/01/2026 10:01:00"
    assert status.resume_time == "07/01/2026 10:16:00"


def test_nasdaq_halt_provider_returns_not_halted_when_symbol_absent():
    provider = NasdaqHaltProvider(fetcher=lambda: HALT_RSS)

    status = provider.get_halt_status("MISS")

    assert status.status == "NOT_HALTED"
    assert status.reason_code is None
    assert status.halt_time is None
    assert status.resume_time is None


def test_nasdaq_halt_provider_parses_live_namespaced_rss_shape():
    provider = NasdaqHaltProvider(fetcher=lambda: NAMESPACED_HALT_RSS)

    status = provider.get_halt_status("MWHS")

    assert status.status == "RESUMED"
    assert status.reason_code == "M"
    assert status.halt_time == "07/02/2026 15:39:42.716"
    assert status.resume_time == "07/02/2026 15:44:42"
    assert status.raw["issuesymbol"] == "MWHS"


def test_nasdaq_halt_provider_returns_unknown_for_non_rss_html():
    provider = NasdaqHaltProvider(fetcher=lambda: "<html><body>Object moved</body></html>")

    status = provider.get_halt_status("MWHS")

    assert status.status == "UNKNOWN"
    assert status.error == "NASDAQ halt feed did not return RSS XML."
    assert "NASDAQ halt feed parse failed" in status.notes


def test_nasdaq_halt_provider_reports_unknown_on_fetch_failure():
    provider = NasdaqHaltProvider(fetcher=lambda: (_ for _ in ()).throw(RuntimeError("DNS")))

    status = provider.get_halt_status("ABCD")

    assert status.status == "UNKNOWN"
    assert status.error == "DNS"
    assert "NASDAQ halt feed unavailable" in status.notes
