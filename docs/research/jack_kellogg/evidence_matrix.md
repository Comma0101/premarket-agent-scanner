# Jack Kellogg Evidence Matrix

Each row must map a source-backed lesson to scanner support or a data gap.

| ID | Source IDs | Category | Extracted Lesson | Confidence | Scanner-Supported Fields | Missing Fields | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EV-001 | JK-001, JK-003 | setup | Trading should focus on simple indicators like VWAP, Volume, Support/Resistance, and Linear Regression rather than overly complex combinations. | high | volume, VWAP (if available) | support/resistance levels, linear regression | "KISS" principle is foundational to his process. |
| EV-002 | JK-002 | scanner | For long positions, avoid buying stocks that are overextended above the VWAP to prevent chasing and to adhere to buying low. | high | VWAP (if available), latest price | distance from VWAP | Requires computing percentage distance of current price above VWAP. |
| EV-003 | JK-002 | scanner | For short positions, avoid shorting stocks that are extended below the VWAP, as sentiment is already weak and entry is suboptimal. | high | VWAP (if available), latest price | distance from VWAP | VWAP acts as a primary entry and risk filter. |
| EV-004 | JK-002, JK-003 | scanner | Volume must be surging to confirm momentum and validate a breakout; low volume moves are generally ignored. | high | volume, RVOL | trade count, order book depth | Surging volume indicates conviction from market participants. |
| EV-005 | JK-004 | setup | OTC breakouts and low float stocks are preferred because constrained supply leads to sharper price spikes when demand enters. | high | cap tier, volume | float, free float, OTC market classification | The scanner needs to distinguish OTC from listed exchanges and know the true float. |
| EV-006 | JK-004 | setup | Stocks in hot sectors or with significant news catalysts provide the necessary demand to fuel high momentum plays. | high | gap %, direction, RVOL | sector tag, catalyst/news, headline quality | Hot sectors require grouping tickers by industry or theme. |
| EV-007 | JK-005 | risk | Cut losses immediately when price action invalidates the setup, regardless of what the indicators suggest. Avoid "death by a thousand paper cuts." | high | confidence label | stop level, entry price, position size | Price action supersedes indicators. Risk management happens outside the scanner. |
