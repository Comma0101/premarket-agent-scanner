# Desk Integration & Fixes — Implementation Plan (for Codex)

> **For Codex:** Execute this plan **task by task, in order.** After each task run its
> verification block and commit before moving on. Do **not** skip verification. Do
> **not** push to a remote or delete any branch/worktree until a task explicitly says
> to ask the human. If a step's reality differs from this document, stop and report
> the difference rather than guessing.

## Read first (non-negotiable context)

1. Read `AGENTS.md` at the repo root. It is the shared contract. The **prime
   directive** governs everything: *never invent a number.* Honor the guardrails
   (read-only on the market, no buy/sell advice, no impersonation).
2. Environment: use `.venv/bin/python` (3.12). Tests must run **offline**.
   - Test: `.venv/bin/python -m pytest -q`
   - Lint: `.venv/bin/ruff check .`
3. Commits: small and scoped. End every commit message with:
   `Co-Authored-By: Codex <codex@openai.com>` (or your configured trailer).
   Do not `git push` in this plan.

## Goal

Consolidate the parallel branch stack (dossier → small-cap scanner → evidence →
agent-orchestrator) onto a single integration branch built on top of the
already-built **MCP spine + `gap_basis`** work, then apply five fixes. End on a
clean integration branch with the full suite green, and **stop before** merging to
`main` or pushing.

## Current state you are starting from

- `main` (HEAD `96a6dcb`) carries the plan/design docs **plus uncommitted work**:
  the MCP server (`mcp_server/`, `.mcp.json`), `gap_basis` (in `app/models.py`,
  `services/scanner_service.py`, `app/db.py`, `agent_tools/tools.py` and their
  tests), the `premarket-desk` agent + `trader_profiles/`, and `AGENTS.md`.
  Confirm with `git status` before Task 1.
- Local branches (not all on origin) form a stack; the superset is
  `feature/agent-orchestrator` (scanner + evidence + market-universe + orchestrator,
  **but** missing the CLI/README and missing all `gap_basis`/MCP work).
- `feature/sykes-small-cap-scanner-autonomous` is the only branch with
  `cli/scan_small_caps.py` + the README section.

---

### Task 1: Establish the integration base (commit the uncommitted spine)

**Why:** the whole stack must be rebased onto `gap_basis`, so that work has to be a
real commit first. The human has delegated this commit.

**Step 1 — confirm what's uncommitted**

```bash
git status --short
.venv/bin/python -m pytest -q
```

Expected: the modified/untracked set listed above; suite green.

**Step 2 — commit the MCP + gap_basis milestone**

Stage and commit exactly these (do NOT include `AGENTS.md` or this plan yet):

```bash
git add mcp_server .mcp.json .claude trader_profiles \
        app/models.py app/db.py services/scanner_service.py \
        agent_tools/tools.py tests/test_scanner.py tests/test_agent_tools.py \
        tests/test_mcp_server.py README.md pyproject.toml
git commit -m "Add MCP server spine, gap_basis provenance, and desk persona"
```

**Step 3 — commit the shared agent contract separately**

```bash
git add AGENTS.md \
        docs/plans/2026-06-28-desk-integration-and-fixes-implementation.md \
        docs/plans/2026-06-28-sykes-data-layer-roadmap.md
git commit -m "Add AGENTS.md shared agent contract, integration plan, and data-layer roadmap"
```

**Verify**

```bash
git status --short        # clean
.venv/bin/python -m pytest -q   # green
```

---

### Task 2: Create the integration branch

```bash
git switch -c integration/desk-v1
```

All remaining work happens here. `main` is untouched until the human approves the
final merge.

---

### Task 3: Merge the orchestrator superset, resolving conflicts by union

**Step 1 — merge**

```bash
git merge --no-ff feature/agent-orchestrator
```

Conflicts are expected in shared files: `app/models.py`, `app/db.py`,
`agent_tools/tools.py`, `agent_tools/definitions.py`, and their tests.

**Step 2 — conflict-resolution policy: keep BOTH sides (union).**

The base side carries `gap_basis` + MCP; the incoming side carries the small-cap /
evidence / orchestrator additions. Neither should be dropped. Specifically:

- `app/models.py`: keep the `gap_basis` field on `ScannerResult` **and** all the
  new dataclasses (`SmallCapScannerPreset`, `SmallCapCandidate`, `SmallCapEvidence`,
  `FilingEvent`, `CatalystEvent`, `FormerRunnerEvent`, `SmallCapScanOutput`, etc.).
- `agent_tools/tools.py`:
  - `_result_to_dict` MUST keep `"gap_basis": result.gap_basis`.
  - `get_ticker_snapshot` MUST use
    `SnapshotService.with_configured_providers()` (NOT bare `SnapshotService()`)
    and MUST include `"gap_basis": gap_basis_for(snap)` in its output. The incoming
    side regressed both — restore them.
  - Keep the new `scan_small_caps` tool and all evidence `_*_to_dict` helpers.
- `app/db.py`: keep the `gap_basis` column + its `_migrate` guard **and** the new
  evidence/news/runner-history tables and accessors.
- `agent_tools/definitions.py`: keep all four tools in `TOOLS` and `_DISPATCH`.

**Verify**

```bash
git diff --check                 # no conflict markers / whitespace errors
.venv/bin/python -m pytest -q    # green
.venv/bin/ruff check .
```

If any test asserts the old yfinance-only snapshot or a missing `gap_basis`, update
it to the corrected behavior. Commit the merge once green.

---

### Task 4: Bring in the CLI + README from the autonomous branch

The superset dropped `cli/scan_small_caps.py` and the README section. Recover them.

```bash
git checkout feature/sykes-small-cap-scanner-autonomous -- cli/scan_small_caps.py
```

Then re-add the "Small-Cap Discovery Scanner" section to `README.md` (see that
branch's README for the exact block). If `cli/_render.py` helpers it imports are
absent, add the missing formatter(s) or inline simple equivalents.

**Verify**

```bash
.venv/bin/python -c "import cli.scan_small_caps as m; assert m.app is not None"
.venv/bin/python -m pytest -q
git add cli/scan_small_caps.py README.md && git commit -m "Restore small-cap CLI and README section"
```

---

### Task 5 (Fix A — 🔴): Collapse the cap-tier loop into one scan

**Problem:** `SmallCapScannerService.scan` runs a full provider scan once **per cap
tier** (`nano`, `micro`, `small`). Each pass fetches a live snapshot for every
ticker, so a `market="us-listed"` run does ~3× the network calls. Because a ticker
has exactly one market cap, the tiers never overlap and the per-tier dedupe is dead
weight.

**Fix:** scan **once** over the union of the preset's cap bounds.

**Step 1 — failing test** in `tests/test_small_cap_scanner.py`: assert that for a
preset with three contiguous tiers the underlying `ScannerService.scan` is called
**once** (not three times), with `filters.min_market_cap == 0` and
`filters.max_market_cap == 2_000_000_000`. Use a `FakeScanner` that records calls.

**Step 2 — implement** in `services/small_cap_scanner_service.py`. Replace the
`for cap_tier in preset.cap_tiers:` loop with a single scan using union bounds:

```python
from app.models import resolve_cap_tier  # (low, high|None) per tier

def _union_cap_bounds(cap_tiers: list[str]) -> tuple[float, float | None]:
    lows, highs = [], []
    for tier in cap_tiers:
        low, high = resolve_cap_tier(tier)
        lows.append(low or 0.0)
        highs.append(float("inf") if high is None else high)
    upper = max(highs)
    return min(lows), (None if upper == float("inf") else upper)
```

Build one `make_scan_filters(min_market_cap=low, max_market_cap=high, ...)`, call
`scanner_service.scan` once, grade each result, keep the existing
`candidates_by_ticker` best-score dedupe (now a safety net, not the main path).
Preserve the `market` resolution + notes exactly as today.

**Step 3 — update** any existing test that assumed one scan per tier (e.g. the
`{call["filters"].max_market_cap for call in fake.calls}` design test) to the
single-call shape.

**Verify**

```bash
.venv/bin/python -m pytest tests/test_small_cap_scanner.py -q
git commit -am "Scan small-cap cap tiers in a single union pass"
```

> If collapsing churns too many tests, fall back to gating: keep the per-tier loop
> for explicit `tickers`/`watchlist`/`universe`, and union **only** when `market` or
> `all_universes` is set (the expensive paths). Document which you chose in the
> commit message.

---

### Task 6 (Fix B — 🔴): Thread `gap_basis` through the small-cap layer + gate A-grades

**Problem:** the small-cap scanner/orchestrator never carry `gap_basis`, so a top
grade can be granted on a `last_trade` price. Per `AGENTS.md`, A-grade requires
`gap_basis == "premarket"`.

**Step 1 — model:** add `gap_basis: str | None = None` to `SmallCapCandidate`
(`app/models.py`).

**Step 2 — grading** in `services/small_cap_scanner_service.py`:
- In `_candidate(...)`, copy `gap_basis=result.gap_basis`.
- In `_grade(...)`, accept the basis and **cap the grade at `B_WATCH` when
  `gap_basis == "last_trade"`** (i.e. only allow `A_WATCH` when
  `gap_basis == "premarket"`). When basis is `None`, keep current behavior but add a
  risk note `"gap_basis unknown; not a confirmed premarket move."`
- Add a matched-signal/risk note so the reason is visible
  (e.g. risk note `"gap_basis=last_trade — last regular/last trade, not a premarket quote."`).

**Step 3 — surface it:**
- `agent_tools/tools.py::_small_cap_candidate_to_dict` → add `"gap_basis": candidate.gap_basis`.
- `agent_orchestrator/`: add `gap_basis` to `AgentWatchCandidate` (its models) and to
  `_agent_candidate(...)`, and include it in `_evidence_summary`/output so the packet
  states basis next to the gap.

**Step 4 — tests** in `tests/test_small_cap_scanner.py`:
- A result with `gap_basis="premarket"`, strong gap/RVOL/volume, OK confidence →
  `A_WATCH`.
- The same result with `gap_basis="last_trade"` → at most `B_WATCH`, with a risk note
  mentioning `last_trade`.

**Verify**

```bash
.venv/bin/python -m pytest -q
git commit -am "Gate small-cap A-grade on premarket gap_basis"
```

---

### Task 7 (Fix C — 🟠): Cache the SEC CIK map; require a real User-Agent

**Problem:** `SECProvider._resolve_cik` re-downloads `company_tickers.json` for every
ticker (it caches only the matched ticker). The default User-Agent is a placeholder
SEC may reject (403).

**Step 1 — failing test** in `tests/test_small_cap_evidence.py` (or a new
`tests/test_sec_provider.py`): inject a fake JSON fetcher that counts calls; resolve
two different tickers and assert the company-tickers file is fetched **once**.

**Step 2 — implement** in `providers/sec_provider.py`:
- Add a private `_load_cik_map()` that fetches `company_tickers.json` **once**, builds
  the full `{TICKER: zero-padded-CIK}` map, and memoizes it on the instance
  (`self._cik_map`). `_resolve_cik` reads from that map.
- Make the contact User-Agent explicit: keep `SEC_USER_AGENT` env override, but if it
  is unset/placeholder, surface a clear note in the evidence rather than silently
  sending `contact@example.com`. (Do not hard-fail enrichment — degrade to "filings
  unknown" with a reason, per the prime directive.)
- Keep `_request_json` injectable for tests (allow passing the fetcher in `__init__`).

**Verify**

```bash
.venv/bin/python -m pytest tests/test_small_cap_evidence.py -q   # plus any new sec test
git commit -am "Cache SEC CIK map and surface User-Agent requirement"
```

---

### Task 8 (Fix D — 🟡): Close the logging DB connection

**Problem:** `agent_tools/definitions.py::_log` uses `with get_connection(...) as conn:`
— sqlite3's context manager commits but does **not** close, leaking a connection per
logged tool call.

**Fix:** wrap with `contextlib.closing`:

```python
from contextlib import closing
...
with closing(get_connection(db_path)) as conn:
    log_agent_query(conn, ...)
```

(Or add explicit `try/finally: conn.close()`.) Add/adjust a small test that logging a
call doesn't leak — or at minimum that `_log` still records to `agent_queries`.

**Verify**

```bash
.venv/bin/python -m pytest -q
git commit -am "Close agent-query logging connection"
```

---

### Task 9 (Fix E — 🟡, document only): Note the evidence N+1

Do **not** re-architect now. Add a short `## Known limitations` note to the README
(or `docs/research/timothy_sykes/data_gap_report.md`) stating that
`SmallCapEvidenceService.enrich_candidates` does a serial profile+filings round-trip
per candidate and should be batched/concurrent before running it behind a full
`market` scan.

```bash
git commit -am "Document evidence enrichment N+1 follow-up"
```

---

### Task 10: Full verification

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
git diff --check
git log --oneline main..HEAD
```

Expected: whole suite green, lint clean, no whitespace errors, a readable commit
series on `integration/desk-v1`.

---

### Task 11: Stop and hand back (do not merge or push)

Prepare a short report for the human:

- the commit series on `integration/desk-v1`,
- test count before/after,
- exactly which conflicts were resolved and how,
- which fix used which approach (note the Fix A fallback if taken),
- branches/worktrees now subsumed and safe to delete.

Then **ask for approval** before any of these irreversible / outward-facing actions:

1. merging `integration/desk-v1` into `main`,
2. pushing anything to `origin`,
3. deleting the subsumed branches (`feature/sykes-small-cap-scanner`,
   `-autonomous`, `feature/small-cap-evidence-enrichment`, `feature/agent-orchestrator`,
   `research/timothy-sykes-distillation`) and their worktrees.

Do not perform 1–3 without that approval.
