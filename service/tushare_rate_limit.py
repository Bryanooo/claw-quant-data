"""Distributed Tushare request pacing shared by every collector process."""

from collections.abc import Callable
from functools import lru_cache
import math
import time
from typing import Any
from datetime import timedelta
from zoneinfo import ZoneInfo

import psycopg2

from service.config import DB_CONFIG, TUSHARE_GLOBAL_MIN_INTERVAL_SECONDS
from service.collection_jobs.context import is_durable_job_active


GLOBAL_RATE_KEY = "__token_global__"
MAX_INLINE_DURABLE_WAIT_SECONDS = 5.0
# Live provider response on 2026-09-20 proves that this token is limited to 40
# major_news calls per Shanghai calendar day (and 20/minute). Reserve only 35
# so manual verification and clock skew cannot push production over quota.
INTERFACE_DAILY_QUOTAS = {"major_news": 35}
SHANGHAI = ZoneInfo("Asia/Shanghai")


class TushareRateSlotDeferredError(RuntimeError):
    """Ask the durable queue to release its worker until the slot is ready."""

    retryable = True
    defer_without_failure = True

    def __init__(self, api_name: str, wait_seconds: float):
        self.retry_after_seconds = max(math.ceil(wait_seconds), 1)
        super().__init__(
            f"Tushare rate slot for {api_name} is available in "
            f"{self.retry_after_seconds} seconds"
        )


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
    quota_wait = _reserve_daily_quota(
        api_name,
        connection_factory=connection_factory,
        sleep=sleep,
    )
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
        return quota_wait

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
            wait = max((slot - database_now).total_seconds(), 0.0)
            # A long inline sleep would occupy a scarce Worker lease and may
            # exceed the whole-job timeout. Do not reserve a later slot yet:
            # release this durable job back to PostgreSQL and let another job
            # use the process while the interface-specific window matures.
            if (
                is_durable_job_active()
                and wait > MAX_INLINE_DURABLE_WAIT_SECONDS
            ):
                raise TushareRateSlotDeferredError(api_name, wait)
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
    return quota_wait + wait


def _reserve_daily_quota(
    api_name: str,
    *,
    connection_factory: Callable[..., Any],
    sleep: Callable[[float], None],
) -> float:
    """Reserve one call from a shared Shanghai-calendar-day allocation.

    The database table retains its historical ``hourly`` name because that
    migration has already been published. Its window columns are generic and
    safely support this corrected daily contract.
    """
    limit = INTERFACE_DAILY_QUOTAS.get(api_name)
    if limit is None:
        return 0.0
    total_wait = 0.0
    while True:
        connection = connection_factory(**DB_CONFIG)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO sys_tushare_hourly_quota(
                        api_name, window_started_at, reservations
                    ) VALUES (%s, NOW(), 0)
                    ON CONFLICT (api_name) DO NOTHING
                    """,
                    (api_name,),
                )
                cursor.execute(
                    """
                    SELECT window_started_at, reservations, NOW()
                    FROM sys_tushare_hourly_quota
                    WHERE api_name = %s
                    FOR UPDATE
                    """,
                    (api_name,),
                )
                window_started_at, reservations, database_now = cursor.fetchone()
                local_now = database_now.astimezone(SHANGHAI)
                day_started_at = local_now.replace(
                    hour=0, minute=0, second=0, microsecond=0
                ).astimezone(database_now.tzinfo)
                next_day_at = day_started_at + timedelta(days=1, minutes=5)
                if window_started_at < day_started_at:
                    window_started_at = day_started_at
                    reservations = 0
                if reservations >= limit:
                    wait = max(
                        (next_day_at - database_now).total_seconds(),
                        1.0,
                    )
                    if is_durable_job_active():
                        raise TushareRateSlotDeferredError(api_name, wait)
                    connection.commit()
                else:
                    cursor.execute(
                        """
                        UPDATE sys_tushare_hourly_quota
                        SET window_started_at = %s, reservations = %s,
                            updated_at = NOW()
                        WHERE api_name = %s
                        """,
                        (window_started_at, reservations + 1, api_name),
                    )
                    connection.commit()
                    return total_wait
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        sleep(wait)
        total_wait += wait
