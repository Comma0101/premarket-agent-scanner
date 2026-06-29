# Roland Wolf Distillation Notes

## Scope

This document distills public Roland Wolf material into a non-impersonating Roland Wolf-style educational lens. It does not claim endorsement or private access.

## Source-Backed Principles

- Emphasize simplicity and "clean charts." Avoid complex, lagging indicators in favor of price action, volume, VWAP, and horizontal Support/Resistance (S/R). (`EV-003`)
- Focus on the psychology of the market, specifically the traps set for retail "newbies" (e.g., chasing morning spikes). (`EV-001`, `EV-002`)
- Strict risk management is paramount. Losses must be cut quickly if the anticipated bounce or reversal fails to materialize. (`EV-005`)
- Understand the "cap table" (float, dilution, warrants). A low float with a catalyst can squeeze, while heavy dilution usually leads to failure (the "crap"). (`EV-004`)

## Candidate Setup Rules

### Gap & Crap (Gap-Crap-Reversal)

- Evidence: `EV-001`, `EV-004`, `EV-006`
- Concept: A stock gaps up significantly premarket on a catalyst, spikes at the open, but fails to sustain momentum and washes out (the "crap"). The trade is to buy the reversal at a key support level or VWAP.
- Current scanner mapping: `direction=up`, `min_gap_abs=5.0` (to find the initial gapper).
- Unsupported but important: Intraday price action (to detect the wash and reversal), VWAP, historical S/R levels, real-time float/dilution checks.
- Profile readiness: partial (can find the gappers, cannot detect the "crap" or reversal automatically without intraday bars).

### Panic Dip Buy

- Evidence: `EV-002`, `EV-004`, `EV-005`
- Concept: Buying a stock during a sharp, emotional sell-off (panic) with the expectation of a quick snap-back bounce. Requires capitulation volume.
- Current scanner mapping: `direction=down`, high `volume` or `RVOL`.
- Unsupported but important: Intraday drop velocity, capitulation volume spikes (e.g., 1-minute or 5-minute volume climax), historical support levels.
- Profile readiness: partial (can find down-movers, but cannot qualify the "panic" without intraday velocity).

## Risk And Psychology Rules

- Never chase the initial morning spike blindly; wait for the setup (the wash or the panic) to develop. (`EV-001`)
- Do not trade without a hard stop based on a clear support level. (`EV-005`)
- Avoid complex indicators that clutter decision-making. (`EV-003`)
- Always verify the catalyst to understand why the panic or gap is happening. (`EV-006`)

## Rules Not Yet Supported By Data

- The "crap" and "reversal" phases of the Gap & Crap strategy require live intraday bar analysis (1m/5m), which our snapshot scanner doesn't natively do well without an intraday service. (`EV-001`)
- "Panic" requires measuring the velocity and volume climax of a drop intraday. (`EV-002`)
- Accurate float, warrants, and dilution history ("cap table") are critical to his strategy and are currently data gaps. (`EV-004`)
- Support and Resistance levels require querying the `DailyBarHistoryService` and analyzing historical pivots. (`EV-003`)

## Profile Readiness

Status: partial

Rationale:
- The scanner can successfully identify the candidates (large premarket gappers and high RVOL names) required for Roland Wolf's setups.
- The actual *triggers* for his strategies (the morning wash, the panic capitulation, the VWAP bounce) are heavily dependent on intraday price action and volume analysis, which requires more than just premarket snapshot data.
- The lack of comprehensive dilution/warrant data is a gap for accurately predicting which gappers will "crap" and fail completely versus those that will reverse.
