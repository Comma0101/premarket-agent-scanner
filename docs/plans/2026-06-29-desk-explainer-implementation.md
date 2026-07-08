# Desk Explainer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a grounded Desk explanation layer that turns Lance Phase 1 snapshot/scanner output into a readable moment-wise view.

**Architecture:** Create a pure service in `services/desk_explainer.py` that accepts existing JSON-safe snapshot and scanner outputs. Expose it through a new `explain_breitstein_ticker` agent tool so all frontends can request a richer single-ticker Desk view without duplicating prompt logic.

**Tech Stack:** Python dataclasses/dicts, existing `agent_tools` schema/dispatch layer, pytest.

---

### Task 1: Pure Desk Explainer

**Files:**
- Create: `tests/test_desk_explainer.py`
- Create: `services/desk_explainer.py`

**Steps:**
1. Write failing tests for a stale `last_trade` MRVL-like snapshot.
2. Verify the tests fail because `services.desk_explainer` is missing.
3. Implement `build_breitstein_ticker_explanation(snapshot, scan_output)`.
4. Verify the test passes.

### Task 2: Agent Tool Exposure

**Files:**
- Modify: `agent_tools/tools.py`
- Modify: `agent_tools/definitions.py`
- Modify: `tests/test_agent_tools.py`

**Steps:**
1. Write failing tests for `tools.explain_breitstein_ticker()`.
2. Implement the tool using `get_ticker_snapshot`, `scan_breitstein`, and the explainer service.
3. Register the tool once in `agent_tools/definitions.py`.
4. Verify focused tests pass.

### Task 3: Full Verification

**Steps:**
1. Run focused tests:
   `.venv/bin/python -m pytest tests/test_desk_explainer.py tests/test_agent_tools.py -q`
2. Run full verification:
   `scripts/verify.sh`
