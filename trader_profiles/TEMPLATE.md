# Trader Profile: <NAME / SOURCE>

> Fill one of these out per trader you study. The Premarket Desk agent reads this
> file and turns the rules below into concrete `scan_premarket` filters and an
> A/B/C grading rubric. Keep every rule *operational* — something the scanner can
> actually filter on (gap, RVOL, cap tier, direction, volume), not vibes.
>
> Copy this file to `trader_profiles/<name>.md` and edit. The agent never invents
> data, so a profile only changes *judgment* (what to look for and how to grade),
> never the numbers.

## Identity
- **Trader / source:** <name, handle, book, interview series…>
- **Status of notes:** <draft | partial | mature> — how much you've collected.
- **Markets / instruments:** <US equities, small-cap momentum, large-cap, etc.>
- **Session focus:** <premarket gappers, opening drive, …>

## Core edge (one paragraph)
<What is this trader actually exploiting? e.g. "Low-float small-caps gapping on a
catalyst with outsized RVOL, fading the first push or riding continuation.">

## Preferred setups
List each setup with the filters it implies. Example shape:

- **Setup name** — direction `up`, `cap_tier: small`, `min_gap_abs: 5`,
  `min_rel_volume: 3`, `min_volume: 1_000_000`.
  - Why it qualifies:
  - Disqualifiers / what kills it:

## Scanner filter mapping (the literal scan)
The default scan the agent should run for this profile:

```
scan_premarket(
    universe / watchlist / all_universes = ...,
    cap_tier = ...,
    direction = ...,
    min_gap_abs = ...,
    min_rel_volume = ...,
    min_volume = ...,
)
```

## Grading rubric (A / B / C)
- **A:** <ideal: e.g. small cap, gap ≥ 8%, RVOL ≥ 5, OK confidence>
- **B:** <decent but missing one ingredient, or one data caveat>
- **C:** <marginal / thin / flagged data>

## Avoid / red flags
- <e.g. extended large caps, RVOL < 2, CONFLICT or STALE data, illiquid (low volume)>

## Notes & open questions
- <things you still need to learn / confirm about this trader's style>
