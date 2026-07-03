# Roland Wolf Evidence Matrix

Each row must map a source-backed lesson to scanner support or a data gap.

| ID | Source IDs | Category | Extracted Lesson | Confidence | Scanner-Supported Fields | Missing Fields | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EV-001 | RW-001, RW-002 | setup | The Gap & Crap setup requires a stock that gaps up premarket but fails to hold, leading to a morning wash before reversing. | high | gap %, gap $, premarket price, direction, open | intraday price action (1m/5m bars), VWAP bounce, support/resistance levels | Requires live intraday tracking to identify the "crap" and "reversal". |
| EV-002 | RW-003, RW-004 | setup | Panic Dip Buy relies on finding extreme, emotional sell-offs with capitulation volume, rather than just any downward movement. | high | volume, RVOL, direction | capitulation volume spikes, intraday drop velocity, short-term RSI | Needs velocity of the drop and intraday volume spikes. |
| EV-003 | RW-005 | indicator | Complex lagging indicators should be avoided; the focus is on clean charts using price action, volume, and horizontal Support/Resistance. | high | price, volume | VWAP, historical S/R lines | The scanner needs basic VWAP and ability to query historical daily bars for S/R. |
| EV-004 | RW-006, RW-001 | market_structure | The "cap table" (float, dilution risk, warrants) is critical for determining if a stock has the potential to squeeze or if it will fail. | high | market cap, cap tier | true float, free float, recent offerings, warrants, SEC filings | Current scanner relies on market cap; true float and dilution data are gaps. |
| EV-005 | RW-004, RW-002 | risk | Trades must have a strict, predefined risk-reward ratio, and losses must be cut immediately if the pattern breaks. | high | confidence label | entry price, strict stop level, account risk | Execution planning belongs outside the scanner, but setups must offer clear S/R stops. |
| EV-006 | RW-006 | setup | Premarket preparation involves identifying catalysts that drive the initial gap, to understand why the stock is moving. | high | gap %, volume, RVOL | catalyst/news, headline source, timestamp | Scanner needs catalyst verification. |
