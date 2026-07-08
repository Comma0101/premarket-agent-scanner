# Advanced Lance Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first advanced Lance layer: a market scan service that ranks Lance-style candidates and persists a structured watchlist with why each ticker is being watched.

**Architecture:** Keep providers raw, compute Lance ranking in `services/lance_market_scan_service.py`, persist watchlist rows through `app/db.py`, and expose one JSON-safe agent tool in `agent_tools`. The existing `LanceIntradayPlanService` remains the per-ticker plan-card engine; the new scanner decides which tickers deserve plan cards.

**Tech Stack:** Python dataclasses/dicts, SQLite via `app/db.py`, existing `ScannerService`, `LanceIntradayPlanService`, and offline pytest fakes.

---

### Task 1: Market Scan Service Tests

**Files:**
- Create: `tests/test_lance_market_scan_service.py`

**Steps:**
1. Write a failing test where fake scanner rows rank a high-move/high-RVOL candidate above a low-RVOL candidate.
2. Write a failing test where the service persists watchlist rows with `why_watching`, `playbook`, `state`, `invalidates_if`, and `next_step`.
3. Run: `.venv/bin/python -m pytest tests/test_lance_market_scan_service.py -q`
4. Expected: fail because the service and DB helpers do not exist yet.

### Task 2: DB Schema And Helpers

**Files:**
- Modify: `app/db.py`

**Steps:**
1. Add `lance_watchlist_items` table with session id, ticker, state, score, playbook, why, invalidation, next step, data quality JSON, plan JSON, timestamps.
2. Add idempotent migration in `_migrate`.
3. Add helpers: `upsert_lance_watchlist_item`, `get_lance_watchlist_items`.
4. Run the failing tests again.

### Task 3: Lance Market Scan Service

**Files:**
- Create: `services/lance_market_scan_service.py`

**Steps:**
1. Compose `ScannerService` and `LanceIntradayPlanService`.
2. Scan selection using broad Lance filters: direction both, minimum absolute move, confidence OK.
3. Score candidates using abnormal move, RVOL, plan state, 2x volume, pressure, and prior-bar trigger.
4. Persist top candidates when requested.
5. Return JSON-safe output with session id, counts, candidates, notes, and guardrail disclaimer.
6. Run service tests until green.

### Task 4: Agent Tool

**Files:**
- Modify: `agent_tools/tools.py`
- Modify: `agent_tools/definitions.py`
- Modify: `tests/test_agent_tools.py`

**Steps:**
1. Add failing tool test for `run_lance_market_scan`.
2. Add tool function with injectable service.
3. Register schema and dispatch entry once.
4. Run tool tests.

### Task 5: Verification

**Commands:**
- `.venv/bin/python -m pytest tests/test_lance_market_scan_service.py tests/test_agent_tools.py -q`
- `.venv/bin/ruff check services/lance_market_scan_service.py app/db.py agent_tools/tools.py agent_tools/definitions.py tests/test_lance_market_scan_service.py tests/test_agent_tools.py`
- `scripts/verify.sh`

### Task 6: Live Smoke

**Command:**
- Run `run_lance_market_scan` over `all_universes=True`, `max_candidates=10`, `persist=True`.

**Expected:** A ranked Lance watchlist with source/as-of/gap_basis/confidence carried through from the data layer.
