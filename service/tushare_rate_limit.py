"""Distributed Tushare request pacing shared by every collector process."""

from collections.abc import Callable
from functools import lru_cache
import time
from typing import Any

import psycopg2

from service.config import DB_CONFIG, TUSHARE_GLOBAL_MIN_INTERVAL_SECONDS


GLOBAL_RATE_KEY = "__token_global__"


def install_distributed_rate_limit(pro: Any) -> Any:
    """Wrap one Tushare SDK client exactly once and return the same client."""
    # Tushare's DataApi implements a permissive __getattr__ that fabricates an
    # endpoint callable for any name, so getattr() cannot test our marker.
    if vars(pro).get("_claw_quant_rate_limit_installed", False):
        return pro
    original_query = pro.query

    def rate_limited_query(api_name, *args, **kwargs):
        reserve_tushare_request(api_name)
        return original_query(api_name, *args, **kwargs)

    pro.query = rate_limited_query
    pro._claw_quant_rate_limit_installed = True
    return pro


@lru_cache(maxsize=256)
def interface_min_interval(api_name: str) -> float:
    """Return catalog pacing when known, otherwise rely on token pacing."""
    try:
        from service.tushare_policy import TusharePolicyRegistry

        return max(TusharePolicyRegistry().get(api_name).min_interval_seconds, 0.0)
    except (KeyError, ValueError):
        return 0.0


def reserve_tushare_request(
    api_name: str,
    *,
    interface_interval: float | None = None,
    global_interval: float = TUSHARE_GLOBAL_MIN_INTERVAL_SECONDS,
    connection_factory: Callable[..., Any] = psycopg2.connect,
    sleep: Callable[[float], None] = time.sleep,
) -> float:
    """Atomically reserve both a token-wide and an interface request slot.

    PostgreSQL row locks make this work across scheduler, workers and manual
    processes.  The transaction is committed before sleeping so another
    process can reserve the following slot without blocking on this process.
    """
    api_interval = (
        interface_min_interval(api_name)
        if interface_interval is None
        else max(float(interface_interval), 0.0)
    )
    intervals = {
        GLOBAL_RATE_KEY: max(float(global_interval), 0.0),
        api_name: api_interval,
    }
    intervals = {key: value for key, value in intervals.items() if value > 0}
    if not intervals:
        return 0.0

    connection = connection_factory(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            for key in sorted(intervals):
                cursor.execute(
                    """
                    INSERT INTO sys_tushare_rate_limit(api_name, next_allowed_at)
                    VALUES (%s, NOW())
                    ON CONFLICT (api_name) DO NOTHING
                    """,
                    (key,),
                )

            slots = []
            database_now = None
            for key in sorted(intervals):
                cursor.execute(
                    """
                    SELECT next_allowed_at, NOW()
                    FROM sys_tushare_rate_limit
                    WHERE api_name = %s
                    FOR UPDATE
                    """,
                    (key,),
                )
                next_allowed, current_database_time = cursor.fetchone()
                database_now = database_now or current_database_time
                slots.append(next_allowed)

            assert database_now is not None
            slot = max(database_now, *slots)
            for key, interval in sorted(intervals.items()):
                cursor.execute(
                    """
                    UPDATE sys_tushare_rate_limit
                    SET next_allowed_at = %s + (%s * INTERVAL '1 second'),
                        updated_at = NOW()
                    WHERE api_name = %s
                    """,
                    (slot, interval, key),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    wait = max((slot - database_now).total_seconds(), 0.0)
    if wait:
        sleep(wait)
    return wait
