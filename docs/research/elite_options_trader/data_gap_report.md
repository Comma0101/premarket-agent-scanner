# Elite Options Trader Data Gap Report

This report tracks what the repo needs before an Elite Options-style agent can be
more than a source-backed educational lens.

## Current Repo Fit

The project currently has strong equity snapshot, premarket, small-cap, catalyst,
filing, and universe-scanning foundations. That is enough to rank underlying
stocks, but not enough to rank option contracts.

The Elite Options public material points to options/day trading on large-cap and
mega-cap underlyings. A true scanner for this profile therefore needs both a
separate options data layer and a large-cap/mega-cap universe (the current
universe scanner is small-cap oriented).

## Required Data Before Contract Scanning

| Need | Why It Matters | Current Status | Candidate Sources / Notes |
| --- | --- | --- | --- |
| Options chain | Required to enumerate available calls/puts by strike and expiration. | missing | Evaluate Alpaca options, Tradier, Polygon, ThetaData, CBOE-delayed sources, or broker APIs. |
| Contract quote | Need bid, ask, midpoint, last, timestamp, and spread. | missing | Must carry source and as-of timestamp like equity snapshots. |
| Contract liquidity | Wide spreads and low open interest can make an options setup unusable. | missing | Volume, open interest, spread percent, and quote freshness. |
| Expiration / DTE | Public material flags 0DTE risk; DTE is mandatory for that gate. | missing | Derive from contract metadata. |
| Greeks / IV | Options risk depends on IV, delta, theta, gamma, and event risk. | missing | May not be available from every low-cost provider. Keep unknown when missing. |
| Underlying levels | Public method emphasizes support/resistance and price action. | missing | Need intraday/daily bars, pivot/high-low helpers, and possibly VWAP. |
| Relative strength | Public method mentions relative strength. | missing | Compare underlying move to SPY/QQQ/sector over defined windows. |
| Market regime / chop | Public method says to sit out unclear/choppy conditions. | missing | Needs trend/chop classifier and index context. |
| Event calendar | Earnings and macro events can dominate option pricing. | missing | Earnings calendar, economic calendar, major scheduled catalysts. |
| Risk/reward plan | Public material references 3:1 risk/reward. | missing | Requires entry, invalidation, and target levels; do not infer these from price alone. |
| Large-cap universe | Source focuses on TSLA and other mega-caps, not small-caps. | partial | Current universe scanner is small-cap oriented. Need a large-cap/mega-cap watchlist (SPY/QQQ components, or top-100 by market cap). |

## Structural Mismatches with Current Scanner

| Mismatch | Detail | Resolution Path |
| --- | --- | --- |
| Small-cap vs. mega-cap | The existing scanner targets small-cap gappers. Brando's public material focuses on TSLA-class names. | Add a large-cap/mega-cap universe preset, or accept that this profile operates on a different universe. |
| Equity vs. options | The scanner grades equity setups. Brando's lens requires option contract selection. | Build an options provider layer before exposing contract-level tools. |
| Stop-loss philosophy | Standard risk management uses stop losses. The source explicitly rejects them as a "breakthrough." | Never automate the no-stop-loss claim. Preserve as a caveat in any profile output. |
| Marketing density | The public X feed has a high ratio of marketing/self-promotion to method detail compared to, e.g., the Sykes public material. | Strictly separate educational principles from outcome claims in the evidence matrix. |

## Guardrail Requirements

- Do not output options buy/sell calls, targets, or position sizes.
- Do not present a contract as tradeable unless quote freshness, liquidity, and
  key fields are source-backed.
- Do not import paid Discord alerts or private membership material.
- Treat performance claims as self-reported unless independently verified.
- Preserve conflicting/risky source statements as caveats, not automation rules.
- The no-stop-loss claim must appear as a flagged caveat in any profile, never
  as a rule.

## Recommended Next Build Step

Build this in three layers:

1. **Profile-only draft**: `trader_profiles/elite_options_trader.md` as a partial
   lens that maps to underlying equity scans and clearly marks options fields as
   unavailable. Include the stop-loss caveat prominently.

2. **Underlying watchlist spike**: Add a large-cap/mega-cap universe preset so
   the existing equity scanner can at least surface the right underlyings for
   this lens (TSLA, NVDA, AAPL, etc.).

3. **Options data spike**: Add a provider abstraction and fake-backed tests for
   option chains, contract quotes, DTE, open interest, spread, and quote
   provenance before any contract-ranking tool is exposed.

## Sources Still Worth Manual Review

The following sources were identified but could not be fully extracted via web
fetch. Manual review may yield additional method detail, but **after NotebookLM
extraction of the two highest-priority sources, the distillation ceiling is
likely already reached** — the podcast and YouTube clip were primarily
philosophy and marketing, not mechanical rules. (`EV-EO-021`)

| Source | URL | Priority | Why |
| --- | --- | --- | --- |
| YouTube: @OptionsTraderclips fan channel | https://www.youtube.com/@OptionsTraderclips | medium | Daily clips/highlights. May contain marginal additional detail on momentum/breakout setups. |
| YouTube: @eliteoptionstrader.clips2025 | https://www.youtube.com/@eliteoptionstrader.clips2025 | low | Clips channel, 16 videos. Likely duplicates. |
| TikTok: @eliteoptionstrader.clips | https://www.tiktok.com/@eliteoptionstrader.clips | low | Short-form. Likely duplicates YouTube content. |
| Whop: Elite Beginner Trading Guide | https://whop.com/elite-options/eo-trading-guide/ | medium | Free guide covering market structure, risk management, execution, and mindset. Behind free Whop sign-up gate. This is the only remaining source that might contain structured method content not yet captured. |
