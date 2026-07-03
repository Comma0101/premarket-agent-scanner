# Tim Grittani Data Gap Report

This report outlines the market data required to support a Tim Grittani-style educational lens, highlighting what is missing from our current premarket scanner (which currently supports equity data, basic VWAP, premarket gap, and volume).

## 1. Multi-Day Chart Context (Historical Lookback)

**The Gap:** Grittani's core setups rely heavily on multi-day context. The "Morning Panic Dip Buy" requires a preceding multi-day run of at least 50%. The "Gap and Crap" requires an overextended multi-day chart before the gap up.
**Why It Matters:** Without a 3-to-5 day lookback on price percentage gain and volume, the scanner cannot differentiate a random gap or drop from a true setup. A drop is only a "panic" if there was a euphoric run-up prior.
**Required Fields:**
- `multi_day_run_percent` (e.g., 3-day or 5-day % change)
- `multi_day_volume_trend`
- `daily_resistance_levels` (historical support/resistance markers)

## 2. Advanced VWAP Metrics

**The Gap:** While the scanner has basic VWAP, Grittani uses VWAP relationally to determine momentum exhaustion and to set risk levels.
**Why It Matters:** The simple presence of VWAP is not enough. The scanner needs to know how far the current price is extended from VWAP to signal a potential "Gap and Crap" exhaustion, or if the price is holding above/below VWAP to confirm a trend.
**Required Fields:**
- `distance_from_vwap_percent`
- `vwap_trend` (slope of VWAP over the session)
- `price_vs_vwap_status` (above/below)

## 3. OTC Market Data Support

**The Gap:** Grittani frequently trades OTC breakouts, which require accurate data for OTC and Pink Sheet equities.
**Why It Matters:** If the current scanner only supports listed equities (NYSE/NASDAQ), it will miss a significant portion of his typical universe. Furthermore, OTC liquidity must be rigorously filtered.
**Required Fields:**
- `exchange_type` (explicit support for OTC)
- `dollar_volume` (crucial for filtering out illiquid OTC stocks; he requires $1M+ daily dollar volume)

## 4. Intraday Momentum Exhaustion / Real-Time Confirmation

**The Gap:** Grittani emphasizes not catching a falling knife and waiting for a confirmed bounce or top exhaustion before entering.
**Why It Matters:** Scanner snapshots provide static points in time, whereas his entry rules require real-time velocity changes and level 2 confirmation.
**Required Fields:**
- `intraday_velocity` (rate of price change)
- `level_2_depth` (bid/ask stacking)
- `candlestick_pattern_state` (e.g., Doji or reversal candles on the 1-minute or 5-minute chart)

## 5. Execution Risk Controls (External to Scanner)

**The Gap:** The "Golden Rule" of cutting losses quickly relies on strict adherence to a predetermined stop loss.
**Why It Matters:** A scanner can only present a setup. To fully evaluate a Grittani-style trade, the system needs to know the risk/reward ratio before entry.
**Required Fields (For Portfolio/Execution System, Not Scanner):**
- `planned_entry`
- `planned_stop`
- `risk_reward_ratio`

## Summary of Confidence Constraints

Until these data gaps are resolved, the Grittani profile must adhere to the following guardrails:
1. Cannot confidently label a "Morning Panic" without historical run-up data.
2. Cannot confirm a "Gap and Crap" short entry without momentum exhaustion signals and VWAP distance.
3. Must remain a discovery tool rather than a setup-confirmation tool.
4. Must maintain the `confidence` label based only on the available premarket gap and volume data.
