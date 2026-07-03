# Steven Dux Data Gap Report

## Current Scanner Fields

- Ticker selection: universe, watchlist, explicit tickers, or all universes.
- Company/profile context: name, membership/universe label, market cap, and market-cap tier filtering.
- Price context: previous close, premarket price, latest price, open, high, low, and provider timestamp at snapshot level.
- Gap metrics: gap percent and dollar gap, computed from previous close against premarket price when present, otherwise latest price.
- Volume metrics: current volume and relative volume when average volume is available.
- Filters/tool inputs: cap tier, minimum/maximum market cap, minimum absolute gap percent, minimum volume, minimum relative volume, direction, and confident-only filtering.
- Small-cap evidence: exposes exchange, shares outstanding, float shares, float rotation, SEC filing risk, and former-runner history when available.

## Gaps For A Dux-Style Lens

| Gap | Why It Matters | Current Status | Possible Future Source |
| --- | --- | --- | --- |
| Intraday VWAP and Resistance | Bounce Short and Gap Up Short entries rely on stock behavior at key levels like VWAP or previous day's close. | unsupported: current scanner is snapshot-based and does not compute or evaluate against live VWAP or resistance levels | Polygon intraday aggregates, Alpaca market data stream, or calculated VWAP in the data layer |
| Multi-Day Parabolic Context | The First Red Day setup requires identifying stocks that have had massive, multi-day consecutive green runs prior to the current session. | partial: scanner focuses on current session gap/move; lacks multi-day consecutive trend indicators | Historical daily bars from yfinance, Alpaca, or Polygon; added multi-day trend calculation |
| Level 2 / Order Book Depth | Dux uses Level 2 and volume surges to detect large player distribution at resistance, confirming short entries. | unsupported | Broker direct feeds (e.g. Webull, Thinkorswim, TradeStation), Alpaca Level 2, or Polygon full order book |
| Short Locate / Borrow Data | Executing small-cap short strategies requires knowing if shares are available to borrow and the borrow fee rate (HTB). | unsupported | Broker-specific locate APIs, FINRA short interest, Ortex, or S3 Partners |
| Historical Pattern Statistics | Dux's edge is strictly based on tracking the win rate and profit-to-risk ratio of specific patterns over time. | unsupported: the system does not currently backtest or track the historical success rate of its own scan hits | Custom backtesting service, historical database of scan snapshots paired with end-of-day outcomes |

## Suggested Data-Layer Priority

1. Integrate real-time or calculated VWAP and previous day's close to support basic intraday confirmation.
2. Add multi-day trend metrics (e.g., number of consecutive green days, % run over 5 days) to identify First Red Day candidates.
3. Incorporate short borrow availability and fee rates to ensure candidates are actually tradeable.
4. Build historical pattern tracking to provide statistical confidence scores for setups.
