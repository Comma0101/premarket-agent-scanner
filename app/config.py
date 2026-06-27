from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv(BASE_DIR / ".env")


def database_path_from_url(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Only sqlite:/// DATABASE_URL values are supported in V1.")

    raw_path = database_url.removeprefix("sqlite:///")
    path = Path(raw_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


@dataclass(frozen=True)
class AppConfig:
    alpaca_api_key: str | None
    alpaca_secret_key: str | None
    fmp_api_key: str | None
    database_url: str
    database_path: Path
    default_timezone: str = "America/New_York"


def get_config() -> AppConfig:
    _load_dotenv_if_available()

    database_url = os.getenv("DATABASE_URL", "sqlite:///data/market_data.sqlite")
    return AppConfig(
        alpaca_api_key=os.getenv("ALPACA_API_KEY") or None,
        alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY") or None,
        fmp_api_key=os.getenv("FMP_API_KEY") or None,
        database_url=database_url,
        database_path=database_path_from_url(database_url),
        default_timezone=os.getenv("DEFAULT_TIMEZONE", "America/New_York"),
    )
