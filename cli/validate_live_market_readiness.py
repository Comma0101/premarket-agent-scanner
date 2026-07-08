"""CLI: validate live market data readiness for Lance."""

from __future__ import annotations

import json
from typing import Any

import typer

from agent_tools.tools import validate_live_market_readiness


app = typer.Typer(add_completion=False, help="Validate live market readiness.")

DISCLAIMER = "Matches your filter - not buy/sell advice. Verify before acting."


@app.command()
def main(
    tickers: str = typer.Option(..., "--tickers", "-t", help="Tickers, comma-separated."),
    max_candidates: int = typer.Option(5, "--max-candidates", help="Maximum Lance rows."),
    persist: bool = typer.Option(False, "--persist", help="Persist the Lance desk cycle."),
    summary_limit: int = typer.Option(5, "--summary-limit", help="Rows per Lance section."),
    review_limit: int = typer.Option(10, "--review-limit", help="Lance review row limit."),
    max_workers: int = typer.Option(1, "--max-workers", help="Snapshot worker count."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    payload = validate_live_market_readiness(
        tickers=tickers,
        max_candidates=max_candidates,
        persist=persist,
        summary_limit=summary_limit,
        review_limit=review_limit,
        max_workers=max_workers,
        now=now,
    )
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render(payload)


def _render(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Live Market Readiness:")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    typer.echo(
        f"Session: {_value(payload.get('session_mode'))}, "
        f"{_value(payload.get('session_time_et'))}"
    )
    typer.echo(
        "Counts: "
        f"tickers={_value(payload.get('ticker_count'))} "
        f"ready={_value(payload.get('ready_count'))} "
        f"blocked={_value(payload.get('blocked_count'))}"
    )
    _render_snapshots(payload.get("snapshot_checks") or [])
    _render_lance(payload.get("lance_cycle") or {})
    _render_notes(payload.get("notes") or [])
    typer.echo("")
    typer.echo("Disclaimer:")
    typer.echo(str(payload.get("disclaimer") or DISCLAIMER))


def _render_snapshots(rows: list[dict[str, Any]]) -> None:
    typer.echo("")
    typer.echo("Snapshot Checks:")
    if not rows:
        typer.echo("- none")
        return
    for row in rows:
        bits = [
            f"readiness={_value(row.get('readiness'))}",
            f"gap_pct={_fmt_percent(row.get('gap_pct'))}",
            f"source={_value(row.get('sources'))}",
            f"as_of={_value(row.get('as_of_et'))}",
            f"gap_basis={_value(row.get('gap_basis'))}",
            f"confidence={_value(row.get('confidence'))}",
            f"data_status={_value(row.get('data_status'))}",
        ]
        halt_status = row.get("halt_status") or {}
        if halt_status:
            bits.append(f"halt_status={_value(halt_status.get('status'))}")
        blockers = row.get("blockers") or []
        if blockers:
            bits.append(f"blockers={_value(blockers)}")
        failures = row.get("provider_failures") or {}
        if failures:
            bits.append(f"provider_failures={_value(failures)}")
        typer.echo(f"- {_value(row.get('ticker'))} {' '.join(bits)}")


def _render_lance(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Lance Cycle:")
    if not payload:
        typer.echo("- none")
        return
    summary = payload.get("scan_summary") or {}
    typer.echo(
        f"status={_value(payload.get('status'))} "
        f"session_id={_value(payload.get('session_id'))} "
        f"candidate_count={_value(summary.get('candidate_count'))}"
    )


def _render_notes(notes: list[str]) -> None:
    typer.echo("")
    typer.echo("Notes:")
    if not notes:
        typer.echo("- none")
        return
    for note in notes:
        typer.echo(f"- {note}")


def _fmt_percent(value: Any) -> str:
    clean = _value(value)
    if clean == "unknown" or clean.endswith("%"):
        return clean
    return f"{clean}%"


def _value(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, list):
        if not value:
            return "unknown"
        return ", ".join(_value(item) for item in value)
    if isinstance(value, dict):
        if not value:
            return "unknown"
        return json.dumps(value, sort_keys=True)
    return str(value)


if __name__ == "__main__":
    app()
