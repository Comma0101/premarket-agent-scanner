---
name: market-data-guardrails
description: Enforce market-data precision and trading-agent safety. Use when producing Desk output, changing market-data models, scanner grading, evidence enrichment, trader profiles, or any feature that reports prices, gaps, volume, float, filings, catalysts, or confidence.
---

# Market Data Guardrails

## Required Data Shape

When stating market data, preserve:

- value
- unit
- source
- as-of timestamp
- `gap_basis`
- confidence label

If a value is unavailable from the current data layer or tool output, state it as unknown.

## Hard Gates

- Do not call a move a premarket gap unless `gap_basis == "premarket"`.
- Do not allow an `A_WATCH` or `primary_watch` setup unless `gap_basis == "premarket"` and confidence is `OK`.
- Do not infer float, filings, catalysts, short interest, or borrow data from price or volume.
- Do not give buy/sell/short recommendations, price targets, or position sizing.
- Do not claim to be Timothy Sykes or imply endorsement.

## Implementation Pattern

1. Keep raw external data in providers.
2. Compute derived fields in services with pure helpers when possible.
3. Carry provenance fields through models, tools, orchestrator packets, and CLI output.
4. Add regression tests for every precision or safety gate.

