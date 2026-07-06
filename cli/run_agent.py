"""CLI: run deterministic scanner-backed agent workflows."""

from __future__ import annotations

import contextlib
import io
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
    market: str = typer.Option(None, "--market", help="Whole-market source, e.g. us-listed."),
    market_limit: int = typer.Option(
        None,
        "--market-limit",
        help="Limit market symbols for smoke tests.",
    ),
    max_workers: int | None = typer.Option(
        None,
        "--max-workers",
        help="Bounded worker count for broad market scans.",
    ),
    include_rejected: bool = typer.Option(
        False,
        "--include-rejected",
        help="Include rejected candidates (score=0, grade=REJECT) in the watchlist packet.",
    ),
    live_intraday: bool = typer.Option(
        False,
        "--live-intraday",
        help="Opt-in regular-session discovery mode for small/spec movers that need enrichment.",
    ),
    all_universes: bool = typer.Option(False, "--all", help="Scan every defined universe."),
    preset_name: str = typer.Option(
        "sykes_small_cap_v0",
        "--preset",
        help="Small-cap scanner preset name.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print the agent packet as JSON."),
) -> None:
    if not any([tickers, universe, watchlist, market, all_universes]):
        raise typer.BadParameter(
            "Pick a selection: --tickers, --universe, --watchlist, --market, or --all."
        )

    kwargs = {
        "preset_name": preset_name,
        "tickers": tickers,
        "universe": universe,
        "watchlist": watchlist,
        "market": market,
        "market_limit": market_limit,
        "max_workers": max_workers,
        "all_universes": all_universes,
        "include_rejected": include_rejected,
        "live_intraday": live_intraday,
        "user_query": "run sykes-style small-cap watchlist agent",
    }
    packet = _run_agent_packet(json_output=json_output, **kwargs)

    if json_output:
        typer.echo(json.dumps(packet.to_dict(), indent=2))
    else:
        _render_plain(packet)

    if packet.status == "ERROR":
        raise typer.Exit(1)


def _run_agent_packet(*, json_output: bool, **kwargs) -> AgentRunPacket:
    orchestrator = TradingAgentOrchestrator()
    if not json_output:
        return orchestrator.run_sykes_small_cap_watchlist(**kwargs)

    captured_stdout = io.StringIO()
    captured_stderr = io.StringIO()
    with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
        packet = orchestrator.run_sykes_small_cap_watchlist(**kwargs)

    note = _provider_console_output_note(captured_stdout.getvalue(), captured_stderr.getvalue())
    if note:
        packet.notes.append(note)
    return packet


def _provider_console_output_note(stdout: str, stderr: str) -> str | None:
    clean = " ".join(f"{stdout}\n{stderr}".split())
    if not clean:
        return None
    if len(clean) > 500:
        clean = f"{clean[:497]}..."
    return f"Suppressed provider console output during JSON run: {clean}"


def _render_plain(packet: AgentRunPacket) -> None:
    typer.echo(f"Agent: {packet.agent_name}")
    typer.echo(f"Strategy: {packet.strategy}")
    typer.echo(f"Status: {packet.status}")
    if packet.session_banner:
        typer.echo(f"Session: {packet.session_banner}")
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
        time_label = candidate.as_of_et or "-"
        typer.echo(
            f"- {candidate.ticker} {candidate.grade} score={candidate.score} "
            f"gap={gap} rvol={rvol} as_of={time_label} evidence={candidate.evidence_summary}"
        )
        if candidate.data_caveat:
            typer.echo(f"    caveat: {candidate.data_caveat}")


def _fmt(value: float | None, *, suffix: str = "") -> str:
    if value is None:
        return "-"
    return f"{value:.2f}{suffix}"


if __name__ == "__main__":
    app()
