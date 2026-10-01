"""Application configuration loaded from environment variables and ``.env``."""

from pathlib import Path
from datetime import time
import os

from dotenv import load_dotenv

from service.version import APP_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        result = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {value!r}") from exc
    if result < 0:
        raise ValueError(f"{name} must be non-negative, got {value!r}")
    return result


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean, got {value!r}")


def _get_time(name: str, default: str) -> time:
    value = os.getenv(name, default).strip()
    try:
        hour_text, minute_text = value.split(":", 1)
        return time(hour=int(hour_text), minute=int(minute_text))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must use HH:MM, got {value!r}") from exc


DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": _get_int("DB_PORT", 5432),
    "dbname": os.getenv("DB_NAME", "tushare_db"),
    "user": os.getenv("DB_USER", "tushare"),
    # An empty default works with local trust authentication while avoiding a
    # deployable credential in source control.
    "password": os.getenv("DB_PASSWORD", ""),
}

APP_REVISION = os.getenv("APP_REVISION", APP_VERSION)
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = _get_int("API_PORT", 8000)
API_DB_POOL_MIN = _get_int("API_DB_POOL_MIN", 1)
API_DB_POOL_MAX = _get_int("API_DB_POOL_MAX", 10)
API_DB_CONNECT_RETRIES = _get_int("API_DB_CONNECT_RETRIES", 12)
API_DB_CONNECT_RETRY_SECONDS = _get_int("API_DB_CONNECT_RETRY_SECONDS", 5)
JOB_POLL_INTERVAL_SECONDS = _get_int("JOB_POLL_INTERVAL_SECONDS", 2)
JOB_STALE_AFTER_SECONDS = _get_int("JOB_STALE_AFTER_SECONDS", 21600)
JOB_EXECUTION_TIMEOUT_SECONDS = _get_int("JOB_EXECUTION_TIMEOUT_SECONDS", 1800)
JOB_LEASE_SECONDS = _get_int("JOB_LEASE_SECONDS", 120)
JOB_RECLAIM_INTERVAL_SECONDS = _get_int("JOB_RECLAIM_INTERVAL_SECONDS", 60)
JOB_NETWORK_RETRY_BASE_SECONDS = _get_int("JOB_NETWORK_RETRY_BASE_SECONDS", 60)
JOB_NETWORK_RETRY_MAX_SECONDS = _get_int("JOB_NETWORK_RETRY_MAX_SECONDS", 900)
# Historical collection is intentionally quiet during the A-share daytime
# session. Routine daily/weekly/monthly delivery is never subject to this gate.
HISTORY_COLLECTION_PAUSE_START_TIME = _get_time(
    "HISTORY_COLLECTION_PAUSE_START_TIME", "08:30"
)
HISTORY_COLLECTION_RESUME_TIME = _get_time(
    "HISTORY_COLLECTION_RESUME_TIME", "16:00"
)
INITIALIZATION_AUTO_RECOVERY_COOLDOWN_SECONDS = _get_int(
    "INITIALIZATION_AUTO_RECOVERY_COOLDOWN_SECONDS", 300
)
INITIALIZATION_AUTO_RECOVERY_MAX_ROUNDS = _get_int(
    "INITIALIZATION_AUTO_RECOVERY_MAX_ROUNDS", 3
)
SCHEDULE_RECONCILE_LOOKBACK_DAYS = _get_int("SCHEDULE_RECONCILE_LOOKBACK_DAYS", 8)
COVERAGE_POLL_INTERVAL_SECONDS = _get_int("COVERAGE_POLL_INTERVAL_SECONDS", 5)
COVERAGE_STALE_AFTER_SECONDS = _get_int("COVERAGE_STALE_AFTER_SECONDS", 3600)
COVERAGE_AUTO_REPAIR_ENABLED = _get_bool("COVERAGE_AUTO_REPAIR_ENABLED", True)
COVERAGE_AUTO_REPAIR_LIMIT = _get_int("COVERAGE_AUTO_REPAIR_LIMIT", 10)
TUSHARE_GLOBAL_MIN_INTERVAL_SECONDS = _get_float(
    "TUSHARE_GLOBAL_MIN_INTERVAL_SECONDS",
    0.5,
)
TUSHARE_CONNECT_TIMEOUT_SECONDS = _get_float(
    "TUSHARE_CONNECT_TIMEOUT_SECONDS",
    5.0,
)
TUSHARE_READ_TIMEOUT_SECONDS = _get_float(
    "TUSHARE_READ_TIMEOUT_SECONDS",
    60.0,
)
TUSHARE_RAW_RECORD_CAPTURE_MODE = os.getenv(
    "TUSHARE_RAW_RECORD_CAPTURE_MODE", "anomalies_only"
).strip().lower()
FINANCIAL_DATA_API_KEY = os.getenv("FINANCIAL_DATA_API_KEY") or None
FINANCIAL_DATA_BASE_URL = os.getenv(
    "FINANCIAL_DATA_BASE_URL",
    "https://dfdatamcpnexus-prod.antgroup-inc.cn/api/v1/common_query",
).strip()
FINANCIAL_DATA_API_VERSION = os.getenv(
    "FINANCIAL_DATA_API_VERSION", "1.6.0"
).strip()
FINANCIAL_DATA_CONNECT_TIMEOUT_SECONDS = _get_float(
    "FINANCIAL_DATA_CONNECT_TIMEOUT_SECONDS", 20.0
)
FINANCIAL_DATA_READ_TIMEOUT_SECONDS = _get_float(
    "FINANCIAL_DATA_READ_TIMEOUT_SECONDS", 300.0
)
if TUSHARE_RAW_RECORD_CAPTURE_MODE not in {"all", "anomalies_only", "none"}:
    raise ValueError(
        "TUSHARE_RAW_RECORD_CAPTURE_MODE must be all, anomalies_only, or none"
    )
if TUSHARE_CONNECT_TIMEOUT_SECONDS <= 0:
    raise ValueError("TUSHARE_CONNECT_TIMEOUT_SECONDS must be greater than zero")
if TUSHARE_READ_TIMEOUT_SECONDS <= 0:
    raise ValueError("TUSHARE_READ_TIMEOUT_SECONDS must be greater than zero")


def get_env_tushare_token() -> str | None:
    """Return the optional Tushare token supplied by the process environment."""
    return os.getenv("TUSHARE_TOKEN") or None
