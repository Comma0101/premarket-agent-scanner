# Timothy Sykes Data Gap Report

## Current Scanner Fields

- Ticker selection: universe, watchlist, explicit tickers, or all universes.
- Company/profile context: name, membership/universe label, market cap, and market-cap tier filtering.
- Price context: previous close, premarket price, latest price, open, high, low, and provider timestamp at snapshot level.
- Gap metrics: gap percent and dollar gap, computed from previous close against premarket price when present, otherwise latest price.
- Volume metrics: current volume and relative volume when average volume is available.
- Filters/tool inputs: cap tier, minimum/maximum market cap, minimum absolute gap percent, minimum volume, minimum relative volume, direction, and confident-only filtering.
- Data quality/context: confidence label, notes, sources, run status, run id, scan start/completion timestamps, and result creation timestamp.
- Small-cap evidence now exposes exchange, shares outstanding, float shares, low-float classification, and float rotation (day volume divided by float) when a public profile source supplies float.

## Gaps For A Sykes-Style Lens

| Gap | Why It Matters | Current Status | Possible Future Source |
| --- | --- | --- | --- |
| Float / low-float classification and float rotation | Sykes-style setups often depend on supply constraints, squeeze potential, and whether volume is rotating the tradeable float. | partial: supported when FMP/yfinance supplies float; FMP profile float is spotty, so the data layer backfills from yfinance and derives `float_rotation = volume / float` | FMP profile, yfinance float fallback; future hardening could add Polygon, Nasdaq, SEC filings, or issuer filings |
| Catalyst/news quality | Breaking-news movers need source, freshness, headline substance, and relevance checks before a catalyst label is trusted. | unsupported | News API, Benzinga, Financial Modeling Prep news, SEC press releases, issuer investor-relations feeds, or curated RSS feeds |
| SEC filing / offering / dilution risk | Penny-stock and small-cap moves can fail or become dangerous when recent filings indicate offerings, toxic financing, reverse splits, or heavy dilution risk. | unsupported | SEC EDGAR company filings, FMP SEC filings, Nasdaq filings, or issuer investor-relations filing feeds |
| Former-runner history | Former runners require historical spike dates, prior percent moves, volume surges, and prior catalyst context, not just today's gap. | unsupported | Local historical scan archive, Polygon aggregates, yfinance history, Nasdaq historical data, or manually curated watchlists |
| Intraday pattern state | Supernova, pre-spike, fade, and liquidity-readiness labels require live or recent intraday structure beyond a single snapshot row. | partial | Polygon intraday bars, Alpaca market data, yfinance intraday bars, or stored scanner snapshots |
| OTC/listing context | OTC, Nasdaq, NYSE, NYSE American, delisting-risk, and exchange context materially affect liquidity assumptions and risk framing. | partial | FMP profile, Polygon ticker details, Nasdaq symbol directory, OTC Markets, SEC filings, or cached exchange/profile data |
| Short interest or borrow context | Crowded shorts, hard-to-borrow status, and borrow cost can affect squeeze potential and risk, but are not derivable from gap and volume alone. | unsupported | FINRA short interest, Nasdaq short interest, Ortex/S3-type data, broker borrow feeds, or Polygon/FMP where available |

## Suggested Data-Layer Priority

1. Harden float coverage with additional float/free-float sources and recent-share-issuance checks.
2. Catalyst/news and SEC filing ingestion.
3. Former-runner and intraday pattern history.
4. Short interest/borrow context.
