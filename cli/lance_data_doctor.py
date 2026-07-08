"""CLI: diagnose Lance live-data readiness blockers."""

from __future__ import annotations

import json
from typing import Any

import typer

from agent_tools.tools import run_lance_data_doctor


app = typer.Typer(add_completion=False, help="Diagnose Lance data readiness.")


@app.command()
def main(
    tickers: str = typer.Option(..., "--tickers", "-t", help="Tickers, comma-separated."),
    max_candidates: int = typer.Option(5, "--max-candidates", help="Maximum Lance rows."),
    persist: bool = typer.Option(False, "--persist", help="Persist the validation Lance cycle."),
    summary_limit: int | None = typer.Option(None, "--summary-limit", help="Rows per summary section."),
    review_limit: int = typer.Option(10, "--review-limit", help="Review row limit."),
    max_workers: int = typer.Option(1, "--max-workers", help="Snapshot worker count."),
    now: str | None = typer.Option(None, "--now", help="Optional ISO timestamp override."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    payload = run_lance_data_doctor(
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
    typer.echo("Lance Data Doctor")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    doctor_read = payload.get("doctor_read") if isinstance(payload.get("doctor_read"), dict) else {}
    if doctor_read.get("one_liner"):
        typer.echo(_value(doctor_read.get("one_liner")))

    root_causes = payload.get("root_causes") if isinstance(payload.get("root_causes"), dict) else {}
    typer.echo("")
    typer.echo("Root Causes")
    printed = False
    for key in [
        "ready",
        "provider_failure",
        "missing_price",
        "stale_or_off_session",
        "halted",
        "confidence",
        "unknown",
    ]:
        values = root_causes.get(key) if isinstance(root_causes.get(key), list) else []
        if values:
            printed = True
            typer.echo(f"{key}: {_join(values)}")
    if not printed:
        typer.echo("- none")

    actions = payload.get("next_actions") if isinstance(payload.get("next_actions"), list) else []
    typer.echo("")
    typer.echo("Next Actions")
    if not actions:
        typer.echo("- none")
    for action in actions:
        typer.echo(f"- {_value(action)}")

    disclaimer = str(payload.get("disclaimer") or "")
    if disclaimer:
        typer.echo("")
        typer.echo(disclaimer)


def _join(values: list[Any]) -> str:
    return ", ".join(_value(value) for value in values)


def _value(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    return str(value)


if __name__ == "__main__":
    app()
