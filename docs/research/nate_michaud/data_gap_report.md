# Nate Michaud Data Gap Report

## Current Scanner Fields

- Ticker selection: universe, watchlist, explicit tickers, or all universes.
- Company/profile context: name, membership/universe label, market cap, and market-cap tier filtering.
- Price context: previous close, premarket price, latest price, open, high, low, and provider timestamp at snapshot level. We also have equity data and a DailyBarHistoryService for multi-day context.
- Gap metrics: gap percent and dollar gap, computed from previous close against premarket price when present, otherwise latest price.
- Volume metrics: current volume and relative volume when average volume is available.
- Indicators: Basic VWAP.
- Filters/tool inputs: cap tier, minimum/maximum market cap, minimum absolute gap percent, minimum volume, minimum relative volume, direction, and confident-only filtering.
- Data quality/context: confidence label, notes, sources, run status, run id, scan start/completion timestamps, and result creation timestamp.

## Gaps For A Michaud-Style Lens

| Gap | Why It Matters | Current Status | Possible Future Source |
| --- | --- | --- | --- |
| Intraday Pattern State (ABCD) | The ABCD pattern requires recognizing a sequence of intraday peaks and troughs (A, B, C) to anticipate the breakout (D). Snapshots cannot capture this sequencing. | unsupported | Intraday tick/minute bar analysis via Polygon, Alpaca, or yfinance to map structural highs and lows. |
| Short Interest / Borrow Context | Michaud frequently targets heavily shorted stocks for squeeze plays. Knowing short float and borrow availability is crucial to his momentum strategies. | unsupported | FINRA short interest, Ortex, S3 Partners, or broker borrow availability feeds. |
| VWAP Distance / Consolidation | While basic VWAP is available, the strategy relies on identifying consolidation *at* VWAP ("VWAP Boulevard") to find support bases or predict short squeezes. | partial (have VWAP, lack consolidation math) | Derived metrics measuring price distance to VWAP and time spent near VWAP. |
| Red-to-Green Velocity | Detecting a stock *crossing* the previous close is easy, but finding stocks "gearing up" to cross requires intraday velocity and accumulation metrics. | partial (can do basic cross) | Intraday trend/momentum indicators analyzing the approach to the previous close level. |

## Suggested Data-Layer Priority

1. Build intraday pattern state recognition (peak/trough detection for ABCD patterns).
2. Integrate short interest and borrow data to support squeeze identification.
3. Add derived metrics for VWAP interaction (distance to VWAP, consolidation time).
