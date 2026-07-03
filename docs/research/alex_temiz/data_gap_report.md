# Alex Temiz Data Gap Report

## Current Repo Fit

The project has a strong foundation for small-cap equity scanning and premarket gaps, which overlaps nicely with Temiz's target market (US small-cap equities). The scanner can currently identify stocks trading below their previous close (the "First Red Day" entry trigger). However, the primary structural gap is identifying the *preceding* conditions — specifically, the multi-day parabolic run that sets up the trade.

## Required Data Before Production Scanner

| Need | Why It Matters | Current Status | Candidate Sources | Blocks Profile? |
| --- | --- | --- | --- | --- |
| Daily bar history (multi-day) | Required to identify the parabolic, multi-day run-up that is a prerequisite for the "First Red Day" strategy. | **missing** | yfinance (history), Alpaca (bars), Polygon | **Yes — blocks the core setup identification** |
| VWAP | Primary chart indicator for trend and strength. | **missing** | Alpaca, Polygon, or compute from intraday bars | No — but blocks full strategy replication |

## Structural Mismatches

- **Intraday vs. Daily Setup:** Unlike Lance Breitstein, whose triggers rely heavily on 2-minute bar data (intraday), Temiz's primary "First Red Day" setup relies heavily on daily bar data (historical context). The scanner currently focuses mostly on the current day's snapshot and previous close.

## Guardrail Requirements

- Do not output buy/sell calls, position sizes, or targets as advice.
- Treat all performance claims ($16M+) as self-reported and flag the existence of his paid course.
- Emphasize the requirement of strict stop losses and broker-level guardrails as part of the strategy context.

## Recommended Next Build Step

### Phase 1: Underlying Watchlist (Current Data)

- Create a scanner preset that filters for small-caps breaking below their previous close with high volume.
- Output: "potential First Red Day trigger — verify multi-day run manually."

### Phase 2: Historical Scanner (After Daily Bar History)

- Add a daily bar history provider (e.g., pulling the last 5-10 days of data).
- Implement a "multi-day run" detector (e.g., 3+ consecutive green days, >50% run up).
- Combine with the break of previous close to generate specific, high-confidence First Red Day candidate alerts.

## Highest-Priority NotebookLM Extractions

- **Chat With Traders Ep 323** (`https://chatwithtraders.com/ep-323-alex-temiz/`): Priority High. Essential for documenting his strict risk management and guardrail philosophy.
- **First Red Day Strategy Page** (`https://www.tradezella.com/strategies/first-red-day`): Priority High. Core mechanics of his primary setup.
