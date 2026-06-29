# Agent Orchestrator Design

## Goal

Add a small deterministic orchestration layer that lets Codex, Claude, opencode,
or any other driver consume the scanner as an agent-ready workflow.

## Recommended Approach

Use a local Python orchestrator that calls the existing `agent_tools` dispatcher,
packages grounded scanner results, and emits a strict handoff packet for an LLM
agent. Do not add a model SDK yet. The driving agent can read the packet and
decide how to communicate with the user, while every market number still comes
from the data layer.

Alternatives considered:

- Add direct OpenAI/Anthropic clients now. This couples model credentials and
  prompting to the scanner before the data contract is stable.
- Add a multi-agent framework. That is too much surface area for the current
  repo and would make testing harder.

## Architecture

Create an `agent_orchestrator` package with a `TradingAgentOrchestrator` service.
The service selects a tool, calls `agent_tools.definitions.dispatch`, and
converts the JSON output into an `AgentRunPacket`. The packet includes the
agent identity, tool calls, evidence-grounded candidate summaries, guardrails,
missing-data warnings, and next-step questions for a human or external agent.

The first strategy is `sykes_small_cap_watchlist`. It is a scanner/watching
workflow only, not execution advice.

## Data Flow

1. Caller asks for a Sykes-style small-cap watchlist run.
2. Orchestrator calls `scan_small_caps` through the dispatcher.
3. Dispatcher logs the tool call and returns JSON-safe scanner output.
4. Orchestrator classifies candidates by grade and evidence completeness.
5. CLI or external agent reads the packet and presents bounded analysis.

## Guardrails

- Never invent prices, floats, market caps, gaps, volume, filings, or catalysts.
- Never output buy/sell/short recommendations.
- Surface unsupported fields such as short interest or borrow cost as unknown.
- Treat missing evidence as a blocker for stronger conclusions.

## Testing

Tests should run fully offline with fake dispatcher output. Coverage should
prove tool-call selection, packet structure, candidate bucketing, guardrails,
error handling, and CLI rendering.
