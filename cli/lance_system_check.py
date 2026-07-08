"""CLI: run the Lance replay suite plus source DB safety checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from app.config import get_config
from services.lance_market_scan_service import DISCLAIMER
from services.lance_system_check_service import LanceSystemCheckService


app = typer.Typer(add_completion=False, help="Run Lance replay and source-DB safety checks.")


@app.command()
def main(
    source_db: Path | None = typer.Option(
        None,
        "--source-db",
        help="Source SQLite DB. Defaults to configured project DB.",
    ),
    scenarios_path: Path | None = typer.Option(
        None,
        "--scenarios-path",
        help="Replay scenarios YAML path. Defaults to data/lance_replay_scenarios.yaml.",
    ),
    scratch_dir: Path | None = typer.Option(
        None,
        "--scratch-dir",
        help="Directory for scratch scenario DB copies.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    payload = LanceSystemCheckService().run(
        source_db_path=source_db or get_config().database_path,
        scenarios_path=scenarios_path,
        scratch_dir=scratch_dir,
    )

    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        if payload.get("status") in {"ERROR", "FAIL"}:
            raise typer.Exit(code=1)
        return

    _render(payload)
    if payload.get("status") in {"ERROR", "FAIL"}:
        raise typer.Exit(code=1)


def _render(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Lance System Check:")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    if payload.get("error"):
        typer.echo(f"error={payload['error']}")
        _render_disclaimer(payload)
        return
    typer.echo(f"source_db={_value(payload.get('source_db_path'))}")
    typer.echo(f"scenarios_path={_value(payload.get('scenarios_path'))}")
    typer.echo(f"scratch_dir={_value(payload.get('scratch_dir'))}")
    summary = payload.get("summary") or {}
    typer.echo(
        "Suite: "
        f"status={_value(summary.get('suite_status'))} "
        f"scenarios={_value(summary.get('suite_scenarios'))} "
        f"passed={_value(summary.get('suite_passed'))} "
        f"failed={_value(summary.get('suite_failed'))}"
    )
    typer.echo(
        "Safety: "
        f"status={_value((payload.get('safety_checks') or {}).get('status'))} "
        f"source_outcomes_before={_value(summary.get('source_outcomes_before'))} "
        f"source_outcomes_after={_value(summary.get('source_outcomes_after'))}"
    )
    _render_notes(payload.get("notes") or [])
    _render_disclaimer(payload)


def _render_notes(notes: list[str]) -> None:
    typer.echo("")
    typer.echo("Notes:")
    if not notes:
        typer.echo("- none")
        return
    for note in notes:
        typer.echo(f"- {note}")


def _render_disclaimer(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Disclaimer:")
    typer.echo(str(payload.get("disclaimer") or DISCLAIMER))


def _value(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    return str(value)


if __name__ == "__main__":
    app()
