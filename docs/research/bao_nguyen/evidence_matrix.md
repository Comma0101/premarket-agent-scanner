# Bao Nguyen Evidence Matrix

Each row must map a source-backed lesson to scanner support or a data gap.

| ID | Source IDs | Category | Extracted Lesson | Confidence | Scanner-Supported Fields | Missing Fields | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EV-001 | BN-003 | setup | VWAP Boulevard lines are created by identifying the highest-volume days in a stock's history and plotting the VWAP from those days as static support/resistance levels. | high | volume | historical anchored VWAP, highest historical volume days | Core mechanical setup used for finding key intraday levels. |
| EV-002 | BN-001, BN-004 | setup | "Nail and Bail" is a high-speed scalping strategy targeting momentum spikes, requiring rapid entry and exit. | high | gap %, volume | Level 2 order data, tape reading speed | Strategy is highly dependent on order flow, not just static chart patterns. |
| EV-003 | BN-004 | setup | "Line to Line" trading involves shorting at known resistance levels (like VWAP Boulevard) and covering at support. | high | gap %, direction | intraday support/resistance lines | Range-bound trading tactic. |
| EV-004 | BN-001, BN-004 | setup | Short-selling low-float stocks is a primary focus, especially when they are extended away from VWAP. | high | volume, RVOL, market cap | float, short interest, borrow availability | Current scanner uses market cap proxy; actual float is missing. |
| EV-005 | BN-001, BN-002 | risk | Traders must define strict daily loss limits and "size down" to handle the wider ranges of modern markets. | high |  | trader plan adherence, position sizing | Core risk management rule. |
| EV-006 | BN-002 | risk | Setups should be graded (e.g., A++ setups) to ensure high probability and favorable risk-to-reward before entering. | high | volume, RVOL, gap % | setup grading criteria, historical win rate | Emphasizes selectivity. |
