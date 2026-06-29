# Steven Dux Evidence Matrix

Each row must map a source-backed lesson to scanner support or a data gap.

| ID | Source IDs | Category | Extracted Lesson | Confidence | Scanner-Supported Fields | Missing Fields | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EV-001 | SD-001, SD-004 | statistical edge | Strategies must be built on tracking historical pattern frequency, win rates, and profit-to-risk ratios. | high | gap %, gap $, volume, RVOL | historical pattern win rate, profit-to-risk ratio | Core to Dux's data-driven approach. |
| EV-002 | SD-002 | setup | Gap Up Short setup targets overextended small caps that gap up significantly in the premarket, expecting early session failure. | high | gap %, gap $, direction, market cap, cap tier | intraday pattern state, VWAP, previous close test | Core short setup. |
| EV-003 | SD-002 | setup | Bounce Short setup targets stocks that have dropped significantly, bounce to key resistance/VWAP, and fail. | high | direction, volume | intraday chart structure, key resistance levels, VWAP | Core short setup. |
| EV-004 | SD-002 | setup | First Red Day setup focuses on multi-day parabolic runners that close red, trapping late buyers. | high | direction, volume | multi-day chart structure, previous day close | Core short setup. |
| EV-005 | SD-005 | scanner | Targets should have a market cap under $300M-$500M (small-cap to micro-cap). | high | market cap, cap tier | float | Explicit market cap filter. |
| EV-006 | SD-005 | scanner | Requires high liquidity (e.g. volume >10M shares) for smooth entry and exit on short positions. | high | volume | order book depth, bid/ask spread, session liquidity profile | Strict liquidity requirement. |
| EV-007 | SD-006 | setup | Volume surges near key resistance or VWAP indicate large player distribution and offer a confirmation signal. | high | volume | level 2 data, order flow, intraday VWAP | Volume and resistance analysis. |
| EV-008 | SD-003 | risk | Maximum risk per trade is strictly 1-2% of total account; losses must be cut immediately if the thesis invalidates. | high | confidence label | account balance, entry price, stop level, risk calculation | Primary risk rule. |
| EV-009 | SD-006 | market_structure | Do not anticipate tops; wait for confirmation like breaking below previous close or failing at resistance before entering shorts. | high | direction | intraday support/resistance, level 2 confirmation | Execution discipline rule. |
