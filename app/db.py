from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from app.config import get_config
from app.models import AssetProfile, CombinedSnapshot, ScannerResult, model_to_dict, utc_now_iso


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS assets (
    ticker TEXT PRIMARY KEY,
    name TEXT,
    exchange TEXT,
    sector TEXT,
    industry TEXT,
    country TEXT,
    market_cap REAL,
    shares_outstanding REAL,
    float_shares REAL,
    source TEXT,
    profile_updated_at TEXT,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    previous_close REAL,
    premarket_price REAL,
    latest_price REAL,
    open_price REAL,
    high REAL,
    low REAL,
    volume REAL,
    source_primary TEXT,
    source_secondary TEXT,
    confidence TEXT,
    raw_yfinance_json TEXT,
    raw_alpaca_json TEXT
);

CREATE TABLE IF NOT EXISTS scanner_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    name TEXT,
    universe TEXT,
    market_cap REAL,
    previous_close REAL,
    premarket_price REAL,
    latest_price REAL,
    gap_pct REAL,
    gap_dollar REAL,
    gap_basis TEXT,
    volume REAL,
    confidence TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scanner_runs (
    run_id TEXT PRIMARY KEY,
    universe TEXT,
    min_market_cap REAL,
    max_market_cap REAL,
    min_gap_abs REAL,
    direction TEXT,
    started_at TEXT,
    completed_at TEXT,
    status TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS agent_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    user_query TEXT NOT NULL,
    tool_name TEXT,
    tool_args_json TEXT,
    result_summary TEXT
);

CREATE TABLE IF NOT EXISTS api_usage (
    provider TEXT NOT NULL,
    usage_date TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (provider, usage_date)
);
"""


def initialize_database(db_path: str | Path | None = None) -> Path:
    path = Path(db_path) if db_path else get_config().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)
        conn.commit()
    return path


def _migrate(conn: sqlite3.Connection) -> None:
    """Idempotent column additions for pre-existing local databases.

    CREATE TABLE IF NOT EXISTS will not add columns to an already-existing
    table, so additive schema changes need an explicit, guarded ALTER.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(scanner_results)")}
    if "gap_dollar" not in columns:
        conn.execute("ALTER TABLE scanner_results ADD COLUMN gap_dollar REAL")
    if "gap_basis" not in columns:
        conn.execute("ALTER TABLE scanner_results ADD COLUMN gap_basis TEXT")


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = initialize_database(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def upsert_asset(conn: sqlite3.Connection, profile: AssetProfile) -> None:
    conn.execute(
        """
        INSERT INTO assets (
            ticker, name, exchange, sector, industry, country, market_cap,
            shares_outstanding, float_shares, source, profile_updated_at, is_active
        )
        VALUES (
            :ticker, :name, :exchange, :sector, :industry, :country, :market_cap,
            :shares_outstanding, :float_shares, :source, :profile_updated_at, :is_active
        )
        ON CONFLICT(ticker) DO UPDATE SET
            name = excluded.name,
            exchange = excluded.exchange,
            sector = excluded.sector,
            industry = excluded.industry,
            country = excluded.country,
            market_cap = excluded.market_cap,
            shares_outstanding = excluded.shares_outstanding,
            float_shares = excluded.float_shares,
            source = excluded.source,
            profile_updated_at = excluded.profile_updated_at,
            is_active = excluded.is_active
        """,
        model_to_dict(profile),
    )
    conn.commit()


def get_asset(conn: sqlite3.Connection, ticker: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM assets WHERE ticker = ?", (ticker.upper(),)).fetchone()
    return row_to_dict(row)


def get_latest_assets(conn: sqlite3.Connection, tickers: list[str]) -> dict[str, dict[str, Any]]:
    if not tickers:
        return {}
    placeholders = ",".join("?" for _ in tickers)
    rows = conn.execute(
        f"SELECT * FROM assets WHERE ticker IN ({placeholders})",
        [ticker.upper() for ticker in tickers],
    ).fetchall()
    return {row["ticker"]: dict(row) for row in rows}


def get_cached_previous_close(conn: sqlite3.Connection, ticker: str) -> float | None:
    row = conn.execute(
        """
        SELECT previous_close
        FROM snapshots
        WHERE ticker = ? AND previous_close IS NOT NULL
        ORDER BY timestamp DESC, id DESC
        LIMIT 1
        """,
        (ticker.upper(),),
    ).fetchone()
    return None if row is None else row["previous_close"]


def insert_snapshot(conn: sqlite3.Connection, snapshot: CombinedSnapshot) -> None:
    conn.execute(
        """
        INSERT INTO snapshots (
            ticker, timestamp, previous_close, premarket_price, latest_price,
            open_price, high, low, volume, source_primary, source_secondary,
            confidence, raw_yfinance_json, raw_alpaca_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot.ticker.upper(),
            snapshot.timestamp or utc_now_iso(),
            snapshot.previous_close,
            snapshot.premarket_price,
            snapshot.latest_price,
            snapshot.open_price,
            snapshot.high,
            snapshot.low,
            snapshot.volume,
            snapshot.source_primary,
            snapshot.source_secondary,
            snapshot.confidence,
            snapshot.raw_yfinance_json,
            snapshot.raw_alpaca_json,
        ),
    )
    conn.commit()


def create_scanner_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    universe: str | None,
    min_market_cap: float | None,
    max_market_cap: float | None,
    min_gap_abs: float | None,
    direction: str,
    started_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO scanner_runs (
            run_id, universe, min_market_cap, max_market_cap, min_gap_abs,
            direction, started_at, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            universe,
            min_market_cap,
            max_market_cap,
            min_gap_abs,
            direction,
            started_at,
            "RUNNING",
        ),
    )
    conn.commit()


def complete_scanner_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    status: str,
    completed_at: str,
    error_message: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE scanner_runs
        SET status = ?, completed_at = ?, error_message = ?
        WHERE run_id = ?
        """,
        (status, completed_at, error_message, run_id),
    )
    conn.commit()


def insert_scanner_result(conn: sqlite3.Connection, run_id: str, result: ScannerResult) -> None:
    conn.execute(
        """
        INSERT INTO scanner_results (
            run_id, ticker, name, universe, market_cap, previous_close,
            premarket_price, latest_price, gap_pct, gap_dollar, gap_basis, volume,
            confidence, notes, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            result.ticker.upper(),
            result.name,
            result.universe,
            result.market_cap,
            result.previous_close,
            result.premarket_price,
            result.latest_price,
            result.gap_pct,
            result.gap_dollar,
            result.gap_basis,
            result.volume,
            result.confidence,
            result.notes,
            result.created_at,
        ),
    )
    conn.commit()


def get_latest_scanner_result(conn: sqlite3.Connection, ticker: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT *
        FROM scanner_results
        WHERE ticker = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (ticker.upper(),),
    ).fetchone()
    return row_to_dict(row)


def get_api_usage_count(conn: sqlite3.Connection, provider: str, usage_date: date | None = None) -> int:
    usage_day = (usage_date or date.today()).isoformat()
    row = conn.execute(
        "SELECT count FROM api_usage WHERE provider = ? AND usage_date = ?",
        (provider, usage_day),
    ).fetchone()
    return 0 if row is None else int(row["count"])


def increment_api_usage(conn: sqlite3.Connection, provider: str, usage_date: date | None = None) -> int:
    usage_day = (usage_date or date.today()).isoformat()
    conn.execute(
        """
        INSERT INTO api_usage (provider, usage_date, count)
        VALUES (?, ?, 1)
        ON CONFLICT(provider, usage_date) DO UPDATE SET count = count + 1
        """,
        (provider, usage_day),
    )
    conn.commit()
    return get_api_usage_count(conn, provider, usage_date)


def log_agent_query(
    conn: sqlite3.Connection,
    *,
    user_query: str,
    tool_name: str,
    tool_args: dict[str, Any],
    result_summary: str,
) -> None:
    conn.execute(
        """
        INSERT INTO agent_queries (
            timestamp, user_query, tool_name, tool_args_json, result_summary
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            utc_now_iso(),
            user_query,
            tool_name,
            json.dumps(tool_args, sort_keys=True),
            result_summary,
        ),
    )
    conn.commit()
