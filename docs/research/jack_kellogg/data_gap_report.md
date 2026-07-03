# Jack Kellogg Data Gap Report

## Current Scanner Fields

- Ticker selection: universe, watchlist, explicit tickers, or all universes.
- Company/profile context: name, membership/universe label, market cap, and market-cap tier filtering.
- Price context: previous close, premarket price, latest price, open, high, low, and provider timestamp at snapshot level.
- Gap metrics: gap percent and dollar gap, computed from previous close against premarket price when present, otherwise latest price.
- Volume metrics: current volume and relative volume when average volume is available.
- Filters/tool inputs: cap tier, minimum/maximum market cap, minimum absolute gap percent, minimum volume, minimum relative volume, direction, and confident-only filtering.
- Data quality/context: confidence label, notes, sources, run status, run id, scan start/completion timestamps, and result creation timestamp.
- Small-cap evidence now exposes exchange, shares outstanding, float shares, low-float classification, float rotation (day volume divided by float), recent SEC filing risk tags, cached RSS catalyst/news events, and local former-runner history when those sources resolve.
- Basic VWAP (assumed present).

## Gaps For A Kellogg-Style Lens

| Gap | Why It Matters | Current Status | Possible Future Source |
| --- | --- | --- | --- |
| Distance from VWAP | Kellogg specifically avoids going long if a stock is extended above VWAP, and avoids going short if it's extended below VWAP, to prevent chasing. | unsupported: current scanner only has the price and basic VWAP, but does not compute the percentage distance between the two as a filterable metric | Calculated metric in the data layer (e.g., `(latest_price - vwap) / vwap`) |
| True Float & OTC Classification | Kellogg's foundational setups often revolve around low-float OTC breakouts. Using market cap as a proxy is insufficient for this specific style. | partial: float is partially supported via yfinance/FMP; OTC market classification is not a primary filter | FMP profile, OTC Markets data feed, SEC filings |
| Linear Regression & Support/Resistance | Kellogg relies on Linear Regression channels and basic Support/Resistance lines to define risk and entry levels. | unsupported: requires historical and intraday pattern analysis, which a snapshot scanner lacks | Intraday bars (Polygon, Alpaca) combined with technical analysis libraries (e.g., TA-Lib, pandas-ta) |
| Sector Strength ("Hot Sectors") | High momentum plays are often driven by sector-wide strength or themes, which he looks for to confirm demand. | unsupported: tickers are not grouped or scored by real-time sector momentum | FMP sector performance, ETF proxies, or real-time sector aggregation |
| Real-time Surging Volume | While RVOL exists, confirming a breakout requires detecting sudden volume surges on an intraday timeframe (e.g., 1-minute or 5-minute bars). | partial: daily volume and RVOL are present, but intraday volume acceleration is not | Intraday volume profiles via Polygon or Alpaca |

## Suggested Data-Layer Priority

1. Add `distance_from_vwap` as a computable, filterable metric to prevent chasing setups.
2. Integrate OTC market data classification and ensure true float is accurately reported.
3. Build intraday data capabilities to support linear regression channels and support/resistance plotting.
4. Implement sector and industry tagging to identify "hot sectors".
