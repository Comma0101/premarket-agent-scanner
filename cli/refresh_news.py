"""CLI: refresh cached catalyst/news events for explicit tickers.

Examples:
    python -m cli.refresh_news --tickers HOT,COOL
    python -m cli.refresh_news --tickers HOT --db-path data/market_data.sqlite
"""

from __future__ import annotations

from pathlib import Path

import typer

from app.config import get_config
from app.db import insert_news_event
from providers.news_provider import RSSNewsProvider

app = typer.Typer(add_completion=False, help="Refresh cached catalyst/news events.")


@app.command()
def main(
    tickers: str = typer.Option(..., "--tickers", "-t", help="Ad-hoc tickers, comma-separated."),
    db_path: Path | None = typer.Option(None, "--db-path", help="SQLite path override."),
) -> None:
    symbols = _parse_tickers(tickers)
    if not symbols:
        raise typer.BadParameter("Provide at least one ticker.")

    resolved_db_path = db_path or get_config().database_path
    provider = RSSNewsProvider()
    total = 0
    for ticker in symbols:
        try:
            events = provider.get_recent_news(ticker)
        except Exception as exc:
            typer.echo(f"{ticker}: error: {exc}")
            continue

        for event in events:
            insert_news_event(resolved_db_path, event)
        total += len(events)
        typer.echo(f"{ticker}: {len(events)} catalyst(s)")

    typer.echo(f"{total} catalyst(s) cached.")


def _parse_tickers(value: str) -> list[str]:
    return [ticker.strip().upper() for ticker in value.split(",") if ticker.strip()]


if __name__ == "__main__":
    app()
