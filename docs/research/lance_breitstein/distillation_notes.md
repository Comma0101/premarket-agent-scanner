# Lance Breitstein Distillation Notes

## Scope

This document distills public Lance Breitstein material into a non-impersonating
educational lens. It does not claim endorsement, private access, or access to
paid course content (Magnum Opus).

## Source-Backed Principles

- **Equities day trader / scalper, not options.** "We trade equities... we're
  professionals." Watches options flow for gamma signals but executes in shares.
  The current equity scanner is the right tool — no options data layer needed.
  (`EV-LB-019`)
- **Mean reversion after capitulation** is the primary setup. Trades the
  snap-back after extreme, fast price moves. Slow grinding moves do not
  qualify. (`EV-LB-002`)
- **Expected value framework** governs all decisions. (win prob × reward) −
  (loss prob × risk). Grade setups on condition-stacking quality, not just
  directional bias. (`EV-LB-003`)
- **Speed is the primary signal.** Fast moves = panic, forced liquidation,
  emotional decision-making → higher reversion probability. (`EV-LB-004`)
- **Right side of the move only.** Never catches exact tops/bottoms. Waits for
  the "turn" or "counter-trend" to confirm. Fading the front side leads to
  massive losses with no defined stop. (`EV-LB-007`)
- **Hard stop losses.** "I am always getting out at my stop if that gets
  breached." Stop = below prior 2-min bar low (for longs) or above prior 2-min
  bar high (for shorts). (`EV-LB-014`)
- **Never average down against a trend.** Biggest past losses came from taking
  too much heat instead of stopping out. (`EV-LB-026`)
- **VWAP is a hard filter.** "Never be long if a stock is steadily holding
  below VWAP unless it capitulates. Vice versa for shorting." (`EV-LB-017`)
- **Volume confirms capitulation.** Wants 2x the volume on the panic bar
  compared to the prior bar. (`EV-LB-018`)
- **Multi-timeframe alignment.** 2-min chart for entries. Daily/weekly/monthly
  for trend confirmation. Sizes 25% larger when intraday and daily trends align
  (project cannot output sizing advice, but can flag alignment quality).
  (`EV-LB-010`)
- **Market open and close are the primary windows.** Open: retail can't sell
  overnight → panic accumulates → flush-outs. Close: liquidity pool for
  panics. Midday: avoid capitulation trades unless breaking news. (`EV-LB-021`)
- **Hunt "in-play" stocks, not fixed watchlists.** "Broken slot machine"
  concept. Screen for largest gappers, highest premarket volume, fresh news.
  Avoid watching efficient names (SPY, GLD) daily — "99% noise." (`EV-LB-020`)
- **Sector rotation.** No fixed sector. Rotate to current theme. (`EV-LB-027`)
- **Daily loss limit / temperature check.** Dynamic risk reduction when
  distracted, tired, or market is slow. (`EV-LB-025`)
- **Chop = Bollinger Band compression / consolidation.** Avoid for mean
  reversion. (`EV-LB-030`)
- **Relative strength/weakness vs. sector and market.** Short stocks flat on
  strong-sector days. Long stocks panicking more than the broader market on
  down days. (`EV-LB-031`)

## Candidate Setup Rules

### Mean Reversion After Capitulation (Primary Setup)

- Evidence: `EV-LB-002`, `EV-LB-004`, `EV-LB-007`, `EV-LB-013`, `EV-LB-016`
- **Scanner filters (underlying identification):**
  - Abnormal daily move (>2x ATR, or >5% for normally stable stock)
  - High premarket volume / large premarket gap
  - Fresh news catalyst (emotional/temporary, not fundamental repricing)
  - Fast rate of change (accelerating move, not grinding)
  - Consecutive directional bars (3+ in one direction)
  - RVOL > 3 (estimated; source uses "huge volume")
  - Not in Bollinger Band compression / chop
- **Entry triggers (require 2-min bar data):**
  1. Break of prior 2-min bar high (after downtrend respecting those highs)
  2. Break of prior 2-min bar low (after uptrend holding those lows)
  3. Trend structure shift (lower highs/lows → higher highs/lows)
  4. Extreme panic single-candle reversal (smaller size, less defined risk)
- **Confirmation required:**
  - 2x volume on the panic bar vs. prior bar (`EV-LB-018`)
  - VWAP filter: not long below VWAP (unless capitulation), not short above
    VWAP (unless capitulation) (`EV-LB-017`)
- **Stop:** Prior 2-min bar low (longs) or high (shorts) (`EV-LB-014`)
- **Target:** 20-period MA (equilibrium). Trail stop along 2-min bar lows/highs.
  Scale out if stock "capitulates and gets euphoric" in your favor. (`EV-LB-015`)
- **Condition stacking:** Large move + fast speed + news (not fundamental) +
  consecutive bars + forced flows + sentiment extreme + stable asset suddenly
  volatile + clean structure. More conditions = higher EV = higher confidence.
  (`EV-LB-016`)
- Profile readiness: **directly scannable once 2-min bar data and VWAP exist**

### Consolidation Breakout (Secondary Setup)

- Evidence: `EV-LB-013`
- Stock tightens into a range, volume dies off midday, then surges heavily on
  breakout. Entry on break of consolidation level.
- Current scanner mapping: not supported. Needs intraday consolidation
  detection and volume profile.

### No-Trade / Chop Filter

- Evidence: `EV-LB-009`, `EV-LB-030`
- Chop = Bollinger Band compression, range-bound, volatility squeezing.
- Avoid mean-reversion setups in chop. Wait for expansion.
- First 30-45 min determines regime: trend day vs. range day.
- Midday capitulation trades are suspicious unless breaking news present.

### VWAP Filter

- Evidence: `EV-LB-017`
- Hard rule: never long if steadily holding below VWAP (unless capitulation).
  Never short if steadily holding above VWAP (unless capitulation).
- The "unless it capitulates" exception is the mean-reversion trigger itself —
  the stock flushing far below VWAP and then reversing is the setup.

## Rules Not Yet Supported By Data

- **2-minute bar data** — required for entry triggers, stops, volume comparison,
  consecutive bar counting, rate of change. This is the single most important
  data addition needed.
- **VWAP** — required for the hard filter rule.
- **Bollinger Bands** — required for chop/compression detection and
  overextension identification.
- **Opening range** — first 30-45 min high/low for regime identification.
- **Order flow / DOM / Level 2** — reads ladder for intent. Flag as
  unsupported limitation.
- **Footprint / delta divergence** — exhaustion detection. Flag as unsupported.
- **Prior day value area** — regime filter component.
- **News classification** — distinguish emotional/temporary catalyst from
  fundamental repricing. Hard to automate; may need manual Desk input.

## Red Flags

1. **Claim inflation**: 8-figure (2022) → $60M+ (2025) → $100M+ (2026) →
   9-figure (one Substack). No new public evidence with each escalation.
2. **No public independent audit**: No Big-4, Darwinex, Myfxbook, or live
   trading record. Schwager's private review is meaningful but not transparent.
3. **Kinfo profile now private**. Steven Dux (#1 on same platform) undermines
   Kinfo's credibility as audit.
4. **Timing**: Bulk of claimed profits from 2020-2021 easy market. Left before
   2022 harder market.
5. **Course selling**: Primary current activity. $3,497-$12,000.
6. **X account suspension**: Reason unknown.
7. **Asymmetric burden of proof**: Offered $10K bounty for others' proof while
   not providing own public audit.

**Critical distinction**: These red flags concern claim verification, not method
quality. The method content is sophisticated, internally consistent, grounded in
prop-firm concepts, and — most importantly — contains specific, scannable rules
with defined entry triggers, stops, targets, and filters. A profile can encode
the method while honestly flagging the verification gaps.

## Profile Readiness

Status: **agent-ready after 2-min bar data layer is built**

Rationale:

- This profile has the most concrete, systematic, scannable rules of any trader
  in the research project.
- Hard entry triggers (prior 2-min bar break), hard stops (prior bar low/high),
  VWAP filter, 2x volume rule, condition-stacking framework — all are specific
  and implementable.
- The primary blocker is **intraday 2-min bar data**, not missing rules.
  Once this exists, the majority of the method can be automated.
- Unlike Brando Le (zero rules, philosophy-only), this is a mechanical system
  with defined conditions.
- Unlike the Sykes-style lens (small-cap penny stock gappers), this operates on
  mid/large-cap equities with news catalysts — a different but overlapping
  universe.
- Order flow and footprint data are genuine method components that cannot be
  automated without new data providers. The profile must flag these as
  limitations, but the entry/exit/VWAP/volume rules are sufficient for a
  production scanner without them.
- **The profile does not require options data** — he trades shares only.

## Comparison with Other Traders in This Project

| Dimension | Brando Le | Timothy Sykes | Lance Breitstein |
| --- | --- | --- | --- |
| Mechanical rules in public sources | Zero | Multiple | **Most** |
| Entry triggers | None stated | OTC breakout | Prior 2-min bar break |
| Stop loss | Rejected ("breakthrough") | Stated but vague | **Hard rule**: prior bar low/high |
| Target | None stated | Multi-day swing | 20-period MA (equilibrium) |
| Instrument | Options (can't scan) | Small-cap equity | **Equity shares** (scannable) |
| Data layer needed | Options chain | Current scanner | **2-min bars + VWAP** |
| Profile readiness | profile-only | scanner-ready | **agent-ready after bar data** |
