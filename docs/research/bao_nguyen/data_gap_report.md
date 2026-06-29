# Bao Nguyen (Modern Rock) Data Gap Report

This report evaluates our current premarket scanner's ability to support Bao Nguyen's mechanical trading rules, particularly the "VWAP Boulevard" strategy.

## Current Scanner Capabilities
- **Equity Data & Basic VWAP:** We can track standard intraday VWAP, which is useful for fading extended moves.
- **Premarket Gap/Volume:** We can identify stocks with high momentum and relative volume (RVOL) to spot potential "Nail and Bail" candidates.
- **DailyBarHistoryService:** Provides multi-day context to evaluate daily trends.

## Critical Data Gaps

### 1. Anchored Historical VWAP (VWAP Boulevard)
- **Requirement:** The "VWAP Boulevard" strategy requires scanning a stock's entire trading history to find the top 1-3 highest volume days of all time, and then calculating the closing VWAP specifically for those days.
- **Gap:** While we have `DailyBarHistoryService`, we do not currently have an automated mechanism to sort historical days by volume across a stock's entire lifespan, extract the VWAP for those specific days, and project them as static levels for the current session.

### 2. Float and Borrow Data
- **Requirement:** Bao's strategies frequently target low-float stocks for short selling.
- **Gap:** We currently rely on market capitalization as a proxy for company size. True float, short interest, and borrow availability (locate data) are missing, which are mandatory for executing short strategies safely.

### 3. Level 2 and Tape Data
- **Requirement:** The "Nail and Bail" strategy is a high-speed scalp that relies on reading the tape and Level 2 order flow.
- **Gap:** Our scanner uses snapshot data (price, volume, gap). We do not stream order book depth or time-and-sales data required to confirm momentum entries for this specific tactic.

## Conclusion
To fully support the Modern Rock / MIC methodology, the scanner's data layer must be upgraded to support historical volume-anchored VWAP (VWAP Boulevard) and true float metrics. Without these, the scanner can only identify generally volatile stocks, but cannot plot the specific, mechanical support/resistance lines required by the strategy.
