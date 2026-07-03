# Cameron Fous Evidence Matrix

Each row must map a source-backed lesson to scanner support or a data gap.

| ID | Source IDs | Category | Extracted Lesson | Confidence | Scanner-Supported Fields | Missing Fields | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EV-001 | CF-001, CF-002 | setup | The Fous4 strategy relies on identifying four specific momentum breakout patterns (Force, Revival, Survival, Gold) before they occur. | high | gap %, direction, volume | chart pattern state, historical price action | Core to the Fous4 methodology. |
| EV-002 | CF-001, CF-004 | risk | Every trade must have a strict 2:1 profit-to-loss ratio target, requiring predefined entries and stop-losses. | high | confidence label | entry price, stop level, target price, risk/reward ratio | Fundamental risk management rule. |
| EV-003 | CF-003, CF-005 | setup | Technical indicators such as the 13-day EMA, RSI, and MACD are used to confirm momentum breakouts. | high | volume, price | 13-day EMA, RSI, MACD | Used for entry confirmation and trend identification. |
| EV-004 | CF-004 | setup | Short-selling setups (Fous4x2) target momentum breakdowns and fades, requiring borrow availability. | high | gap %, direction, volume | short interest, borrow availability, borrow cost | Expands the strategy to bear markets. |
| EV-005 | CF-001, CF-003 | data_gap | Relying on mechanical pattern recognition requires multi-day chart structure analysis to classify "Force" or "Revival" patterns. | high | volume, RVOL, gap %, direction | multi-day pattern state, intraday chart structure | The scanner currently only identifies daily gaps, not complex multi-day chart patterns. |
| EV-006 | CF-003 | data_gap | The 13-day EMA is a required indicator for trend confirmation, which must be calculated from historical daily closes. | high | gap %, direction | 13-day EMA, historical moving averages | Essential indicator for Fous setups. |
