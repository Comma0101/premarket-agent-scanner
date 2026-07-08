from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from app.config import get_config
from app.models import (
    AssetProfile,
    CatalystEvent,
    CombinedSnapshot,
    FilingEvent,
    FormerRunnerEvent,
    ScannerResult,
    model_to_dict,
    utc_now_iso,
)


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

CREATE TABLE IF NOT EXISTS ticker_filings (
    ticker TEXT NOT NULL,
    form_type TEXT NOT NULL,
    filed_at TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    description TEXT,
    source_url TEXT,
    risk_tags_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (ticker, accession_number)
);

CREATE TABLE IF NOT EXISTS ticker_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    headline TEXT NOT NULL,
    published_at TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL,
    url TEXT,
    summary TEXT,
    confidence TEXT NOT NULL DEFAULT 'UNKNOWN',
    catalyst_quality TEXT,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ticker_news_url
ON ticker_news(ticker, url)
WHERE url IS NOT NULL AND url <> '';

CREATE UNIQUE INDEX IF NOT EXISTS idx_ticker_news_no_url
ON ticker_news(ticker, headline, published_at)
WHERE url IS NULL OR url = '';

CREATE TABLE IF NOT EXISTS ticker_runner_history (
    ticker TEXT NOT NULL,
    event_date TEXT NOT NULL,
    max_gap_pct REAL,
    max_volume REAL,
    source_run_id TEXT NOT NULL DEFAULT '',
    notes_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (ticker, event_date, source_run_id)
);

CREATE TABLE IF NOT EXISTS lance_watchlist_items (
    session_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    state TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    playbook TEXT NOT NULL,
    why_watching TEXT NOT NULL,
    invalidates_if TEXT,
    next_step TEXT,
    data_quality_json TEXT NOT NULL DEFAULT '{}',
    plan_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (session_id, ticker)
);

CREATE TABLE IF NOT EXISTS lance_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    playbook TEXT NOT NULL,
    outcome TEXT NOT NULL,
    notes TEXT,
    plan_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lance_watchlist_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    event_type TEXT NOT NULL,
    state TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    data_quality_json TEXT NOT NULL DEFAULT '{}',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
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
    news_columns = {row[1] for row in conn.execute("PRAGMA table_info(ticker_news)")}
    if "catalyst_quality" not in news_columns:
        conn.execute("ALTER TABLE ticker_news ADD COLUMN catalyst_quality TEXT")


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = initialize_database(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _json_dumps_list(values: list[Any] | None) -> str:
    return json.dumps(values or [], sort_keys=True)


def _json_loads_list(value: str | None) -> list[Any]:
    if not value:
        return []
    parsed = json.loads(value)
    return parsed if isinstance(parsed, list) else []


def _json_dumps_dict(values: dict[str, Any] | None) -> str:
    return json.dumps(values or {}, sort_keys=True)


def _json_loads_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


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


def insert_filing_event(db_path: str | Path | None, event: FilingEvent) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO ticker_filings (
                ticker, form_type, filed_at, accession_number, description,
                source_url, risk_tags_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, accession_number) DO UPDATE SET
                form_type = excluded.form_type,
                filed_at = excluded.filed_at,
                description = excluded.description,
                source_url = excluded.source_url,
                risk_tags_json = excluded.risk_tags_json,
                updated_at = excluded.updated_at
            """,
            (
                event.ticker.upper(),
                event.form_type,
                event.filed_at,
                event.accession_number,
                event.description,
                event.source_url,
                _json_dumps_list(event.risk_tags),
                utc_now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_cached_filings(
    db_path: str | Path | None,
    ticker: str,
    limit: int = 10,
) -> list[FilingEvent]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM ticker_filings
            WHERE ticker = ?
            ORDER BY filed_at DESC, accession_number DESC
            LIMIT ?
            """,
            (ticker.upper(), max(0, int(limit))),
        ).fetchall()
    finally:
        conn.close()
    return [
        FilingEvent(
            ticker=row["ticker"],
            form_type=row["form_type"],
            filed_at=row["filed_at"],
            accession_number=row["accession_number"],
            description=row["description"],
            source_url=row["source_url"],
            risk_tags=_json_loads_list(row["risk_tags_json"]),
        )
        for row in rows
    ]


def insert_news_event(db_path: str | Path | None, event: CatalystEvent) -> None:
    conn = get_connection(db_path)
    ticker = event.ticker.upper()
    published_at = event.published_at or ""
    url = event.url or None
    updated_at = utc_now_iso()
    try:
        if url:
            existing = conn.execute(
                """
                SELECT rowid AS row_id
                FROM ticker_news
                WHERE ticker = ? AND url = ?
                ORDER BY updated_at DESC, rowid DESC
                LIMIT 1
                """,
                (ticker, url),
            ).fetchone()
        else:
            existing = conn.execute(
                """
                SELECT rowid AS row_id
                FROM ticker_news
                WHERE ticker = ?
                    AND headline = ?
                    AND published_at = ?
                    AND (url IS NULL OR url = '')
                ORDER BY updated_at DESC, rowid DESC
                LIMIT 1
                """,
                (ticker, event.headline, published_at),
            ).fetchone()

        if existing is not None:
            row_id = existing["row_id"]
            conn.execute(
                """
                UPDATE ticker_news
                SET headline = ?,
                    published_at = ?,
                    source = ?,
                    url = ?,
                    summary = ?,
                    confidence = ?,
                    catalyst_quality = ?,
                    updated_at = ?
                WHERE rowid = ?
                """,
                (
                    event.headline,
                    published_at,
                    event.source,
                    url,
                    event.summary,
                    event.confidence,
                    event.catalyst_quality,
                    updated_at,
                    row_id,
                ),
            )
            if url:
                conn.execute(
                    """
                    DELETE FROM ticker_news
                    WHERE ticker = ? AND url = ? AND rowid <> ?
                    """,
                    (ticker, url, row_id),
                )
            else:
                conn.execute(
                    """
                    DELETE FROM ticker_news
                    WHERE ticker = ?
                        AND headline = ?
                        AND published_at = ?
                        AND (url IS NULL OR url = '')
                        AND rowid <> ?
                    """,
                    (ticker, event.headline, published_at, row_id),
                )
            conn.commit()
            return

        conn.execute(
            """
            INSERT INTO ticker_news (
                ticker, headline, published_at, source, url, summary, confidence,
                catalyst_quality, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                event.headline,
                published_at,
                event.source,
                url,
                event.summary,
                event.confidence,
                event.catalyst_quality,
                updated_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_cached_news(
    db_path: str | Path | None,
    ticker: str,
    limit: int = 10,
) -> list[CatalystEvent]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM ticker_news
            WHERE ticker = ?
            ORDER BY published_at DESC, headline ASC
            LIMIT ?
            """,
            (ticker.upper(), max(0, int(limit))),
        ).fetchall()
    finally:
        conn.close()
    return [
        CatalystEvent(
            ticker=row["ticker"],
            headline=row["headline"],
            published_at=row["published_at"] or None,
            source=row["source"],
            url=row["url"],
            summary=row["summary"],
            confidence=row["confidence"],
            catalyst_quality=row["catalyst_quality"],
        )
        for row in rows
    ]


def insert_runner_event(db_path: str | Path | None, event: FormerRunnerEvent) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO ticker_runner_history (
                ticker, event_date, max_gap_pct, max_volume, source_run_id,
                notes_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, event_date, source_run_id) DO UPDATE SET
                max_gap_pct = excluded.max_gap_pct,
                max_volume = excluded.max_volume,
                notes_json = excluded.notes_json,
                updated_at = excluded.updated_at
            """,
            (
                event.ticker.upper(),
                event.event_date,
                event.max_gap_pct,
                event.max_volume,
                event.source_run_id or "",
                _json_dumps_list(event.notes),
                utc_now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_runner_history(
    db_path: str | Path | None,
    ticker: str,
    limit: int = 5,
) -> list[FormerRunnerEvent]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM ticker_runner_history
            WHERE ticker = ?
            ORDER BY event_date DESC, max_gap_pct DESC
            LIMIT ?
            """,
            (ticker.upper(), max(0, int(limit))),
        ).fetchall()
    finally:
        conn.close()
    return [
        FormerRunnerEvent(
            ticker=row["ticker"],
            event_date=row["event_date"],
            max_gap_pct=row["max_gap_pct"],
            max_volume=row["max_volume"],
            source_run_id=row["source_run_id"] or None,
            notes=_json_loads_list(row["notes_json"]),
        )
        for row in rows
    ]


def upsert_lance_watchlist_item(
    db_path: str | Path | None,
    *,
    session_id: str,
    ticker: str,
    state: str,
    score: float,
    playbook: str,
    why_watching: str,
    invalidates_if: str | None,
    next_step: str | None,
    data_quality: dict[str, Any] | None,
    plan: dict[str, Any] | None,
) -> None:
    normalized = ticker.upper()
    now = utc_now_iso()
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO lance_watchlist_items (
                session_id, ticker, created_at, updated_at, state, score, playbook,
                why_watching, invalidates_if, next_step, data_quality_json, plan_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, ticker) DO UPDATE SET
                updated_at = excluded.updated_at,
                state = excluded.state,
                score = excluded.score,
                playbook = excluded.playbook,
                why_watching = excluded.why_watching,
                invalidates_if = excluded.invalidates_if,
                next_step = excluded.next_step,
                data_quality_json = excluded.data_quality_json,
                plan_json = excluded.plan_json
            """,
            (
                session_id,
                normalized,
                now,
                now,
                state,
                float(score),
                playbook,
                why_watching,
                invalidates_if,
                next_step,
                _json_dumps_dict(data_quality),
                _json_dumps_dict(plan),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_lance_watchlist_items(
    db_path: str | Path | None,
    *,
    session_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM lance_watchlist_items
            WHERE session_id = ?
            ORDER BY score DESC, updated_at DESC, ticker ASC
            LIMIT ?
            """,
            (session_id, max(0, int(limit))),
        ).fetchall()
    finally:
        conn.close()

    output = []
    for row in rows:
        item = dict(row)
        item["data_quality"] = _json_loads_dict(item.pop("data_quality_json", None))
        item["plan"] = _json_loads_dict(item.pop("plan_json", None))
        output.append(item)
    return output


def get_latest_lance_session_id(
    db_path: str | Path | None,
    *,
    session_id_suffix: str | None = None,
    exclude_session_id_suffix: str | None = None,
) -> str | None:
    clauses = []
    params: list[Any] = []
    if session_id_suffix:
        clauses.append("session_id LIKE ?")
        params.append(f"%{session_id_suffix}")
    if exclude_session_id_suffix:
        clauses.append("session_id NOT LIKE ?")
        params.append(f"%{exclude_session_id_suffix}")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            f"""
            SELECT session_id, MAX(rowid) AS latest_row_id
            FROM lance_watchlist_items
            {where}
            GROUP BY session_id
            ORDER BY MAX(updated_at) DESC, latest_row_id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
    finally:
        conn.close()
    return None if row is None else str(row["session_id"])


def insert_lance_outcome(
    db_path: str | Path | None,
    *,
    session_id: str,
    ticker: str,
    playbook: str,
    outcome: str,
    notes: str | None = None,
    plan: dict[str, Any] | None = None,
) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO lance_outcomes (
                session_id, ticker, playbook, outcome, notes, plan_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                ticker.upper(),
                playbook,
                outcome,
                notes,
                _json_dumps_dict(plan),
                utc_now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_lance_outcomes(
    db_path: str | Path | None,
    *,
    ticker: str | None = None,
    session_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses = []
    params: list[Any] = []
    if ticker:
        clauses.append("ticker = ?")
        params.append(ticker.upper())
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(0, int(limit)))
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            f"""
            SELECT *
            FROM lance_outcomes
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    output = []
    for row in rows:
        item = dict(row)
        item["plan"] = _json_loads_dict(item.pop("plan_json", None))
        output.append(item)
    return output


def insert_lance_watchlist_event(
    db_path: str | Path | None,
    *,
    session_id: str,
    ticker: str,
    event_type: str,
    state: str,
    score: float,
    data_quality: dict[str, Any] | None,
    payload: dict[str, Any] | None,
) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO lance_watchlist_events (
                session_id, ticker, event_type, state, score, data_quality_json,
                payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                ticker.upper(),
                event_type,
                state,
                float(score),
                _json_dumps_dict(data_quality),
                _json_dumps_dict(payload),
                utc_now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_lance_watchlist_events(
    db_path: str | Path | None,
    *,
    session_id: str,
    ticker: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    clauses = ["session_id = ?"]
    params: list[Any] = [session_id]
    if ticker:
        clauses.append("ticker = ?")
        params.append(ticker.upper())
    params.append(max(0, int(limit)))
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            f"""
            SELECT *
            FROM lance_watchlist_events
            WHERE {' AND '.join(clauses)}
            ORDER BY id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    output = []
    for row in rows:
        item = dict(row)
        item["data_quality"] = _json_loads_dict(item.pop("data_quality_json", None))
        item["payload"] = _json_loads_dict(item.pop("payload_json", None))
        output.append(item)
    return output


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
