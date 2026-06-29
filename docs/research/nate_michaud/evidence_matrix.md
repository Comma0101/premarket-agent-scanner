# Nate Michaud Evidence Matrix

Each row must map a source-backed lesson to scanner support or a data gap.

| ID | Source IDs | Category | Extracted Lesson | Confidence | Scanner-Supported Fields | Missing Fields | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EV-001 | NM-001, NM-002 | setup | The ABCD Pattern requires finding an initial spike (A), a pullback (B), a higher low (C), and anticipating a breakout past A (D). | high | direction, volume, latest price | intraday pattern state, intraday peak/trough detection | Core momentum setup requiring live intraday structural recognition. |
| EV-002 | NM-003, NM-002 | setup | The Red-to-Green setup triggers when a stock moving below the previous close crosses back above it on increasing volume, signaling a momentum shift. | high | previous close, latest price, direction, volume | intraday price velocity leading to the close line | Captures significant sentiment shifts intraday. |
| EV-003 | NM-004 | philosophy | "Trade the ticker, not the company": Fundamental analysis is irrelevant for these setups; focus solely on price action, volume, and volatility. | high | volume, RVOL, gap %, direction | none (relies on existing market metrics) | Simplifies filtering by removing fundamental constraints. |
| EV-004 | NM-005 | indicator | VWAP acts as a critical line for market sentiment and support/resistance ("VWAP Boulevard"). Trading above is bullish, below is bearish. | high | basic VWAP, latest price | distance to VWAP, historical VWAP reactions | Essential for risk management and bias determination. |
| EV-005 | NM-001, NM-003 | risk | Risk must be strictly defined against technical levels before entry (e.g., stopping out below Point B in ABCD or below previous close in Red-to-Green). | high | previous close, latest price | defined entry price, stop level, position sizing | Follows strict risk management rules over intuition. |
| EV-006 | NM-006 | setup | Heavily shorted stocks holding support (like VWAP) can create squeeze opportunities as short sellers are forced to cover. | high | volume, RVOL, basic VWAP | short interest, borrow availability, short float % | Highly relevant for momentum ignition. |
