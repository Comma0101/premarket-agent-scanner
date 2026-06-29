# Alex Temiz (MIC) Evidence Matrix

Evidence rows turn public sources into operational lessons. A lesson can become an agent/scanner rule only when the current data layer can source the required fields.

| ID | Sources | Theme | Source-Backed Observation | Confidence | Current Scanner Fields | Missing Fields / Data Needs | Implementation Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EV-AT-001 | AT-011, AT-013, AT-014 | identity | Co-founder of MIC, $16M+ verified trader (claims). Focuses on small-cap momentum. | high | none | none | Attribution only. |
| EV-AT-002 | AT-010, AT-013 | method_primary | Primary method: **First Red Day**. Target stocks with massive, parabolic, multi-day run-ups that show signs of exhaustion. There is no strict "number of green days" required, but the move must be parabolic. | high | ticker, gap, volume | multi-day run detection | Core setup. Scannable with daily bar history. |
| EV-AT-003 | AT-010 | entry_trigger | Enters short when price breaks below the **previous day's closing price** or **previous day's low**. This traps late buyers. | high | previous close, previous low | current day price vs previous day levels | **Directly scannable**. |
| EV-AT-004 | AT-011, AT-014 | stop_placement | Stops are based on market structure (e.g., day's high or recent resistance). Hard stop set *before* entry. If stock reclaims the previous day's level, thesis is invalidated. | high | none | intraday highs, resistance levels | Scannable once intraday bars exist. |
| EV-AT-005 | AT-010, AT-014 | profit_taking | Scales out of the position ("covers into the panic") to lock in realized P&L cushion. Target depends on the speed of the breakdown. | high | none | none | Desk output / trade management, not entry rule. |
| EV-AT-006 | AT-011, AT-014 | market_instrument | **Equities only.** Specializes in US small-cap equities. Does not trade options. | high | ticker, price | none | Current equity scanner is perfect. |
| EV-AT-007 | AT-011, AT-014 | vwap_usage | Uses VWAP as primary chart reference for market strength/weakness. Monitors if price "bounces" or "fails" at VWAP to gauge institutional money flow. | high | none | VWAP | Scannable once VWAP exists. |
| EV-AT-008 | AT-011, AT-013 | risk_management | Uses strict broker-level "guardrails", hard daily loss limits to prevent revenge trading. "Start small" and only "scale into winners" (add to the fail). Never average down a loser. | high | none | none | Desk output language / execution rule. |
| EV-AT-009 | AT-013 | psychology | Written "Perfect Trade Checklist" before entry (e.g., must meet 8 of 12 criteria). Process over magic. | high | none | none | Educational lens. |
| EV-AT-010 | AT-012, AT-014 | adaptability | While known as a short-seller, actively pivots to long-biased trading (e.g., VWAP bounces) during hot, bull-market environments. | high | none | none | Strategy toggling. |
| EV-AT-011 | AT-080 | verification | Claims are self-reported or verified via marketing/broker screenshots. Operates a paid course (MIC). Reddit debates legitimacy of paid room. | medium | none | none | Flag in profile. |
