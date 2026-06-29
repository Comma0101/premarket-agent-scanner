from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


AgentRunStatus = Literal["OK", "ERROR"]
WatchBucket = Literal["primary_watch", "secondary_watch", "context_watch"]


@dataclass
class AgentToolCall:
    name: str
    tool_input: dict[str, Any]
    result_summary: str


@dataclass
class AgentWatchCandidate:
    ticker: str
    bucket: WatchBucket
    grade: str
    score: int | None
    gap_pct: float | None
    gap_dollar: float | None
    volume: float | None
    rel_volume: float | None
    market_cap: float | None
    confidence: str | None
    evidence_summary: str
    name: str | None = None
    matched_signals: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    gap_basis: str | None = None


@dataclass
class AgentRunPacket:
    agent_name: str
    strategy: str
    status: AgentRunStatus
    tool_calls: list[AgentToolCall]
    watchlist: dict[WatchBucket, list[AgentWatchCandidate]]
    guardrails: list[str]
    warnings: list[str]
    notes: list[str] = field(default_factory=list)
    handoff_prompt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
