---
name: premarket-scanner
description: Work safely on this premarket scanner repo. Use when changing scanner services, providers, agent tools, MCP exposure, orchestrator packets, CLI scanner commands, or tests for market-data behavior.
---

# Premarket Scanner

## Workflow

1. Read `AGENTS.md` first and preserve the prime directive: never invent market numbers.
2. Keep dependencies layered: providers -> services -> agent_tools -> mcp_server/agent_orchestrator -> cli.
3. Add new agent-callable tools only in `agent_tools/definitions.py`; `mcp_server` reflects that schema.
4. Use injected fake providers in tests. Tests must not hit live network services.
5. Prefer small commits with `Co-Authored-By: Codex <codex@openai.com>`.

## Verification

Run the narrowest relevant tests first, then finish with:

```bash
scripts/verify.sh
```

If `scripts/verify.sh` is unavailable, run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
git diff --check
```

