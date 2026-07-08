"""CLI: run the Lance intraday desk cycle."""

from __future__ import annotations

import json
import time
from typing import Any

import typer

from agent_tools.tools import run_lance_desk_cycle

app = typer.Typer(add_completion=False, help="Run the Lance intraday desk cycle.")

DISCLAIMER = "Matches your filter - not buy/sell advice. Verify before acting."


@app.command()
def main(
    tickers: str = typer.Option(None, "--tickers", "-t", help="Ad-hoc tickers, comma-separated."),
    universe: str = typer.Option(None, "--universe", "-u", help="Universe name(s), comma-separated."),
    watchlist: str = typer.Option(None, "--watchlist", "-w", help="Watchlist name(s)."),
    all_universes: bool = typer.Option(
        False,
        "--all-universes",
        "--all",
        help="Scan every defined universe.",
    ),
    market: str = typer.Option(None, "--market", help="Full-market source, e.g. us-listed."),
    market_limit: int = typer.Option(
        None,
        "--market-limit",
        help="Optional cap on market symbols for bounded testing.",
    ),
    min_gap_abs: float = typer.Option(3.0, "--min-gap-abs", help="Minimum absolute gap %."),
    max_candidates: int = typer.Option(20, "--max-candidates", help="Maximum candidates to scan."),
    persist: bool = typer.Option(False, "--persist", help="Persist scan/update state."),
    session_id: str = typer.Option(None, "--session-id", help="Reuse or label a session id."),
    max_workers: int = typer.Option(1, "--max-workers", help="Bounded worker count."),
    include_caveated_context: bool = typer.Option(
        False,
        "--include-caveated-context",
        help="Allow stale/conflict/low-confidence names as blocked context rows.",
    ),
    update_limit: int = typer.Option(50, "--update-limit", help="Maximum tracked rows to update."),
    review_limit: int = typer.Option(500, "--review-limit", help="Maximum rows for review steps."),
    target_session_date: str = typer.Option(
        None,
        "--target-session-date",
        help="Target date for carryover prep.",
    ),
    summary_limit: int = typer.Option(5, "--summary-limit", help="Rows per summary section."),
    watch: float | None = typer.Option(
        None,
        "--watch",
        min=0.0,
        help="Re-run the Lance desk cycle every N seconds and print changes.",
    ),
    watch_iterations: int | None = typer.Option(
        None,
        "--watch-iterations",
        min=1,
        hidden=True,
        help="Bounded watch iterations for tests/smoke runs.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print the raw payload as JSON."),
) -> None:
    if not any([tickers, universe, watchlist, all_universes, market]):
        all_universes = True
    if (all_universes or market) and not any([tickers, universe, watchlist]):
        include_caveated_context = True

    if watch is not None and json_output:
        typer.echo("--json cannot be combined with --watch")
        raise typer.Exit(code=2)

    run_kwargs = {
        "tickers": tickers,
        "universe": universe,
        "watchlist": watchlist,
        "all_universes": all_universes,
        "market": market,
        "market_limit": market_limit,
        "min_gap_abs": min_gap_abs,
        "max_candidates": max_candidates,
        "persist": persist,
        "session_id": session_id,
        "max_workers": max_workers,
        "include_caveated_context": include_caveated_context,
        "update_limit": update_limit,
        "review_limit": review_limit,
        "target_session_date": target_session_date,
        "summary_limit": summary_limit,
    }

    if watch is not None:
        _run_watch(
            run_kwargs=run_kwargs,
            interval_seconds=watch,
            watch_iterations=watch_iterations,
        )
        return

    payload = run_lance_desk_cycle(
        **run_kwargs,
    )

    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return

    _render_readable(payload)


def _run_watch(
    *,
    run_kwargs: dict[str, Any],
    interval_seconds: float,
    watch_iterations: int | None,
) -> None:
    typer.echo(f"Watch Mode: every {interval_seconds:g} seconds")
    iteration = 0
    try:
        while watch_iterations is None or iteration < watch_iterations:
            iteration += 1
            payload = run_lance_desk_cycle(**run_kwargs)
            _section(f"Watch Cycle {iteration}")
            if iteration == 1:
                _render_readable(payload)
            else:
                _render_watch_changes(payload)
            if watch_iterations is not None and iteration >= watch_iterations:
                break
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        typer.echo("")
        typer.echo("Watch stopped.")


def _render_readable(payload: dict[str, Any]) -> None:
    _render_session(payload)
    _render_market_context(payload.get("market_context") or {})
    _render_watchlist(payload.get("top_watchlist") or [])
    _render_updates(payload.get("top_updates") or [])
    _render_pending_reviews(payload.get("pending_reviews") or [])
    _render_unified_carryover(payload.get("unified_carryover") or {})
    _render_carryover(payload.get("carryover_groups") or {}, payload.get("carryover_summary") or {})
    _render_disclaimer(str(payload.get("disclaimer") or DISCLAIMER))


def _render_watch_changes(payload: dict[str, Any]) -> None:
    _section("Lance Watch Changes")
    updates = payload.get("top_updates") or []
    if not updates:
        typer.echo("- none")
    for row in updates:
        typer.echo(_watch_update_line(row))
    _render_disclaimer(str(payload.get("disclaimer") or DISCLAIMER))


def _watch_update_line(row: dict[str, Any]) -> str:
    parts = [
        f"- {_value(row.get('ticker'))}",
        f"previous_state={_value(row.get('previous_state'))}",
        f"current_state={_value(row.get('current_state'))}",
        f"state_changed={_value(row.get('state_changed'))}",
        f"score_delta={_value(row.get('score_delta'))}",
        f"gap_pct_delta={_value(row.get('gap_pct_delta'))}",
        f"rel_volume_delta={_value(row.get('rel_volume_delta'))}",
        f"flags={_value(row.get('change_flags'))}",
        f"as_of={_value(_row_value(row, 'as_of_et', 'as_of'))}",
        f"gap_basis={_value(_row_value(row, 'gap_basis'))}",
        f"confidence={_value(_row_value(row, 'confidence'))}",
        f"data_status={_value(_row_value(row, 'data_status'))}",
    ]
    provider_failures = _row_value(row, "provider_failures")
    if provider_failures:
        parts.append(f"provider_failures={_value(provider_failures)}")
    halt_status = _row_value(row, "halt_status")
    if isinstance(halt_status, dict) and halt_status:
        parts.append(f"halt_status={_value(halt_status.get('status'))}")
    return " ".join(parts)


def _render_session(payload: dict[str, Any]) -> None:
    _section("Session and Status")
    typer.echo(f"Agent: {_value(payload.get('agent_name'))}")
    typer.echo(f"Mode: {_value(payload.get('mode'))}")
    typer.echo(f"Strategy: {_value(payload.get('strategy'))}")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    typer.echo(f"Session: {_value(payload.get('session_id'))}")
    _render_summary("Scan", payload.get("scan_summary") or {})
    _render_summary("Unified", payload.get("unified_summary") or {})
    _render_summary("Updates", payload.get("updates_summary") or {})
    _render_summary("Review", payload.get("review_summary") or {})
    _render_summary("Carryover", payload.get("carryover_summary") or {})


def _render_summary(label: str, summary: dict[str, Any]) -> None:
    if not summary:
        typer.echo(f"{label}: unknown")
        return
    fields = " ".join(f"{key}={_value(value)}" for key, value in summary.items())
    typer.echo(f"{label}: {fields}")


def _render_market_context(context: dict[str, Any]) -> None:
    _section("Market Context / Theme Rotation")
    themes = context.get("theme_rotation") or []
    if not themes:
        typer.echo("- none")
        return
    for theme in themes:
        if isinstance(theme, dict):
            tickers = theme.get("tickers")
            ticker_text = ",".join(tickers) if isinstance(tickers, list) else _value(tickers)
            typer.echo(
                f"- theme={_value(theme.get('theme'))} tickers={ticker_text} "
                f"evidence={_value(theme.get('evidence'))}"
            )
        else:
            typer.echo(f"- {_value(theme)}")


def _render_watchlist(rows: list[dict[str, Any]]) -> None:
    _section("Top Lance Watchlist Rows")
    if not rows:
        typer.echo("- none")
        return

    for row in rows:
        ticker = _value(row.get("ticker"))
        state = _value(row.get("state") or row.get("bucket") or row.get("label"))
        score = _value(row.get("score"))
        market_bits = _market_bits(row)
        policy_bits = _policy_bits(row)
        line = f"- {ticker} state={state} score={score} {market_bits}"
        if policy_bits:
            line = f"{line} {policy_bits}"
        typer.echo(line)
        if row.get("state_reason"):
            typer.echo(f"  reason={_value(row.get('state_reason'))}")
        if row.get("thesis"):
            typer.echo(f"  thesis={_value(row.get('thesis'))}")
        if row.get("waiting_for"):
            typer.echo(f"  waiting_for={_value(row.get('waiting_for'))}")
        if row.get("invalidates_if"):
            typer.echo(f"  invalidates_if={_value(row.get('invalidates_if'))}")
        if row.get("manual_review_questions"):
            typer.echo(f"  manual_review={_value(row.get('manual_review_questions'))}")
        if row.get("conflict_flags"):
            typer.echo(f"  conflict_flags={_value(row.get('conflict_flags'))}")
        evidence = row.get("evidence") or row.get("evidence_summary")
        if evidence:
            typer.echo(f"  evidence={_value(evidence)}")


def _market_bits(row: dict[str, Any]) -> str:
    parts: list[str] = []
    gap_pct = _row_value(row, "gap_pct", "gap_percent")
    if gap_pct is not None:
        parts.append(f"gap_pct={_fmt_percent(gap_pct)}")
    parts.extend(_provenance_bits(row))
    gap_dollar = _row_value(row, "gap_dollar")
    if gap_dollar is not None:
        parts.append(f"gap_dollar={_value(gap_dollar)}")
    price = _row_value(row, "price", "latest_price")
    if price is not None:
        parts.append(f"price={_value(price)}")
    volume = _row_value(row, "volume")
    if volume is not None:
        parts.append(f"volume={_value(volume)}")
    rvol = _row_value(row, "rvol", "rel_volume")
    if rvol is not None:
        parts.append(f"rvol={_value(rvol)}")
    provider_failures = _row_value(row, "provider_failures")
    if provider_failures:
        parts.append(f"provider_failures={_value(provider_failures)}")
    return " ".join(parts)


def _policy_bits(row: dict[str, Any]) -> str:
    parts = []
    grade = row.get("lance_quality_grade")
    if grade:
        parts.append(f"grade={_value(grade)}")
    front_side = row.get("front_side_status")
    if front_side:
        parts.append(f"front_side={_value(front_side)}")
    action = row.get("action_mode")
    if action:
        parts.append(f"action={_value(action)}")
    alignment = row.get("alignment")
    if alignment:
        parts.append(f"alignment={_value(alignment)}")
    primary = row.get("primary_timeframe")
    if primary:
        parts.append(f"primary={_value(primary)}")
    swing_state = row.get("swing_state")
    if swing_state:
        parts.append(f"swing={_value(swing_state)}")
    intraday_state = row.get("intraday_state")
    if intraday_state:
        parts.append(f"intraday={_value(intraday_state)}")
    swing_grade = row.get("swing_grade")
    if swing_grade:
        parts.append(f"swing_grade={_value(swing_grade)}")
    intraday_grade = row.get("intraday_grade")
    if intraday_grade:
        parts.append(f"intraday_grade={_value(intraday_grade)}")
    return " ".join(parts)


def _provenance_bits(row: dict[str, Any]) -> list[str]:
    return [
        f"source={_value(_row_value(row, 'source', 'sources'))}",
        f"as_of={_value(_row_value(row, 'as_of_et', 'as_of'))}",
        f"gap_basis={_value(_row_value(row, 'gap_basis'))}",
        f"confidence={_value(_row_value(row, 'confidence'))}",
        f"data_status={_value(_row_value(row, 'data_status'))}",
    ]


def _render_updates(rows: list[dict[str, Any]]) -> None:
    _section("What Changed Since The Last Run")
    if not rows:
        typer.echo("- none")
        return
    for row in rows:
        typer.echo(
            f"- {_value(row.get('ticker'))} previous_state={_value(row.get('previous_state'))} "
            f"current_state={_value(row.get('current_state'))} "
            f"state_changed={_value(row.get('state_changed'))}"
        )


def _render_pending_reviews(rows: list[dict[str, Any]]) -> None:
    _section("Pending Manual Review Queue")
    if not rows:
        typer.echo("- none")
        return
    for row in rows:
        typer.echo(
            f"- {_value(row.get('ticker'))} suggested_outcome={_value(row.get('suggested_outcome'))}"
        )


def _render_unified_carryover(payload: dict[str, Any]) -> None:
    _section("Unified Carryover")
    if not payload:
        typer.echo("- none")
        return
    summary = payload.get("summary") or {}
    if summary:
        _render_summary("Summary", summary)
    groups = payload.get("groups") or {}
    if not groups:
        typer.echo("- none")
        return
    for group_name in ["carry_forward", "manual_review", "blocked", "ignore"]:
        rows = groups.get(group_name) or []
        typer.echo(f"{group_name}:")
        if not rows:
            typer.echo("- none")
            continue
        for row in rows:
            typer.echo(
                f"- {_value(row.get('ticker'))} "
                f"action={_value(row.get('action_mode'))} "
                f"alignment={_value(row.get('alignment'))} "
                f"primary={_value(row.get('primary_timeframe'))}"
            )
            if row.get("thesis"):
                typer.echo(f"  thesis={_value(row.get('thesis'))}")


def _render_carryover(groups: dict[str, Any], summary: dict[str, Any]) -> None:
    _section("Carryover Prep")
    if summary:
        _render_summary("Summary", summary)
    if not groups:
        typer.echo("- none")
        return
    for name, rows in groups.items():
        typer.echo(f"{name}:")
        if not rows:
            typer.echo("- none")
            continue
        for row in rows:
            if isinstance(row, dict):
                typer.echo(f"- {_value(row.get('ticker'))} reason={_value(row.get('reason'))}")
            else:
                typer.echo(f"- {_value(row)}")


def _render_disclaimer(disclaimer: str) -> None:
    _section("Disclaimer")
    typer.echo(disclaimer)


def _section(title: str) -> None:
    typer.echo("")
    typer.echo(f"{title}:")


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


def _row_value(row: dict[str, Any], *keys: str) -> Any:
    data_quality = row.get("data_quality") if isinstance(row.get("data_quality"), dict) else {}
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
        if key in data_quality and data_quality[key] is not None:
            return data_quality[key]
    return None


if __name__ == "__main__":
    app()
