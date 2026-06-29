# Small-Cap Evidence Enrichment Design

## Goal

Add an evidence layer on top of the small-cap scanner so a future
Sykes-style agent can discuss candidates with better context and fewer
unsupported assumptions. The enrichment layer should expose what the data layer
knows about float, share supply, exchange/listing context, recent filings,
catalysts/news, and former-runner history while keeping missing fields explicit
as unknown.

This is still a discovery and watchlist workflow. It must not provide buy/sell
recommendations, broker execution, or claimed Timothy Sykes endorsement.

## Current Context

The scanner already ranks candidates by:

- market-cap fit across nano, micro, and small tiers
- positive gap size
- absolute volume and relative volume
- data confidence

The repo already has useful profile plumbing:

- `AssetProfile.float_shares`
- `AssetProfile.shares_outstanding`
- `AssetProfile.exchange`
- FMP and yfinance profile providers
- SQLite asset caching

The current scanner intentionally marks `float`, `catalyst`, `filings`,
`former_runner`, `liquidity`, and `short_interest` as unknown. This design
starts reducing those unknowns only where the repo can ground the answer in
actual data.

## Source Strategy

Use a layered source strategy:

1. Local cache first, so repeated scans are deterministic and cheap.
2. Existing profile providers for float, shares outstanding, exchange, and
   listing context.
3. SEC EDGAR JSON APIs for recent filing metadata.
4. Optional news/catalyst providers later. In v1, a provider interface and
   cached evidence shape can exist, but unavailable news must stay unknown.
5. Former-runner history from local historical scans. Do not infer a
   former-runner label from a single current gap.

Short-interest and borrow context remain out of scope for v1 unless a reliable
free source is added. They should stay unknown.

## Data Model

Add evidence dataclasses:

- `SmallCapEvidence`
  - `ticker`
  - `float_shares`
  - `shares_outstanding`
  - `float_source`
  - `exchange`
  - `is_low_float`
  - `filings`
  - `catalysts`
  - `former_runner`
  - `missing_fields`
  - `risk_notes`
  - `sources`
  - `updated_at`

- `FilingEvent`
  - `ticker`
  - `form_type`
  - `filed_at`
  - `accession_number`
  - `description`
  - `source_url`
  - `risk_tags`

- `CatalystEvent`
  - `ticker`
  - `headline`
  - `published_at`
  - `source`
  - `url`
  - `summary`
  - `confidence`

- `FormerRunnerEvent`
  - `ticker`
  - `event_date`
  - `max_gap_pct`
  - `max_volume`
  - `source_run_id`
  - `notes`

Attach `SmallCapEvidence | None` to `SmallCapCandidate`. This keeps candidate
ranking and evidence separated but colocated for tools and renderers.

## Database Additions

Add small, source-oriented cache tables:

- `ticker_filings`
  - one row per recent filing event
  - unique by ticker/accession number

- `ticker_news`
  - one row per catalyst/news event
  - unique by ticker/url or ticker/headline/published_at

- `ticker_runner_history`
  - derived from local scan history or manual import
  - one row per prior runner event

Avoid persisting full enriched scan reports in v1. The scanner can assemble
enriched output dynamically from the latest raw scan plus evidence caches.

## Service Design

Add `SmallCapEvidenceService`:

```text
SmallCapScannerService.scan(...)
  -> ranked candidates
  -> SmallCapEvidenceService.enrich(candidates)
  -> candidates with evidence
```

Responsibilities:

- Load cached asset profiles for all candidate tickers.
- Derive float context from profile fields.
- Pull cached filings and optionally refresh recent filings through a provider.
- Pull cached catalysts if available.
- Pull local former-runner records if available.
- Compute remaining `missing_fields` by subtracting supported evidence from the
  preset missing-field list.
- Add risk notes for stale, missing, or high-risk evidence.

Provider boundaries:

- `SECProvider` handles CIK lookup and recent filing metadata from SEC JSON
  endpoints.
- `NewsProvider` remains an interface in v1; concrete implementation can come
  later.
- Existing `ProfileService` remains the profile source.

## Scoring Behavior

Evidence should improve explanation quality before it changes ranking.

V1 rules:

- Low float adds `low_float_context` to matched signals and a risk note.
- Recent offering-related filings add risk notes and risk tags.
- Fresh catalyst/news adds `verified_catalyst` only when a provider returns a
  timestamped source.
- Former-runner context adds `former_runner_context` only from local history.
- Missing evidence remains explicit in `missing_fields`.

Do not upgrade a weak scan to `A_WATCH` solely because one evidence field is
present. Price/volume/liquidity still gate the ranking.

## Tool And CLI Output

`scan_small_caps` JSON output should include an `evidence` block per candidate:

- float/shares/listing context
- filing summaries and risk tags
- catalyst summaries
- former-runner summaries
- remaining missing fields
- risk notes

CLI output should stay compact:

- `Float`
- `Catalyst`
- `Filing Risk`
- `Former`

Full details belong in JSON, not a crowded terminal table.

## Error Handling

- Provider failures should not fail the scan.
- Failed enrichment should add notes and keep evidence fields unknown.
- SEC rate-limit or network failures should be surfaced as source notes.
- Unknown CIK should make filings unknown, not clean/no-risk.
- Stale cache should be marked stale rather than silently trusted.

## Testing Strategy

Use offline tests with fakes only:

- profile evidence marks float known and removes `float` from missing fields
- absent profile keeps `float` unknown
- SEC fake filings add filing events and risk tags
- provider failures do not crash scans
- `scan_small_caps` JSON includes evidence
- CLI imports and renders enriched fields
- full existing scanner tests continue passing

## Non-Goals

- No broker execution.
- No buy/sell recommendations.
- No paid-data dependency as a required path.
- No short-interest or borrow-cost claims in v1.
- No dedicated trader profile or `.claude` agent file yet.

## References

- SEC EDGAR APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- Existing repo profile fields: `AssetProfile.float_shares`,
  `AssetProfile.shares_outstanding`, and `ProfileService`
