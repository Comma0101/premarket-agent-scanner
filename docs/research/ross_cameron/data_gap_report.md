# Ross Cameron Data Gap Report

## Current Scanner Fields

- Ticker selection: universe, watchlist, explicit tickers, or all universes.
- Company/profile context: name, membership/universe label, market cap, and market-cap tier filtering.
- Price context: previous close, premarket price, latest price, open, high, low, and provider timestamp at snapshot level.
- Gap metrics: gap percent and dollar gap, computed from previous close against premarket price when present, otherwise latest price.
- Volume metrics: current volume and relative volume when average volume is available.
- Small-cap evidence: includes basic low-float classification and recent SEC filing risk tags.

## Gaps For A Cameron-Style Lens

| Gap | Why It Matters | Current Status | Possible Future Source |
| --- | --- | --- | --- |
| Intraday VWAP | Cameron strictly uses VWAP to determine bullish/bearish control. Trades below VWAP are often rejected. | unsupported | Polygon intraday bars, Alpaca streaming, or local calculation on minute bars |
| Intraday EMAs (9, 20) | Used for determining short-term trend and identifying pullback entries (e.g., Bull flags). | unsupported | Polygon intraday bars or local calculation |
| Level 2 Order Book Depth | Crucial for Momentum Breakouts to read tape speed, liquidity gaps, and spot false breakouts. | unsupported | Alpaca Level 2 feed, broker depth feeds |
| Intraday Chart Patterns | Strategies rely on visually identifying Flat Top Breakouts and Opening Range Breakouts. | unsupported | Pattern recognition service over 1-min/5-min bars |
| Catalyst Verification | Gap and Go requires a strong fundamental news catalyst, not just a random price gap. | partial (RSS cache) | Broader News API, Benzinga, financial news streams |
| True Float | Core to finding supply-constrained momentum names, whereas market cap is only a proxy. | partial (yfinance/FMP) | Reliable financial data provider for exact float, SEC filings |

## Suggested Data-Layer Priority

1. Implement intraday VWAP calculation or ingestion for immediate trend filtering.
2. Integrate 1-min and 5-min EMA (9, 20) calculations.
3. Harden true float data sources.
4. Expand catalyst/news verification to ensure gaps have fundamental backing.
