"""CLI: run deterministic scanner-backed agent workflows."""

from __future__ import annotations

import json

import typer

from agent_orchestrator.models import AgentRunPacket, AgentWatchCandidate
from agent_orchestrator.trading_agent import TradingAgentOrchestrator

app = typer.Typer(add_completion=False, help="Run scanner-backed agent workflows.")


@app.command()
def main(
    tickers: str = typer.Option(None, "--tickers", "-t", help="Ad-hoc tickers, comma-separated."),
    universe: str = typer.Option(None, "--universe", "-u", help="Universe name(s)."),
    watchlist: str = typer.Option(None, "--watchlist", "-w", help="Watchlist name(s)."),
    all_universes: bool = typer.Option(False, "--all", help="Scan every defined universe."),
    preset_name: str = typer.Option(
        "sykes_small_cap_v0",
        "--preset",
        help="Small-cap scanner preset name.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print the agent packet as JSON."),
) -> None:
    if not any([tickers, universe, watchlist, all_universes]):
        raise typer.BadParameter(
            "Pick a selection: --tickers, --universe, --watchlist, or --all."
        )

    packet = TradingAgentOrchestrator().run_sykes_small_cap_watchlist(
        preset_name=preset_name,
        tickers=tickers,
        universe=universe,
        watchlist=watchlist,
        all_universes=all_universes,
        user_query="run sykes-style small-cap watchlist agent",
    )

    if json_output:
        typer.echo(json.dumps(packet.to_dict(), indent=2))
    else:
        _render_plain(packet)

    if packet.status == "ERROR":
        raise typer.Exit(1)


def _render_plain(packet: AgentRunPacket) -> None:
    typer.echo(f"Agent: {packet.agent_name}")
    typer.echo(f"Strategy: {packet.strategy}")
    typer.echo(f"Status: {packet.status}")
    typer.echo("")

    _render_bucket("Primary Watch", packet.watchlist["primary_watch"])
    _render_bucket("Secondary Watch", packet.watchlist["secondary_watch"])
    _render_bucket("Context Watch", packet.watchlist["context_watch"])

    if packet.warnings:
        typer.echo("Warnings:")
        for warning in packet.warnings:
            typer.echo(f"- {warning}")

    if packet.notes:
        typer.echo("Notes:")
        for note in packet.notes:
            typer.echo(f"- {note}")


def _render_bucket(title: str, candidates: list[AgentWatchCandidate]) -> None:
    typer.echo(f"{title}:")
    if not candidates:
        typer.echo("- none")
        return

    for candidate in candidates:
        gap = _fmt(candidate.gap_pct, suffix="%")
        rvol = _fmt(candidate.rel_volume, suffix="x")
        typer.echo(
            f"- {candidate.ticker} {candidate.grade} score={candidate.score} "
            f"gap={gap} rvol={rvol} evidence={candidate.evidence_summary}"
        )


def _fmt(value: float | None, *, suffix: str = "") -> str:
    if value is None:
        return "-"
    return f"{value:.2f}{suffix}"


if __name__ == "__main__":
    app()
