# Roland Wolf Data Gap Report

## Current Scanner Fields

- Ticker selection: universe, watchlist.
- Company/profile context: market cap, cap tier.
- Price context: previous close, premarket price, latest price.
- Gap metrics: gap percent and dollar gap.
- Volume metrics: current volume and relative volume.
- Filters/tool inputs: gap percent, volume, direction.
- Small-cap evidence: basic float (where available), recent SEC filing tags, cached RSS catalysts.
- Multi-day context: `DailyBarHistoryService` is available for multi-day analysis.

## Gaps For A Roland Wolf-Style Lens

| Gap | Why It Matters | Current Status | Possible Future Source |
| --- | --- | --- | --- |
| Intraday Price Action (1m/5m bars) | Gap & Crap and Panic Dip Buy are intraday setups. They require detecting a morning wash, capitulation volume spikes, and reversal patterns. | unsupported: scanner relies on snapshots. | Polygon intraday bars, Alpaca market data stream |
| VWAP (Volume Weighted Average Price) | Roland Wolf uses VWAP as a key level for reversals and determining intraday trend, preferring it over complex lagging indicators. | partial: basic VWAP is assumed, but needs robust real-time intraday calculation. | Polygon/Alpaca real-time aggregates |
| Cap Table (Warrants, Dilution, True Float) | Essential for understanding if a stock is a crowded trap or likely to fail heavily (the "crap"). He relies heavily on this for conviction. | partial: FMP/yfinance fallback float, basic SEC tags. Lacks deep warrant/dilution parsing. | SEC EDGAR deep parsing, purpose-built dilution feeds |
| Historical Support / Resistance | Dip buying requires knowing where historical buyers stepped in. | partial: `DailyBarHistoryService` exists, but needs algorithmic S/R detection. | Algorithmic pivot detection on `DailyBarHistoryService` |
| Drop Velocity / Panic Detection | A Panic Dip Buy requires a rapid, emotional sell-off, not just a slow fade. | unsupported | Real-time rate-of-change (ROC) on intraday feeds |

## Suggested Data-Layer Priority

1. Integrate real-time intraday bars (1m/5m) and VWAP to enable the detection of morning washes and panic capitulations.
2. Build algorithmic Support and Resistance (S/R) detection using the existing `DailyBarHistoryService`.
3. Harden the "cap table" data, specifically focusing on dilution risk and warrants via SEC filings.
