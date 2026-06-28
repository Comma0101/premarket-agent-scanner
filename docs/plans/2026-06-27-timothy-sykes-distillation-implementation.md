# Timothy Sykes Distillation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a public-source Timothy Sykes research dossier that can later support a non-impersonating, source-backed Sykes-style trading profile.

**Architecture:** Keep the first milestone entirely in `docs/research/timothy_sykes/`. Source collection, evidence extraction, operational translation, and data-fit analysis are separate files so claims can be audited before any profile or agent behavior is created.

**Tech Stack:** Markdown research docs, existing scanner code for data-field mapping, web research with public/free sources only, git commits per completed task.

---

### Task 1: Scaffold The Research Dossier

**Files:**
- Create: `docs/research/timothy_sykes/source_inventory.md`
- Create: `docs/research/timothy_sykes/evidence_matrix.md`
- Create: `docs/research/timothy_sykes/distillation_notes.md`
- Create: `docs/research/timothy_sykes/data_gap_report.md`

**Step 1: Create the directory**

Run:

```bash
mkdir -p docs/research/timothy_sykes
```

Expected: command exits with status 0.

**Step 2: Create the source inventory skeleton**

Add this content to `docs/research/timothy_sykes/source_inventory.md`:

```markdown
# Timothy Sykes Source Inventory

Public/free sources only. Do not include paid/private material.

| ID | Source | Type | URL | Published / Updated | Accessed | Why It Matters |
| --- | --- | --- | --- | --- | --- | --- |
```

**Step 3: Create the evidence matrix skeleton**

Add this content to `docs/research/timothy_sykes/evidence_matrix.md`:

```markdown
# Timothy Sykes Evidence Matrix

Each row must map a source-backed lesson to scanner support or a data gap.

| ID | Source IDs | Category | Extracted Lesson | Confidence | Scanner-Supported Fields | Missing Fields | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
```

**Step 4: Create the distillation notes skeleton**

Add this content to `docs/research/timothy_sykes/distillation_notes.md`:

```markdown
# Timothy Sykes Distillation Notes

## Scope

This document distills public Timothy Sykes material into a non-impersonating
Sykes-style educational lens. It does not claim endorsement or private access.

## Source-Backed Principles

## Candidate Setup Rules

## Risk And Psychology Rules

## Rules Not Yet Supported By Data

## Open Questions
```

**Step 5: Create the data gap report skeleton**

Add this content to `docs/research/timothy_sykes/data_gap_report.md`:

```markdown
# Timothy Sykes Data Gap Report

## Current Scanner Fields

- ticker selection
- gap percent
- dollar gap
- direction
- market cap / cap tier
- volume
- relative volume
- confidence labels

## Gaps For A Sykes-Style Lens

| Gap | Why It Matters | Current Status | Possible Future Source |
| --- | --- | --- | --- |
```

**Step 6: Verify files exist**

Run:

```bash
find docs/research/timothy_sykes -maxdepth 1 -type f | sort
```

Expected output includes exactly:

```text
docs/research/timothy_sykes/data_gap_report.md
docs/research/timothy_sykes/distillation_notes.md
docs/research/timothy_sykes/evidence_matrix.md
docs/research/timothy_sykes/source_inventory.md
```

**Step 7: Commit**

Run:

```bash
git add docs/research/timothy_sykes
git commit -m "Scaffold Timothy Sykes research dossier"
```

Expected: commit includes only the four research files.

### Task 2: Populate Public Source Inventory

**Files:**
- Modify: `docs/research/timothy_sykes/source_inventory.md`

**Step 1: Search official sources first**

Use web search/open tools with these seed URLs and related links:

```text
https://www.timothysykes.com/
https://www.timothysykes.com/blog/
https://www.timothysykes.com/blog/how-to-trade-in-premarket/
https://www.timothysykes.com/blog/how-to-use-stock-scanners/
https://www.timothysykes.com/blog/low-float-stocks/
https://www.timothysykes.com/blog/penny-stock-patterns/
```

Also search:

```text
site:timothysykes.com/blog Timothy Sykes cut losses
site:timothysykes.com/blog Timothy Sykes catalyst volume penny stocks
site:timothysykes.com/blog Timothy Sykes stock scanner
site:timothysykes.com/blog Timothy Sykes premarket
site:timothysykes.com/blog Timothy Sykes low float
```

**Step 2: Search public video/interview sources**

Use web search for:

```text
Timothy Sykes interview penny stock strategy catalyst volume
Timothy Sykes YouTube penny stock rules cut losses quickly
Timothy Sykes former runners penny stocks
Timothy Sykes supernova penny stock pattern
```

**Step 3: Add source rows**

Add rows with IDs `TS-001`, `TS-002`, and so on. Use this table shape:

```markdown
| TS-001 | How To Trade In Premarket | official blog | https://... | YYYY-MM-DD or unknown | 2026-06-27 | Premarket process, scanner criteria, risk context. |
```

Rules:

- Include at least 20 public/free sources if enough relevant sources are available.
- Include at least 8 official Timothy Sykes sources if available.
- Mark dates as `unknown` when the page does not expose one.
- Do not include inaccessible, paywalled, or private material.

**Step 4: Verify inventory density**

Run:

```bash
rg -n "^\| TS-[0-9]{3} \|" docs/research/timothy_sykes/source_inventory.md
```

Expected: at least 15 result rows. If fewer than 15 strong public sources are available, add a note under the table explaining the limit.

**Step 5: Commit**

Run:

```bash
git add docs/research/timothy_sykes/source_inventory.md
git commit -m "Catalog public Timothy Sykes sources"
```

Expected: commit includes only `source_inventory.md`.

### Task 3: Build The Evidence Matrix

**Files:**
- Modify: `docs/research/timothy_sykes/evidence_matrix.md`
- Read: `docs/research/timothy_sykes/source_inventory.md`

**Step 1: Extract source-backed lessons**

For each strong source, add evidence rows using this shape:

```markdown
| EV-001 | TS-001, TS-004 | scanner | Premarket candidates should be filtered for meaningful price movement, volume, and relevant company context before considering them. | high | gap %, volume, RVOL, market cap | catalyst/news, filings | Repeated in official scanning/premarket material. |
```

Categories:

- `setup`
- `scanner`
- `risk`
- `psychology`
- `market_structure`
- `data_gap`

Confidence values:

- `high`: repeated in official sources or detailed in one official source
- `medium`: one official source or multiple credible secondary sources
- `low`: secondary-only, old, or inferred

**Step 2: Add at least one risk/disclaimer row**

Include source-backed cautions about educational use, risk, loss control, or avoiding unsupported claims.

**Step 3: Verify every evidence row has source IDs and confidence**

Run:

```bash
rg -n "^\| EV-[0-9]{3} \|" docs/research/timothy_sykes/evidence_matrix.md
```

Expected: every row has a `TS-` source reference and confidence value `high`, `medium`, or `low`.

**Step 4: Commit**

Run:

```bash
git add docs/research/timothy_sykes/evidence_matrix.md
git commit -m "Extract Timothy Sykes evidence matrix"
```

Expected: commit includes only `evidence_matrix.md`.

### Task 4: Write The Operational Distillation Notes

**Files:**
- Modify: `docs/research/timothy_sykes/distillation_notes.md`
- Read: `docs/research/timothy_sykes/evidence_matrix.md`

**Step 1: Summarize source-backed principles**

Write short bullets under `## Source-Backed Principles`.

Every bullet must end with source/evidence references:

```markdown
- Prefer small, volatile names where price movement and volume show real participation. (`EV-001`, `EV-006`)
```

**Step 2: Draft candidate setup rules**

Use this format:

```markdown
### Small-Cap Premarket Gapper

- Evidence: `EV-001`, `EV-004`
- Current scanner mapping: `cap_tier=small`, `direction=up`, `min_gap_abs=<pragmatic threshold>`, `min_rel_volume=<pragmatic threshold>`
- Unsupported but important: float, catalyst/news quality, dilution/offering risk
- Profile readiness: partial
```

If a threshold is pragmatic rather than source-explicit, label it as such.

**Step 3: Draft risk and psychology rules**

Include only rules backed by evidence rows. Good examples:

```markdown
- Do not present a setup as tradeable when confidence is `CONFLICT`, `STALE_DATA`, or missing required fields. (`EV-...`)
- Treat unsupported catalyst or float assumptions as unknown, not inferred. (`EV-...`)
```

**Step 4: Add open questions**

List rules that need stronger evidence or new data before profile implementation.

**Step 5: Verify every major rule cites evidence**

Run:

```bash
rg -n "EV-[0-9]{3}" docs/research/timothy_sykes/distillation_notes.md
```

Expected: every principle, setup, and risk rule cites at least one `EV-` row.

**Step 6: Commit**

Run:

```bash
git add docs/research/timothy_sykes/distillation_notes.md
git commit -m "Distill Timothy Sykes operating rules"
```

Expected: commit includes only `distillation_notes.md`.

### Task 5: Map Distillation To Current Data Layer

**Files:**
- Modify: `docs/research/timothy_sykes/data_gap_report.md`
- Read: `app/models.py`
- Read: `services/scanner_service.py`
- Read: `agent_tools/definitions.py`

**Step 1: Confirm current scanner-supported fields**

Read these files:

```bash
sed -n '1,220p' app/models.py
sed -n '1,260p' services/scanner_service.py
sed -n '1,220p' agent_tools/definitions.py
```

Confirm the fields listed in `data_gap_report.md` match actual models and tool schemas.

**Step 2: Fill the gap table**

Use this row shape:

```markdown
| Float / low-float classification | Sykes-style setups often depend on supply constraints and squeeze potential. | unsupported | FMP profile, Polygon, Nasdaq, SEC filings, or yfinance float fallback |
```

Minimum required gaps:

- float / low-float classification
- catalyst/news quality
- SEC filing / offering / dilution risk
- former-runner history
- intraday pattern state
- OTC/listing context
- short interest or borrow context

**Step 3: Add implementation priority**

Below the table, add:

```markdown
## Suggested Data-Layer Priority

1. Float and listing/OTC context.
2. Catalyst/news and SEC filing ingestion.
3. Former-runner and intraday pattern history.
4. Short interest/borrow context.
```

**Step 4: Verify no unsupported field is described as available**

Run:

```bash
rg -n "unsupported|partial|supported" docs/research/timothy_sykes/data_gap_report.md
```

Expected: each gap row clearly says `unsupported`, `partial`, or `supported`.

**Step 5: Commit**

Run:

```bash
git add docs/research/timothy_sykes/data_gap_report.md
git commit -m "Map Timothy Sykes rules to scanner data gaps"
```

Expected: commit includes only `data_gap_report.md`.

### Task 6: Final Research Review

**Files:**
- Modify: `docs/research/timothy_sykes/source_inventory.md`
- Modify: `docs/research/timothy_sykes/evidence_matrix.md`
- Modify: `docs/research/timothy_sykes/distillation_notes.md`
- Modify: `docs/research/timothy_sykes/data_gap_report.md`

**Step 1: Check citation consistency**

Run:

```bash
rg -n "TS-[0-9]{3}|EV-[0-9]{3}" docs/research/timothy_sykes
```

Expected: `EV-` references in distillation notes correspond to rows in the evidence matrix; `TS-` references in the evidence matrix correspond to rows in the source inventory.

**Step 2: Add final readiness note**

Append this section to `docs/research/timothy_sykes/distillation_notes.md`:

```markdown
## Profile Readiness

Status: not ready | partial | ready

Rationale:

- ...
```

Use `partial` unless all core Sykes-style rules are supported by current or planned data fields.

**Step 3: Run final text checks**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

Run:

```bash
rg -n "impersonat|endorsement|private access|invent" docs/research/timothy_sykes
```

Expected: the docs preserve the non-impersonation and no-invented-data constraints.

**Step 4: Commit**

Run:

```bash
git add docs/research/timothy_sykes
git commit -m "Review Timothy Sykes research dossier"
```

Expected: final commit includes only review/readiness changes.

### Task 7: Stop Before Profile Implementation

**Files:**
- Read: `docs/research/timothy_sykes/distillation_notes.md`
- Read: `docs/research/timothy_sykes/data_gap_report.md`

**Step 1: Summarize the dossier**

Prepare a short user-facing summary:

- what was strongly supported
- what was only partially supported
- what the current scanner can do now
- what data must be added before a high-fidelity Timothy Sykes-style agent

**Step 2: Ask for approval before profile work**

Do not create `trader_profiles/timothy_sykes.md` yet. Ask whether to proceed to:

1. profile-only implementation,
2. data-layer expansion first,
3. dedicated agent plus profile.

Expected: no code or profile changes happen without that next approval.
