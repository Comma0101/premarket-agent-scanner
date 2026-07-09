"""CLI: Lance end-of-day review, outcome journal, and carryover prep."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import typer

from agent_tools.tools import (
    build_lance_carryover_plan,
    journal_lance_outcome,
    review_lance_session,
    summarize_lance_memory,
)


app = typer.Typer(add_completion=False, help="Review and close a Lance session.")

DISCLAIMER = "Matches your filter - not buy/sell advice. Verify before acting."


@app.command("review")
def review_command(
    session_id: str | None = typer.Option(None, "--session-id", help="Lance session id."),
    limit: int = typer.Option(500, "--limit", help="Maximum timeline events to review."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    payload = review_lance_session(session_id=session_id, limit=limit)
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_review(payload)


@app.command("journal")
def journal_command(
    session_id: str = typer.Option(..., "--session-id", help="Lance session id."),
    ticker: str = typer.Option(..., "--ticker", help="Ticker to journal."),
    playbook: str = typer.Option(..., "--playbook", help="Playbook name."),
    outcome: str = typer.Option(..., "--outcome", help="worked, failed, chop, reversed, unknown."),
    notes: str | None = typer.Option(None, "--notes", help="Optional human review notes."),
    plan_json: str | None = typer.Option(
        None,
        "--plan-json",
        help="Optional unified plan JSON to attach to the journaled outcome.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    plan = _parse_plan_json(plan_json)
    payload = journal_lance_outcome(
        session_id=session_id,
        ticker=ticker,
        playbook=playbook,
        outcome=outcome,
        notes=notes,
        plan=plan,
    )
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_journal(payload)


@app.command("carryover")
def carryover_command(
    session_id: str | None = typer.Option(None, "--session-id", help="Source Lance session id."),
    target_session_date: str | None = typer.Option(
        None,
        "--target-session-date",
        help="Next-session date label.",
    ),
    limit: int = typer.Option(500, "--limit", help="Maximum timeline events to inspect."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    payload = build_lance_carryover_plan(
        session_id=session_id,
        target_session_date=target_session_date,
        limit=limit,
    )
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_carryover(payload)


@app.command("memory")
def memory_command(
    session_id: str | None = typer.Option(None, "--session-id", help="Optional session filter."),
    ticker: str | None = typer.Option(None, "--ticker", help="Optional ticker filter."),
    limit: int = typer.Option(100, "--limit", help="Maximum outcome rows to summarize."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    payload = summarize_lance_memory(
        session_id=session_id,
        ticker=ticker,
        limit=limit,
    )
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_memory(payload)


@app.command("summary")
def summary_command(
    session_id: str | None = typer.Option(None, "--session-id", help="Lance session id."),
    summary_date: str | None = typer.Option(None, "--date", help="Summary date, YYYY-MM-DD."),
    output_dir: Path = typer.Option(
        Path("data/daily_summaries"),
        "--output-dir",
        help="Directory for saved JSON and Markdown summaries.",
    ),
    limit: int = typer.Option(500, "--limit", help="Maximum rows/events to inspect."),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON."),
) -> None:
    review = review_lance_session(session_id=session_id, limit=limit)
    resolved_session_id = review.get("session_id") or session_id
    memory = summarize_lance_memory(
        session_id=str(resolved_session_id) if resolved_session_id else None,
        limit=limit,
    )
    carryover = build_lance_carryover_plan(
        session_id=str(resolved_session_id) if resolved_session_id else None,
        target_session_date=None,
        limit=limit,
    )
    payload = _daily_summary_payload(
        summary_date or _today_ny(),
        str(resolved_session_id) if resolved_session_id else None,
        review,
        memory,
        carryover,
        output_dir,
    )
    _write_daily_summary(payload)
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    _render_daily_summary(payload)


def _render_review(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Lance EOD Review:")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    typer.echo(f"Session: {_value(payload.get('session_id'))}")
    typer.echo(
        f"Counts: tickers={_value(payload.get('ticker_count'))} "
        f"pending={_value(payload.get('pending_count'))} "
        f"reviewed={_value(payload.get('reviewed_count'))}"
    )
    typer.echo("")
    typer.echo("Pending Reviews:")
    pending = payload.get("pending_reviews") or []
    if not pending:
        typer.echo("- none")
    for row in pending:
        typer.echo(
            f"- {_value(row.get('ticker'))} "
            f"latest_state={_value(row.get('latest_state'))} "
            f"score_delta={_value(row.get('score_delta'))} "
            f"gap_pct_delta={_value(row.get('gap_pct_delta'))} "
            f"rel_volume_delta={_value(row.get('rel_volume_delta'))} "
            f"focus={_value(row.get('review_focus'))}"
        )
        args = row.get("journal_args") or {}
        typer.echo(
            f"  journal: session_id={_value(args.get('session_id'))} "
            f"ticker={_value(args.get('ticker'))} "
            f"playbook={_value(args.get('playbook'))} "
            f"outcome={_value(args.get('outcome'))}"
        )
    _render_notes(payload.get("notes") or [])
    _render_disclaimer(payload)


def _render_memory(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Lance Market Memory:")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    typer.echo(f"outcome_count={_value(payload.get('outcome_count'))}")
    filters = payload.get("filters") or {}
    typer.echo(
        f"filters: session_id={_value(filters.get('session_id'))} "
        f"ticker={_value(filters.get('ticker'))} limit={_value(filters.get('limit'))}"
    )
    typer.echo("")
    typer.echo("By Playbook:")
    _render_memory_rows(payload.get("by_playbook") or [], "playbook")
    typer.echo("")
    typer.echo("By Ticker:")
    _render_memory_rows(payload.get("by_ticker") or [], "ticker")
    typer.echo("")
    typer.echo("By Action Mode:")
    _render_memory_rows(payload.get("by_action_mode") or [], "action_mode")
    typer.echo("")
    typer.echo("By Alignment:")
    _render_memory_rows(payload.get("by_alignment") or [], "alignment")
    typer.echo("")
    typer.echo("By Primary Timeframe:")
    _render_memory_rows(payload.get("by_primary_timeframe") or [], "primary_timeframe")
    _render_notes(payload.get("notes") or [])
    _render_disclaimer(payload)


def _render_daily_summary(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Lance Daily Summary:")
    typer.echo(f"Date: {_value(payload.get('date'))}")
    typer.echo(f"Session: {_value(payload.get('session_id'))}")
    typer.echo(f"Live session captured: {_yes_no(payload.get('live_session_captured'))}")
    watched = payload.get("watched") or {}
    typer.echo(
        f"Watched: tickers={_value(watched.get('ticker_count'))} "
        f"pending={_value(watched.get('pending_count'))} "
        f"reviewed={_value(watched.get('reviewed_count'))}"
    )
    outcomes = payload.get("outcomes") or {}
    counts = outcomes.get("counts") or {}
    typer.echo(
        "Outcomes: "
        f"worked={_value(counts.get('worked'))} failed={_value(counts.get('failed'))} "
        f"chop={_value(counts.get('chop'))} reversed={_value(counts.get('reversed'))} "
        f"unknown={_value(counts.get('unknown'))}"
    )
    typer.echo("")
    typer.echo("Tomorrow Follow-Up:")
    follow_up = payload.get("tomorrow_follow_up") or []
    if not follow_up:
        typer.echo("- none")
    for row in follow_up:
        typer.echo(f"- {_value(row.get('ticker'))} source={_value(row.get('source'))}")
    _render_notes(payload.get("notes") or [])
    typer.echo("")
    typer.echo("Files:")
    files = payload.get("files") or {}
    typer.echo(f"- json: {_value(files.get('json'))}")
    typer.echo(f"- markdown: {_value(files.get('markdown'))}")
    _render_disclaimer(payload)


def _daily_summary_payload(
    summary_date: str,
    session_id: str | None,
    review: dict[str, Any],
    memory: dict[str, Any],
    carryover: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    json_path = output_dir / f"{summary_date}.json"
    markdown_path = output_dir / f"{summary_date}.md"
    pending = review.get("pending_reviews") if isinstance(review.get("pending_reviews"), list) else []
    reviewed = review.get("reviewed") if isinstance(review.get("reviewed"), list) else []
    source_session_date = _session_date(session_id)
    live_session_captured = source_session_date in {None, summary_date}
    notes = []
    if not live_session_captured:
        notes.append(
            f"No live Lance session captured for {summary_date}; using latest persisted session {session_id} for prep/carryover only."
        )
    return {
        "agent_name": "lance_eod",
        "mode": "daily_summary",
        "date": summary_date,
        "session_id": session_id,
        "source_session_date": source_session_date,
        "live_session_captured": live_session_captured,
        "status": _summary_status(review, memory, carryover) if live_session_captured else "PREP_ONLY",
        "watched": {
            "ticker_count": review.get("ticker_count"),
            "pending_count": review.get("pending_count"),
            "reviewed_count": review.get("reviewed_count"),
            "tickers": _dedupe_tickers([*pending, *reviewed]),
        },
        "outcomes": {
            "outcome_count": memory.get("outcome_count"),
            "counts": _outcome_counts(memory.get("recent_outcomes") or []),
            "by_playbook": memory.get("by_playbook") or [],
            "by_ticker": memory.get("by_ticker") or [],
        },
        "tomorrow_follow_up": _tomorrow_follow_up(pending, carryover),
        "market_context": {
            "regime": "unknown",
            "themes": [],
            "note": "No persisted market-regime snapshot is attached to the EOD summary yet.",
        },
        "tim_sykes": {
            "status": "unknown",
            "tickers": [],
            "note": "Tim/Sykes session persistence is not wired into EOD summaries yet.",
        },
        "source_reports": {
            "review": review,
            "memory": memory,
            "carryover": carryover,
        },
        "files": {
            "json": str(json_path),
            "markdown": str(markdown_path),
        },
        "notes": notes,
        "disclaimer": DISCLAIMER,
    }


def _write_daily_summary(payload: dict[str, Any]) -> None:
    files = payload["files"]
    json_path = Path(files["json"])
    markdown_path = Path(files["markdown"])
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_daily_summary_markdown(payload), encoding="utf-8")


def _daily_summary_markdown(payload: dict[str, Any]) -> str:
    watched = payload.get("watched") or {}
    outcomes = payload.get("outcomes") or {}
    counts = outcomes.get("counts") or {}
    follow_up = payload.get("tomorrow_follow_up") or []
    lines = [
        f"# Daily Trading Summary - {_value(payload.get('date'))}",
        "",
        f"- Session: {_value(payload.get('session_id'))}",
        f"- Live session captured: {_yes_no(payload.get('live_session_captured'))}",
        f"- Status: {_value(payload.get('status'))}",
        f"- Watched: {_value(watched.get('ticker_count'))} ticker(s), "
        f"{_value(watched.get('pending_count'))} pending, "
        f"{_value(watched.get('reviewed_count'))} reviewed",
        f"- Outcomes: worked={_value(counts.get('worked'))}, "
        f"failed={_value(counts.get('failed'))}, chop={_value(counts.get('chop'))}, "
        f"reversed={_value(counts.get('reversed'))}, unknown={_value(counts.get('unknown'))}",
        "",
        "## Tomorrow Follow-Up",
    ]
    lines.extend(
        [f"- {_value(row.get('ticker'))} ({_value(row.get('source'))})" for row in follow_up]
        or ["- none"]
    )
    notes = payload.get("notes") or []
    if notes:
        lines.extend(["", "## Notes", *[f"- {note}" for note in notes]])
    lines.extend([
        "",
        "## Data Used",
        "- review_lance_session",
        "- summarize_lance_memory",
        "- build_lance_carryover_plan",
        "",
        "## Tim/Sykes",
        f"- {_value((payload.get('tim_sykes') or {}).get('note'))}",
        "",
        DISCLAIMER,
        "",
    ])
    return "\n".join(lines)


def _summary_status(*payloads: dict[str, Any]) -> str:
    statuses = {str(payload.get("status") or "UNKNOWN") for payload in payloads}
    if statuses <= {"OK"}:
        return "OK"
    if "OK" in statuses:
        return "PARTIAL"
    if "ERROR" in statuses:
        return "ERROR"
    return "EMPTY"


def _outcome_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {key: 0 for key in ["worked", "failed", "chop", "reversed", "unknown"]}
    for row in rows:
        outcome = str(row.get("outcome") or "unknown")
        counts[outcome if outcome in counts else "unknown"] += 1
    return counts


def _tomorrow_follow_up(
    pending: list[dict[str, Any]],
    carryover: dict[str, Any],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in pending:
        ticker = row.get("ticker")
        if ticker:
            rows.append({"ticker": str(ticker), "source": "pending_review"})
    groups = carryover.get("groups") if isinstance(carryover.get("groups"), dict) else {}
    for group_name, group_rows in groups.items():
        if not isinstance(group_rows, list):
            continue
        for row in group_rows:
            if isinstance(row, dict) and row.get("ticker"):
                rows.append({"ticker": str(row["ticker"]), "source": str(group_name)})
    return _dedupe_follow_up(rows)


def _dedupe_tickers(rows: list[dict[str, Any]]) -> list[str]:
    return [row["ticker"] for row in _dedupe_follow_up([
        {"ticker": str(row["ticker"]), "source": ""}
        for row in rows
        if isinstance(row, dict) and row.get("ticker")
    ])]


def _dedupe_follow_up(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output = []
    seen = set()
    for row in rows:
        ticker = row["ticker"].upper()
        if ticker in seen:
            continue
        seen.add(ticker)
        output.append({"ticker": ticker, "source": row["source"]})
    return output


def _today_ny() -> str:
    return datetime.now(ZoneInfo("America/New_York")).date().isoformat()


def _session_date(session_id: str | None) -> str | None:
    if not session_id or len(session_id) < 10:
        return None
    value = session_id[:10]
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return None
    return value


def _yes_no(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"


def _render_memory_rows(rows: list[dict[str, Any]], label: str) -> None:
    if not rows:
        typer.echo("- none")
        return
    for row in rows:
        outcomes = row.get("outcomes") or {}
        typer.echo(
            f"- {_value(row.get(label))} "
            f"total={_value(row.get('total'))} "
            f"worked={_value(outcomes.get('worked'))} "
            f"failed={_value(outcomes.get('failed'))} "
            f"chop={_value(outcomes.get('chop'))} "
            f"reversed={_value(outcomes.get('reversed'))} "
            f"unknown={_value(outcomes.get('unknown'))} "
            f"worked_rate={_value(row.get('worked_rate'))}"
        )


def _render_journal(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Recorded Outcome:")
    if payload.get("error"):
        typer.echo(f"error={payload['error']}")
        return
    recorded = payload.get("recorded") or {}
    typer.echo(
        f"{_value(recorded.get('ticker'))} "
        f"outcome={_value(recorded.get('outcome'))} "
        f"playbook={_value(recorded.get('playbook'))} "
        f"session_id={_value(recorded.get('session_id'))}"
    )
    if recorded.get("notes"):
        typer.echo(f"notes={recorded['notes']}")
    plan_summary = recorded.get("plan_summary") or {}
    if plan_summary:
        typer.echo(
            "plan_summary: "
            f"action_mode={_value(plan_summary.get('action_mode'))} "
            f"alignment={_value(plan_summary.get('alignment'))} "
            f"primary_timeframe={_value(plan_summary.get('primary_timeframe'))}"
        )
        if plan_summary.get("thesis"):
            typer.echo(f"thesis={_value(plan_summary.get('thesis'))}")
    _render_disclaimer(payload)


def _render_carryover(payload: dict[str, Any]) -> None:
    typer.echo("")
    typer.echo("Lance Carryover Plan:")
    typer.echo(f"Status: {_value(payload.get('status'))}")
    typer.echo(
        f"source_session={_value(payload.get('source_session_id'))} "
        f"target_session={_value(payload.get('target_session_date'))} "
        f"carryover_count={_value(payload.get('carryover_count'))} "
        f"fresh_scan_required={_value(payload.get('fresh_scan_required'))}"
    )
    groups = payload.get("groups") or {}
    for group_name in ["strength_carryover", "weakness_carryover", "context_only"]:
        typer.echo("")
        typer.echo(f"{group_name}:")
        rows = groups.get(group_name) or []
        if not rows:
            typer.echo("- none")
            continue
        for row in rows:
            typer.echo(_carryover_row(row))
    _render_notes(payload.get("notes") or [])
    _render_disclaimer(payload)


def _carryover_row(row: dict[str, Any]) -> str:
    parts = [
        f"- {_value(row.get('ticker'))}",
        f"latest_state={_value(row.get('latest_state'))}",
    ]
    if row.get("gap_pct") is not None:
        parts.append(f"gap_pct={_fmt_percent(row.get('gap_pct'))}")
    if row.get("rel_volume") is not None:
        parts.append(f"rvol={_value(row.get('rel_volume'))}")
    if row.get("as_of_et") is not None:
        parts.append(f"as_of={_value(row.get('as_of_et'))}")
    if row.get("gap_basis") is not None:
        parts.append(f"gap_basis={_value(row.get('gap_basis'))}")
    if row.get("confidence") is not None:
        parts.append(f"confidence={_value(row.get('confidence'))}")
    if row.get("review_focus"):
        parts.append(f"focus={_value(row.get('review_focus'))}")
    return " ".join(parts)


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


def _parse_plan_json(plan_json: str | None) -> dict[str, Any] | None:
    if not plan_json:
        return None
    try:
        parsed = json.loads(plan_json)
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid --plan-json: {exc.msg}")
        raise typer.Exit(code=2) from exc
    if not isinstance(parsed, dict):
        typer.echo("Invalid --plan-json: expected a JSON object")
        raise typer.Exit(code=2)
    return parsed


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
