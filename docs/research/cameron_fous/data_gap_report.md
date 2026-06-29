# Cameron Fous Data Gap Report

## Current Scanner Fields

- Ticker selection: universe, watchlist, explicit tickers, or all universes.
- Company/profile context: name, membership/universe label, market cap, and market-cap tier filtering.
- Price context: previous close, premarket price, latest price, open, high, low, and provider timestamp at snapshot level.
- Gap metrics: gap percent and dollar gap, computed from previous close against premarket price when present, otherwise latest price.
- Volume metrics: current volume and relative volume when average volume is available.
- Filters/tool inputs: cap tier, minimum/maximum market cap, minimum absolute gap percent, minimum volume, minimum relative volume, direction, and confident-only filtering.
- Data quality/context: confidence label, notes, sources, run status, run id, scan start/completion timestamps, and result creation timestamp.

## Gaps For A Fous4-Style Lens

| Gap | Why It Matters | Current Status | Possible Future Source |
| --- | --- | --- | --- |
| Technical Indicators (13 EMA, RSI, MACD) | Fous setups heavily rely on the 13-day EMA for trend confirmation and other momentum indicators like RSI/MACD. | unsupported: current scanner only has raw price/gap data without historical indicator calculations | FMP technical indicators endpoint, Polygon aggregate bars, or yfinance historical data combined with local TA-Lib calculations |
| Multi-Day Pattern Classification | The core "Fous4" setups (Force, Revival, Survival, Gold) require analysis of chart structure over multiple days/weeks, not just a single premarket gap. | unsupported: scanner evaluates single-session snapshots | Polygon intraday/daily bars, stored scanner snapshots, or a dedicated pattern recognition microservice |
| Short Interest and Borrow Availability | The Fous4x2 system focuses on shorting breakdowns, requiring knowledge of whether a stock is hard-to-borrow and what the borrow fees are. | unsupported | Broker API feeds (Alpaca/Interactive Brokers), FINRA short interest, or Ortex data |
| Pre-Trade Risk/Reward Modeling | The strategy requires strict adherence to a 2:1 profit-to-loss ratio, which means entry, stop-loss, and target levels must be identified prior to the trade. | unsupported: scanner outputs candidates, not trade plans | Agent-driven trade planning tool based on support/resistance levels derived from historical bars |

## Suggested Data-Layer Priority

1. Integrate basic technical indicators, specifically the 13-day EMA, to filter candidates based on trend alignment.
2. Build or integrate a historical bar service (daily/intraday) to support multi-day pattern recognition for the specific Fous4 patterns.
3. Incorporate short borrow availability data for Fous4x2 breakdown setups.
4. Develop automated support/resistance calculation to model hypothetical 2:1 risk/reward setups.
