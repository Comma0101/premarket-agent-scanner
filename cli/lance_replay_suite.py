"""CLI: run all Lance replay scenarios as a regression suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from app.config import get_config
from services.lance_replay_suite_service import LanceReplaySuiteService


app = typer.Typer(add_completion=False, help="Run every Lance replay scenario.")

DISCLAIMER = "Matches your filter - not buy/sell advice. Verify before acting."


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
    payload = LanceReplaySuiteService().run(
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
    typer.echo("Lance Replay Suite:")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    if payload.get("error"):
        typer.echo(f"error={payload['error']}")
        _render_disclaimer(payload)
        return
    typer.echo(f"source_db={_value(payload.get('source_db_path'))}")
    typer.echo(f"scenarios_path={_value(payload.get('scenarios_path'))}")
    typer.echo(f"scratch_dir={_value(payload.get('scratch_dir'))}")
    typer.echo(
        f"scenario_count={_value(payload.get('scenario_count'))} "
        f"passed={_value(payload.get('passed_count'))} "
        f"failed={_value(payload.get('failed_count'))}"
    )
    typer.echo("")
    typer.echo("Scenario Results:")
    for row in payload.get("results") or []:
        typer.echo(
            f"- {_value(row.get('scenario_name'))} "
            f"assertion_status={_value(row.get('assertion_status'))} "
            f"checked={_value(row.get('checked_count'))} "
            f"failed={_value(row.get('failed_count'))} "
            f"memory={_value(row.get('memory_outcome_count'))} "
            f"carryover={_value(row.get('carryover_count'))}"
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
