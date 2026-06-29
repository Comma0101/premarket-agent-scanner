# Trader Profile: Lance Breitstein (Mean Reversion After Capitulation)

> Distilled from public sources only (YouTube interviews, TradeZella strategy
> page, articles). No paid course content. All performance claims are
> self-reported and unverified by public independent audit. This profile encodes
> method rules, not trading advice.
>
> **Critical data note**: This profile requires **2-minute intraday bar data**
> and **VWAP** for entry triggers, stops, and volume confirmation. Without these,
> the profile can only identify candidate underlyings (Phase 1). Entry/exit
> signals require Phase 2 data.
>
> **Missing method components**: Order flow (DOM/tape), footprint/delta analysis
> are core to the source's method but cannot be automated with current data
> providers. These are flagged as limitations.

## Identity
- **Trader / source:** Lance Breitstein (@TheOneLanceB), ex-Trillium Trading
  top PnL trader (2011-2021), advisor @SMBCapital, profiled in Market Wizards:
  The Next Generation.
- **Status of notes:** mature — NotebookLM extraction of primary video source
  completed with 42-question granular prompt.
- **Markets / instruments:** US equities (shares only). Does NOT trade options.
  Watches options flow for gamma signals. Methods described as applicable to ES,
  NQ, Gold futures but primary execution is equities.
- **Session focus:** Market open (primary — flush-outs from overnight panic
  accumulation) and close (secondary — liquidity pool). Avoids midday
  capitulation trades unless breaking news present.

## Core edge (one paragraph)
Trade the snap-back after extreme, fast, emotional price dislocations. When a
stock capitulates — panic selling, forced liquidation, margin calls — the move
is temporarily overextended and likely to revert toward equilibrium. The edge is
NOT picking random tops/bottoms; it is waiting for the "turn" (confirmation
that the move has exhausted) and entering on the right side of the V with a
defined stop. Expected value is the governing framework: stack conditions that
increase reversal probability, expand reward, and define risk. Speed of the move
is the most important factor — fast moves are more likely to revert than slow
grinds.

## Preferred setups

### Mean Reversion After Capitulation (PRIMARY)
- **Direction:** `both` (long flush-outs, short euphoric spikes)
- **Cap tier:** mid, large (liquid names with news catalysts, not micro-caps)
- **Entry trigger (requires 2-min bars):** Break of prior 2-min bar high (for
  longs after downtrend respecting those highs) or prior 2-min bar low (for
  shorts after uptrend holding those lows).
- **Confirmation required:**
  - 2x volume on panic bar vs. prior bar
  - VWAP filter: never long if steadily holding below VWAP unless capitulating;
    never short if steadily holding above VWAP unless capitulating
  - Right side of the move only — no front-side fading
- **Stop (requires 2-min bars):** Prior 2-min bar low (longs) or high (shorts).
  Hard stop. "I am always getting out at my stop if that gets breached."
- **Target:** 20-period MA (equilibrium). Trail stop along 2-min bar lows/highs.
  Scale out if stock "capitulates and gets euphoric" in your favor.
- **Condition stacking (more = stronger setup):**
  - Large move size (abnormal vs. normal daily range)
  - Fast speed of move (accelerating, not grinding)
  - News-driven but NOT a fundamental value change
  - Consecutive directional bars (3+)
  - Forced buying/selling (margin calls, liquidations)
  - Sentiment extremes
  - Normally stable asset suddenly volatile
  - Clean price structure during the move
  - Multi-timeframe alignment (intraday + daily + weekly trend all same side)
- **Why it qualifies:** High expected value when conditions stack. Fast panic
  creates temporary dislocation. Confirmation reduces risk.
- **Disqualifiers:** Slow grinding move (no panic), Bollinger Band compression
  (chop), midday without news, stock holding steadily below VWAP (for longs)
  without capitulation, fundamental repricing (not emotional/temporary).

### Consolidation Breakout (SECONDARY)
- Stock tightens into a range, volume dies off, then surges on breakout.
- Entry on break of consolidation level with "enormous volume."
- Less detailed in public sources than mean-reversion setup.

### Earnings Continuation (SECONDARY)
- Earnings as catalyst for continuation breakouts (cited TSLA pre-split, NVDA
  AI guidance gap).
- Entry on continuation of earnings-driven move.

## Scanner filter mapping

### Phase 1: Underlying Watchlist (current data — no intraday bars)

```
scan_premarket(
    all_universes = true,
    direction = "both",
    min_gap_abs = 3,
    min_rel_volume = 3,
    cap_tier = ["mid", "large"],
)
```

Plus manual Desk check for: fresh news catalyst, whether catalyst is
emotional/temporary vs. fundamental repricing, sector theme of the day.

Output: "Potential mean-reversion candidate — requires intraday 2-min bar
confirmation for entry signal."

### Phase 2: Intraday Scanner (after 2-min bar data + VWAP)

```
# Not yet implementable — requires new data layer
# Logic: scan for stocks with abnormal intraday move + 2x volume panic bar
# + prior 2-min bar break + VWAP filter
# Entry: prior 2-min bar high break (longs) or low break (shorts)
# Stop: prior 2-min bar low (longs) or high (shorts)
# Target: 20-period MA
```

## Grading rubric (A / B / C)

### Phase 1 (Underlying Watchlist Only)
- **A:** Gap ≥ 5%, RVOL ≥ 5, fresh news catalyst (emotional/temporary), fast
  move (abnormal vs. normal range), `confidence: OK`, mid/large-cap.
- **B:** Solid gap + RVOL but missing one condition (no clear catalyst, or
  catalyst may be fundamental repricing), or one data caveat.
- **C:** Marginal gap, low RVOL, slow grinding move, Bollinger compression,
  no catalyst, or `CONFLICT`/`STALE` data.

### Phase 2 (With Intraday Bars — Future)
- **A:** All Phase 1 A conditions + 2x volume panic bar + prior 2-min bar
  break confirmed + VWAP filter passed + multi-timeframe alignment.
- **B:** Good underlying but missing one intraday confirmation (volume < 2x,
  or VWAP filter marginal, or no multi-timeframe alignment).
- **C:** Underlying qualifies but intraday setup not confirmed — no entry
  signal, wait.

## Avoid / red flags
- **Never fade the front side** of a move (buying a falling knife without
  confirmation) — no defined stop, leads to massive losses.
- **Never average down** against a trend — biggest past losses from taking too
  much heat instead of stopping out.
- **Never long if steadily holding below VWAP** unless capitulating (and vice
  versa for shorts).
- **Avoid midday capitulation trades** without breaking news — suspicious moves.
- **Avoid chop / Bollinger Band compression** — no directional edge in ranges.
- **Avoid efficient, highly-traded names** (SPY, GLD) as daily watchlist —
  "99% noise." Hunt "in-play" stocks instead.
- **Avoid fundamental repricings** — mean reversion only works on
  emotional/temporary dislocations, not permanent valuation changes.
- **Self-reported performance claims**: Claim escalation pattern (8-figure →
  $100M+) with no public independent audit. Kinfo profile private. X account
  suspended. Flag in all Desk output.

## Verified performance claims (self-reported, no public audit)
- "8-figure trader" (2022) → "$60M+" (2025) → "$100M+" (2026)
- #1 trader at Trillium (firm vouching, no public records)
- Kinfo #1 all-time PnL leaderboard (profile now private)
- Market Wizards: The Next Generation (Schwager saw brokerage statements
  privately, not public)
- **All claims are self-reported. No independent public audit exists.**

## Specific concrete rules (directly implementable)
1. **VWAP Rule:** Never long below VWAP unless capitulating. Never short above
   VWAP unless capitulating.
2. **2x Volume Rule:** Valid capitulation bar must have 2x volume of prior bar.
3. **Entry Trigger:** Break of prior 2-min bar high (longs) or low (shorts).
4. **Stop:** Prior 2-min bar low (longs) or high (shorts). Always honored.
5. **Target:** 20-period moving average (equilibrium reference).
6. **Alignment Sizing:** Size up 25% when intraday + daily trends align
   (project cannot output sizing advice — flag as quality signal only).
7. **Scratch Rule:** Exit at breakeven/small loss if thesis breaks before stop
   is hit.
8. **Daily Report Card:** Grade self on rule execution, not P&L.

## Notes & open questions
- LB-011 (Humbled Traders, 1.5h) and LB-012 (TraderLion, 3h18m) are not yet
  extracted — may contain additional mechanical detail.
- Order flow / DOM / footprint are core method components that cannot be
  automated. The profile must flag this as a significant limitation.
- News classification (emotional/temporary vs. fundamental repricing) is hard
  to automate. May need manual Desk input or LLM classification.
- The "Reference Price" concept (unaffected close before catalyst) can be
  approximated by the scanner's prior close comparison.
- Should the profile include futures (ES, NQ, Gold) or remain equities-only?
- Sector rotation is a theme, not a fixed filter — how should the scanner
  handle theme-of-the-day selection?
