"""CLI: explain one ticker from the latest Lance command-center payload."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from services.lance_ticker_explain_service import (
    DEFAULT_LANCE_PAYLOAD_PATH,
    LanceTickerExplainService,
)


app = typer.Typer(add_completion=False, help="Explain a ticker from Lance's saved evidence.")


@app.command()
def main(
    ticker: str = typer.Argument(..., help="Ticker to explain."),
    payload: Path = typer.Option(
        DEFAULT_LANCE_PAYLOAD_PATH,
        "--payload",
        help="Path to latest_command_center.json.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    output = LanceTickerExplainService().explain(ticker=ticker, payload_path=payload)
    if json_output:
        typer.echo(json.dumps(output, indent=2))
        return
    _render(output)


def _render(output: dict[str, Any]) -> None:
    _section("Lance Ticker Explain")
    typer.echo(f"ticker={_value(output.get('ticker'))}")
    typer.echo(f"status={_value(output.get('status'))}")
    if output.get("session_banner"):
        typer.echo(_value(output.get("session_banner")))
    if output.get("summary"):
        typer.echo(_value(output.get("summary")))

    if output.get("status") == "FOUND":
        _render_data_quality(output)
        _render_detail("Intraday", output.get("intraday"))
        _render_detail("Swing", output.get("swing"))
        _render_benchmarks(output)
    elif output.get("status") == "OMITTED":
        omitted = output.get("omitted_reason") if isinstance(output.get("omitted_reason"), dict) else {}
        typer.echo(f"stage={_value(omitted.get('stage'))}")
        typer.echo(f"reason={_value(omitted.get('reason'))}")
    elif output.get("error"):
        typer.echo(f"error={_value(output.get('error'))}")

    if output.get("source_paths"):
        typer.echo(f"source_paths={_join(output.get('source_paths'))}")
    disclaimer = str(output.get("disclaimer") or "")
    if disclaimer:
        typer.echo("")
        typer.echo(disclaimer)


def _render_data_quality(output: dict[str, Any]) -> None:
    data = output.get("data_quality") if isinstance(output.get("data_quality"), dict) else {}
    _section("Data Quality")
    typer.echo(
        " ".join([
            f"price={_format_price(data.get('latest_price'))}",
            f"gap={_format_pct(data.get('gap_pct'))}",
            f"rvol={_format_multiple(data.get('rel_volume'))}",
            f"gap_basis={_value(data.get('gap_basis'))}",
            f"confidence={_value(data.get('confidence'))}",
            f"status={_value(data.get('data_status'))}",
            f"as_of={_value(data.get('as_of_et') or data.get('as_of'))}",
            f"sources={_join(data.get('sources'))}",
        ])
    )
    if data.get("data_caveat"):
        typer.echo(f"caveat={_value(data.get('data_caveat'))}")


def _render_detail(title: str, value: Any) -> None:
    if not isinstance(value, dict) or not value:
        return
    _section(title)
    typer.echo(f"state={_value(value.get('state'))}")
    typer.echo(f"playbook={_value(value.get('playbook'))}")
    if value.get("thesis"):
        typer.echo(f"thesis={_value(value.get('thesis'))}")
    typer.echo(f"waiting_for={_join(value.get('waiting_for'))}")
    typer.echo(f"invalidates_if={_join(value.get('invalidates_if'))}")


def _render_benchmarks(output: dict[str, Any]) -> None:
    rows = output.get("benchmark_context") if isinstance(output.get("benchmark_context"), list) else []
    if not rows:
        return
    _section("Benchmarks")
    for row in rows[:5]:
        if not isinstance(row, dict):
            continue
        typer.echo(
            " ".join([
                f"{_value(row.get('ticker'))}:",
                f"gap={_format_pct(row.get('gap_pct'))}",
                f"basis={_value(row.get('gap_basis'))}",
                f"confidence={_value(row.get('confidence'))}",
                f"as_of={_value(row.get('as_of'))}",
                f"sources={_join(row.get('sources'))}",
            ])
        )


def _section(title: str) -> None:
    typer.echo("")
    typer.echo(title)


def _join(values: Any) -> str:
    if not isinstance(values, list) or not values:
        return "none"
    return ", ".join(_value(value) for value in values)


def _format_pct(value: Any) -> str:
    if not isinstance(value, int | float):
        return "unknown"
    return f"{float(value):.2f}%"


def _format_price(value: Any) -> str:
    if not isinstance(value, int | float):
        return "unknown"
    return f"{float(value):.2f}"


def _format_multiple(value: Any) -> str:
    if not isinstance(value, int | float):
        return "unknown"
    return f"{float(value):.2f}x"


def _value(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


if __name__ == "__main__":
    app()
