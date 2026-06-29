# Agent Orchestrator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a minimal local agent orchestration layer for the Sykes-style small-cap scanner.

**Architecture:** Add an `agent_orchestrator` package that calls existing JSON tools and returns deterministic agent handoff packets. Add a small CLI wrapper for manual testing. Keep model APIs out of scope.

**Tech Stack:** Python dataclasses, existing `agent_tools` dispatcher, Typer CLI, pytest.

---

### Task 1: Add Agent Packet Models

**Files:**
- Modify: `app/models.py`
- Test: `tests/test_agent_orchestrator.py`

**Step 1: Write failing tests**

Add tests that instantiate the orchestrator and expect a packet with `agent_name`,
`strategy`, `tool_calls`, `watchlist`, `guardrails`, and `warnings`.

**Step 2: Verify red**

Run:

```bash
/home/comma/Documents/premarket-agent-scanner/.venv/bin/python -m pytest tests/test_agent_orchestrator.py -q
```

Expected: import failure for missing `agent_orchestrator`.

**Step 3: Implement models**

Add dataclasses for agent tool calls, watchlist candidates, and the final run
packet.

**Step 4: Verify green**

Run the targeted test again.

### Task 2: Add Trading Agent Orchestrator

**Files:**
- Create: `agent_orchestrator/__init__.py`
- Create: `agent_orchestrator/trading_agent.py`
- Test: `tests/test_agent_orchestrator.py`

**Step 1: Write failing behavior tests**

Cover:

- `sykes_small_cap_watchlist` calls `scan_small_caps`.
- A-watch/B-watch/C-watch candidates are bucketed.
- Missing evidence becomes packet warnings.
- Tool errors become packet status `ERROR`.

**Step 2: Verify red**

Run the targeted orchestrator tests.

**Step 3: Implement service**

Use a dispatcher injection point for tests and default to
`agent_tools.definitions.dispatch` in production.

**Step 4: Verify green**

Run the targeted tests.

### Task 3: Expose CLI

**Files:**
- Create: `cli/run_agent.py`
- Modify: `pyproject.toml`
- Test: `tests/test_agent_orchestrator.py`

**Step 1: Write failing CLI test**

Use `CliRunner` with a fake orchestrator to ensure the command renders a packet.

**Step 2: Verify red**

Run the targeted test.

**Step 3: Implement CLI**

Add a Typer command with `--tickers`, `--universe`, `--watchlist`, `--all`, and
`--json` options.

**Step 4: Verify green**

Run the targeted tests.

### Task 4: Document and Verify

**Files:**
- Modify: `README.md`

**Steps:**

1. Document the orchestrator contract and CLI.
2. Run the full pytest suite.
3. Run ruff.
4. Run `git diff --check`.
5. Commit the implementation.
