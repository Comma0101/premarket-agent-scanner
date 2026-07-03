"""CLI: replay a Lance session from a scratch database copy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from app.config import get_config
from services.lance_replay_service import LanceReplayService


app = typer.Typer(add_completion=False, help="Replay Lance workflow from saved session data.")

DISCLAIMER = "Matches your filter - not buy/sell advice. Verify before acting."


@app.command()
def main(
    source_db: Path | None = typer.Option(
        None,
        "--source-db",
        help="Source SQLite DB. Defaults to configured project DB.",
    ),
    scratch_db: Path | None = typer.Option(
        None,
        "--scratch-db",
        help="Scratch SQLite DB path. Defaults to /tmp/lance_replay_<session>.sqlite.",
    ),
    scenario: str | None = typer.Option(
        None,
        "--scenario",
        help="Named replay scenario from data/lance_replay_scenarios.yaml.",
    ),
    scenarios_path: Path | None = typer.Option(
        None,
        "--scenarios-path",
        help="Replay scenarios YAML path override.",
    ),
    session_id: str | None = typer.Option(None, "--session-id", help="Lance session id."),
    target_session_date: str | None = typer.Option(
        None,
        "--target-session-date",
        help="Target date label for carryover prep.",
    ),
    outcome: list[str] = typer.Option(
        [],
        "--outcome",
        help="Synthetic replay label: TICKER:OUTCOME or TICKER:OUTCOME:PLAYBOOK.",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Evaluate scenario expected counts and exit nonzero on assertion failure.",
    ),
    limit: int = typer.Option(500, "--limit", help="Maximum rows for review/memory/carryover."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    parsed_outcomes = [_parse_outcome_spec(item) for item in outcome]
    invalid = [item for item in parsed_outcomes if item.get("error")]
    if invalid:
        typer.echo(str(invalid[0]["error"]))
        raise typer.Exit(code=2)

    payload = LanceReplayService().replay(
        source_db_path=source_db or get_config().database_path,
        scratch_db_path=scratch_db,
        scenario_name=scenario,
        scenarios_path=scenarios_path,
        session_id=session_id,
        target_session_date=target_session_date,
        outcomes=parsed_outcomes,
        limit=limit,
        check_assertions=check,
    )

    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return

    _render(payload)
    if payload.get("status") == "ERROR":
        raise typer.Exit(code=1)
    assertions = payload.get("assertions") or {}
    if check and assertions.get("status") == "FAIL":
        raise typer.Exit(code=1)


def _parse_outcome_spec(value: str) -> dict[str, Any]:
    parts = [part.strip() for part in value.split(":")]
    if len(parts) not in {2, 3} or not parts[0] or not parts[1]:
        return {"error": "outcome must look like TICKER:OUTCOME or TICKER:OUTCOME:PLAYBOOK."}
    output = {"ticker": parts[0].upper(), "outcome": parts[1].lower()}
    if len(parts) == 3 and parts[2]:
        output["playbook"] = parts[2]
    return output


def _render(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Lance Replay:")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    if payload.get("error"):
        typer.echo(f"error={payload['error']}")
        _render_disclaimer(payload)
        return

    typer.echo(f"Session: {_value(payload.get('session_id'))}")
    scenario = payload.get("scenario") or {}
    if scenario:
        typer.echo(
            f"Scenario: {_value(scenario.get('name'))} "
            f"description={_value(scenario.get('description'))}"
        )
    typer.echo(f"source_db={_value(payload.get('source_db_path'))}")
    typer.echo(f"scratch_db={_value(payload.get('scratch_db_path'))}")
    typer.echo(f"mode={_value(payload.get('mode'))} outcomes_applied={len(payload.get('outcomes_applied') or [])}")
    _render_summary("Initial Review", payload.get("initial_review_summary") or {})
    _render_review(payload.get("review") or {})
    _render_memory(payload.get("memory") or {})
    _render_carryover(payload.get("carryover") or {})
    _render_assertions(payload.get("assertions") or {})
    _render_applied(payload.get("outcomes_applied") or [])
    _render_notes(payload.get("notes") or [])
    _render_disclaimer(payload)


def _render_summary(label: str, summary: dict[str, Any]) -> None:
    typer.echo(
        f"{label}: status={_value(summary.get('status'))} "
        f"pending={_value(summary.get('pending_count'))} "
        f"reviewed={_value(summary.get('reviewed_count'))}"
    )


def _render_review(review: dict[str, Any]) -> None:
    typer.echo(
        f"Final Review: status={_value(review.get('status'))} "
        f"pending={_value(review.get('pending_count'))} "
        f"reviewed={_value(review.get('reviewed_count'))}"
    )


def _render_memory(memory: dict[str, Any]) -> None:
    typer.echo(
        f"Memory: status={_value(memory.get('status'))} "
        f"outcome_count={_value(memory.get('outcome_count'))}"
    )


def _render_carryover(carryover: dict[str, Any]) -> None:
    typer.echo(
        f"Carryover: status={_value(carryover.get('status'))} "
        f"carryover_count={_value(carryover.get('carryover_count'))} "
        f"fresh_scan_required={_value(carryover.get('fresh_scan_required'))}"
    )


def _render_assertions(assertions: dict[str, Any]) -> None:
    typer.echo(
        f"Assertions: status={_value(assertions.get('status'))} "
        f"checked={_value(assertions.get('checked_count'))} "
        f"failed={_value(assertions.get('failed_count'))}"
    )
    for check in assertions.get("checks") or []:
        typer.echo(
            f"- {_value(check.get('field'))} "
            f"expected={_value(check.get('expected'))} "
            f"actual={_value(check.get('actual'))} "
            f"status={_value(check.get('status'))}"
        )


def _render_applied(rows: list[dict[str, Any]]) -> None:
    typer.echo("")
    typer.echo("Applied Outcomes:")
    if not rows:
        typer.echo("- none")
        return
    for row in rows:
        typer.echo(
            f"- {_value(row.get('ticker'))} "
            f"outcome={_value(row.get('outcome'))} "
            f"playbook={_value(row.get('playbook'))} "
            f"status={_value(row.get('status'))}"
        )


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
    if isinstance(value, list):
        if not value:
            return "none"
        return ", ".join(str(item) for item in value)
    return str(value)


if __name__ == "__main__":
    app()
