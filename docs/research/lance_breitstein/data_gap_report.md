# Lance Breitstein Data Gap Report

## Current Repo Fit

The project has strong equity snapshot, premarket, small-cap, catalyst, filing,
and universe-scanning foundations. These partially overlap with Breitstein's
method. The critical difference from the Brando Le and Sykes profiles: **the
rules exist and are concrete; the data is what's missing.** This makes the gaps
actionable.

## Required Data Before Production Scanner

| Need | Why It Matters | Current Status | Candidate Sources | Blocks Profile? |
| --- | --- | --- | --- | --- |
| 2-minute bar data | Required for ALL entry triggers (prior bar high/low break), stops (prior bar low/high), volume comparison (2x rule), consecutive bar count, rate of change, 20-period MA target, trailing stops | **implemented when Alpaca bars are configured; provider quality still must be validated live** | Alpaca now; Polygon, Tradier, Tiingo as possible backups | No longer a code blocker; still a live-provider/readiness gate |
| VWAP | Hard filter rule: "never long below VWAP unless capitulation." Also used as trend line. | **implemented from intraday bars** | Compute from intraday bar data | No longer a code blocker; unavailable when bars are missing |
| Bollinger Bands (20-period, 2 std dev) | Chop/compression detection and overextension identification | **implemented as intraday technicals / chop context** | Compute from intraday bar data | No; keep testing live behavior |
| Opening range (first 30-45 min) | Regime filter: trend vs. range day | **partial** | Compute from intraday bar data | No; current agent has opening-range regime labels but not full value-area context |
| Prior day value area | Regime filter component | **missing** | Volume profile data; complex to compute | No — nice-to-have, not blocking |
| Order flow / DOM / Level 2 | Reads ladder for absorption vs. offering | **missing** | Databento, Bookmap, Exegy | No — flag as limitation |
| Footprint / delta divergence | Exhaustion detection | **missing** | Databento, tick data | No — flag as limitation |
| News classification | Distinguish emotional/temporary vs. fundamental repricing | **missing** | LLM classification, manual Desk input, or rule-based heuristics | No — can start with manual |
| Short interest | Forced-flow signal | partial | FMP provider may have this | No — nice-to-have |
| Mid/large-cap universe | Trades liquid stocks, not small-caps | partial | Add universe preset for mid/large-cap | No — configurable |

## What Can Be Built NOW (Without New Data)

Even without 2-min bar data, the following components are scannable with the
current equity snapshot layer:

1. **Abnormal daily move detection**: stock moving >2x ATR or >5% (if normally
   stable) — detectable from daily data
2. **High premarket volume / large gap**: already in the scanner
3. **Fresh news catalyst**: already partially in the scanner (filing/catalyst
   detection)
4. **Consecutive down/up days**: computable from daily bar history
5. **RVOL filter**: already available
6. **Earnings calendar**: obtainable
7. **Sector relative strength**: partially computable from current data

This is enough for an **underlying watchlist** that surfaces candidates. The
entry triggers, stops, and volume confirmation require 2-min bar data.

## Build Priority

### Phase 1: Underlying Watchlist (Current Data)

- Profile draft encoding the framework
- Scanner preset: abnormal daily move + high RVOL + news catalyst + gap
- Output: "potential mean-reversion setup — requires intraday confirmation"
- Cannot output entry/exit signals

### Phase 2: Intraday Scanner (Current Bar-Backed Mode)

- Use configured 2-min bar provider (Alpaca path exists)
- Compute: VWAP, prior bar high/low, 2x volume comparison, consecutive bar
  count, rate of change, 20-period MA, Bollinger Bands
- Implement entry triggers: prior 2-min bar break
- Implement VWAP filter
- Implement 2x volume rule
- Implement regime filter (opening range)
- Output: specific entry signals with stop and target levels

### Phase 3: Order Flow Enhancement (Future)

- Research and add order-flow / footprint data provider
- Implement DOM absorption detection
- Implement delta divergence detection
- These are genuine method components but not required for a functional
  scanner — the entry/stop/target rules work without them

## Guardrail Requirements

- Do not output buy/sell calls, position sizes, or targets as advice.
- Do not present a setup as tradeable unless entry trigger, stop, and target
  fields are all source-backed and data-backed.
- Treat all performance claims as self-reported. Flag claim inflation.
- Never output the 25% sizing rule or "exponential bet sizing" as advice.
- The VWAP rule and stop rule are educational filters, not trading
  instructions.
- Flag order flow / footprint as an unsupported method component.

## Comparison: Data Gap Severity

| Profile | Rules Exist? | Data Exists? | Gap Type |
| --- | --- | --- | --- |
| Brando Le | **No** (zero rules) | No (options chain) | **Source gap** — cannot fix with data |
| Timothy Sykes | Yes | Partially | **Data gap** — fixable |
| Lance Breitstein | **Yes** (most concrete rules) | Mostly for bar-backed scanner when providers are configured | **Policy + provider-quality gap** — deepen decision policy and validate live bars |

The Breitstein profile is the strongest candidate for the next production
scanner because the gap is purely data, not rules.
