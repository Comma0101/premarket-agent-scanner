# Ross Cameron Evidence Matrix

Each row must map a source-backed lesson to scanner support or a data gap.

| ID | Source IDs | Category | Extracted Lesson | Confidence | Scanner-Supported Fields | Missing Fields | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EV-101 | RC-001 | setup | Gap and Go requires a minimum 4% pre-market gap up on high volume with a strong news catalyst. | high | gap %, direction, volume | catalyst/news text, news strength, intraday setup | Core criteria for Gap and Go. |
| EV-102 | RC-001 | market_structure | Stocks that do not hold the pre-market high or sell off heavily before the open are typically avoided. | high | premarket price, high | intraday pattern state, 1-min candle data | Price action context. |
| EV-103 | RC-002 | setup | Momentum breakouts target low-float stocks surging on high volume that are "in play." | high | volume, RVOL, cap tier | true float, Level 2 depth | Float is critical for volatility. |
| EV-104 | RC-002 | setup | Technical patterns include flat top breakouts, bull flags, and opening range breakouts (ORB). | high | gap %, volume | intraday chart pattern state, 1-min/5-min charts | Strategy relies on chart patterns. |
| EV-105 | RC-003 | setup | VWAP is an essential equilibrium indicator; setups below VWAP are generally avoided. | high | | VWAP, price relative to VWAP | Requires intraday VWAP calculation. |
| EV-106 | RC-003 | setup | 9 EMA and 20 EMA are used for short-term trend identification and pullback entries. | high | | 9 EMA, 20 EMA on 1-min and 5-min charts | Requires intraday EMA. |
| EV-107 | RC-004 | risk | Strict stop-loss rules (like the low of a 1-minute candle) and quick cutting of losses are mandatory. | high | confidence label | entry price, stop level, account risk | Risk management is heavily emphasized. |
