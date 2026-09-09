"""Strict completion evidence for bounded dedicated scheduler jobs.

Dedicated callables predate the durable queue and historically returned only
an integer row count.  This module upgrades the small set of schedules whose
stored scope can be proven deterministically without calling Tushare again.
Unknown or ambiguous schedules deliberately remain unverified.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any


Query = Callable[[str, tuple[Any, ...]], list[dict[str, Any]]]


def _scheduled_date(value: str | None) -> date:
    if not value:
        raise ValueError("scheduled_for is required for completion verification")
    return datetime.fromisoformat(value).date()


def verify_scheduled_transport(
    schedule_id: str,
    scheduled_for: str | None,
    rows_fetched: int,
    *,
    query: Query | None = None,
) -> dict[str, Any] | None:
    """Return strict evidence only when the persisted scope matches the run.

    The checks are intentionally schedule-specific.  A generic positive row
    count is never enough because it cannot detect a capped response or a
    partially completed multi-request schedule.
    """
    if query is None:
        from service.db import query as database_query

        query = database_query
    target = _scheduled_date(scheduled_for)
    evidence: dict[str, Any] = {
        "verified": True,
        "verification_type": "dedicated_stored_scope",
        "schedule_id": schedule_id,
        "scheduled_for": scheduled_for,
        "rows_fetched": rows_fetched,
    }

    month_end_only = {
        "stk_weekly_monthly_month_daily",
        "stk_monthly_monthly_eom",
    }
    if rows_fetched == 0 and schedule_id in month_end_only:
        result = query(
            """
            SELECT max(cal_date)=%s AS is_month_end
            FROM trade_cal
            WHERE exchange='SSE' AND is_open=1
              AND date_trunc('month', cal_date)=date_trunc('month', %s::date)
            """,
            (target, target),
        )[0]
        if bool(result.get("is_month_end")):
            return None
        return {
            **evidence,
            "scope": "conditional_schedule_skip",
            "empty": True,
            "skip_reason": "not_last_open_day_of_month",
            "target_date": target.isoformat(),
        }
    if rows_fetched == 0 and schedule_id == "stk_weekly_monthly_week_daily":
        result = query(
            """
            SELECT max(cal_date)=%s AS is_week_end
            FROM trade_cal
            WHERE exchange='SSE' AND is_open=1
              AND date_trunc('week', cal_date)=date_trunc('week', %s::date)
            """,
            (target, target),
        )[0]
        if bool(result.get("is_week_end")):
            return None
        return {
            **evidence,
            "scope": "conditional_schedule_skip",
            "empty": True,
            "skip_reason": "not_last_open_day_of_week",
            "target_date": target.isoformat(),
        }
    if rows_fetched == 0 and schedule_id == "stk_weekly_weekly_fri":
        result = query(
            """
            SELECT max(cal_date)=%s AS is_week_end
            FROM trade_cal
            WHERE exchange='SSE' AND is_open=1
              AND date_trunc('week', cal_date)=date_trunc('week', %s::date)
            """,
            (target, target),
        )[0]
        if bool(result.get("is_week_end")):
            return None
        return {
            **evidence,
            "scope": "conditional_schedule_skip",
            "empty": True,
            "skip_reason": "scheduled_date_is_not_week_end_trade_day",
            "target_date": target.isoformat(),
        }
    if rows_fetched <= 0:
        return None

    if schedule_id == "stock_basic_daily":
        result = query(
            """
            SELECT count(*) AS row_count,
                   array_agg(DISTINCT list_status ORDER BY list_status) AS statuses
            FROM stock_basic
            """,
            (),
        )[0]
        statuses = set(result.get("statuses") or ())
        if int(result["row_count"] or 0) != rows_fetched or not {"L", "D"} <= statuses:
            return None
        return {
            **evidence,
            "scope": "atomic_snapshot",
            "requested_statuses": ["L", "D", "P"],
            "observed_statuses": sorted(statuses),
        }

    if schedule_id == "trade_cal_daily":
        start = target - timedelta(days=3650)
        end = target + timedelta(days=366)
        expected_per_exchange = (end - start).days + 1
        result = query(
            """
            SELECT exchange, count(*) AS row_count
            FROM trade_cal
            WHERE cal_date BETWEEN %s AND %s AND exchange IN ('SSE', 'SZSE')
            GROUP BY exchange
            """,
            (start, end),
        )
        counts = {row["exchange"]: int(row["row_count"]) for row in result}
        if counts != {"SSE": expected_per_exchange, "SZSE": expected_per_exchange}:
            return None
        if sum(counts.values()) != rows_fetched:
            return None
        return {
            **evidence,
            "scope": "bounded_exchange_calendar",
            "requested_start": start.isoformat(),
            "requested_end": end.isoformat(),
            "exchange_rows": counts,
        }

    if schedule_id == "index_basic_weekly":
        result = query(
            """
            SELECT count(*) AS row_count,
                   count(*) FILTER (WHERE market='CSI') AS csi_rows,
                   array_agg(DISTINCT market ORDER BY market) AS markets
            FROM index_basic
            """,
            (),
        )[0]
        stored = int(result["row_count"] or 0)
        csi_rows = int(result["csi_rows"] or 0)
        markets = set(result.get("markets") or ())
        if (
            stored != rows_fetched
            or csi_rows <= 8000
            or not {"CSI", "SSE", "SZSE", "SW"} <= markets
        ):
            return None
        return {
            **evidence,
            "scope": "atomic_market_category_snapshot",
            "stored_rows": stored,
            "csi_rows": csi_rows,
            "observed_markets": sorted(markets),
            "response_boundary": 8000,
        }

    snapshot_by_schedule = {
        "fx_obasic_weekly": (
            "fx_obasic",
            "classify",
            {"FX", "INDEX", "COMMODITY", "BUND", "CRYPTO", "FX_BASKET"},
            None,
        ),
        "sge_basic_weekly": ("sge_basic", None, set(), 1000),
        "stock_company_weekly": (
            "stock_company", "exchange", {"SSE", "SZSE", "BSE"}, 4500,
        ),
    }
    if schedule_id in snapshot_by_schedule:
        table, partition_column, required_partitions, per_partition_cap = (
            snapshot_by_schedule[schedule_id]
        )
        if partition_column:
            result = query(
                f"SELECT {partition_column} AS partition, count(*) AS row_count "
                f"FROM {table} GROUP BY {partition_column}",
                (),
            )
            counts = {
                str(row["partition"]): int(row["row_count"] or 0) for row in result
            }
            stored = sum(counts.values())
            if not required_partitions <= set(counts):
                return None
            if per_partition_cap and any(
                count >= per_partition_cap for count in counts.values()
            ):
                return None
        else:
            result = query(f"SELECT count(*) AS row_count FROM {table}", ())[0]
            stored = int(result["row_count"] or 0)
            counts = {}
            if per_partition_cap and stored >= per_partition_cap:
                return None
        if stored != rows_fetched:
            return None
        return {
            **evidence,
            "scope": "bounded_reference_snapshot",
            "stored_rows": stored,
            "partition_rows": counts,
            "response_boundary_per_partition": per_partition_cap,
        }

    top10_by_schedule = {
        "hsgt_top10_daily": {1, 3},
        "ggt_top10_daily": {2, 4},
    }
    if schedule_id in top10_by_schedule:
        table = schedule_id.removesuffix("_daily")
        result = query(
            f"""
            SELECT market_type, count(*) AS row_count FROM {table}
            WHERE trade_date=%s GROUP BY market_type
            """,
            (target,),
        )
        counts = {
            int(row["market_type"]): int(row["row_count"] or 0) for row in result
        }
        if set(counts) != top10_by_schedule[schedule_id]:
            return None
        if sum(counts.values()) != rows_fetched or any(
            count < 1 or count > 10 for count in counts.values()
        ):
            return None
        return {
            **evidence,
            "scope": "exact_trade_date_market_types",
            "target_date": target.isoformat(),
            "partition_rows": counts,
        }

    if schedule_id == "ggt_daily_daily":
        start = target - timedelta(days=3)
        result = query(
            "SELECT count(*) AS row_count FROM ggt_daily "
            "WHERE trade_date BETWEEN %s AND %s",
            (start, target),
        )[0]
        stored = int(result["row_count"] or 0)
        if stored != rows_fetched or stored > 4:
            return None
        return {
            **evidence,
            "scope": "bounded_calendar_window",
            "requested_start": start.isoformat(),
            "requested_end": target.isoformat(),
            "stored_rows": stored,
        }

    if schedule_id == "ggt_monthly_daily":
        start_month = (target.replace(day=1) - timedelta(days=90)).strftime("%Y%m")
        end_month = target.strftime("%Y%m")
        result = query(
            "SELECT count(*) AS row_count FROM ggt_monthly "
            "WHERE month BETWEEN %s AND %s",
            (start_month, end_month),
        )[0]
        stored = int(result["row_count"] or 0)
        if stored != rows_fetched or stored > 4:
            return None
        return {
            **evidence,
            "scope": "bounded_month_window",
            "requested_start_month": start_month,
            "requested_end_month": end_month,
            "stored_rows": stored,
        }

    if schedule_id == "new_share_weekly":
        start = target - timedelta(days=30)
        end = target + timedelta(days=7)
        result = query(
            "SELECT count(*) AS row_count FROM new_share "
            "WHERE ipo_date BETWEEN %s AND %s",
            (start, end),
        )[0]
        stored = int(result["row_count"] or 0)
        if stored != rows_fetched:
            return None
        return {
            **evidence,
            "scope": "bounded_ipo_window",
            "requested_start": start.isoformat(),
            "requested_end": end.isoformat(),
            "stored_rows": stored,
        }

    stock_periodic_scopes = {
        "stk_weekly_weekly_fri": ("week", "weekly"),
        "stk_weekly_monthly_week_daily": ("week", "stk_weekly_monthly"),
        "stk_weekly_monthly_month_daily": ("month", "stk_weekly_monthly"),
        "stk_monthly_monthly_eom": ("month", "monthly"),
    }
    if schedule_id in stock_periodic_scopes:
        frequency, source = stock_periodic_scopes[schedule_id]
        result = query(
            """
            SELECT count(*) AS row_count FROM stk_weekly_monthly
            WHERE trade_date=%s AND freq=%s AND source=%s
            """,
            (target, frequency, source),
        )[0]
        stored = int(result["row_count"] or 0)
        documented_cap = 6000
        if stored != rows_fetched or stored >= documented_cap:
            return None
        return {
            **evidence,
            "scope": "exact_stock_period_frequency_source",
            "target_date": target.isoformat(),
            "frequency": frequency,
            "source": source,
            "stored_rows": stored,
            "documented_row_limit": documented_cap,
        }

    table_by_schedule = {
        # ``bak_basic`` is an independent historical snapshot, not the
        # ``daily_basic`` dataset. Prove the exact persisted trading-day scope
        # here so it never enters coverage verification under the wrong table.
        # A full A-share universe is safely below the documented/default
        # 10,000-row response boundary; equality remains ambiguous.
        "bak_basic_daily": ("bak_basic", "trade_date", 10000),
        "suspend_d_daily": ("suspend_d", "trade_date", None),
        "stock_st_daily": ("stock_st", "trade_date", 1000),
        # Both interfaces are single, exact-date market snapshots. Their
        # observed universes are safely below the provider's default 1,000-row
        # boundary; equality would therefore be ambiguous and stays unverified.
        "index_global_daily": ("index_global", "trade_date", 1000),
        "ths_daily_daily": ("ths_daily", "trade_date", 1000),
    }
    if schedule_id in table_by_schedule:
        table, date_column, hard_cap = table_by_schedule[schedule_id]
        result = query(
            f"SELECT count(*) AS row_count FROM {table} WHERE {date_column}=%s",
            (target,),
        )[0]
        stored = int(result["row_count"] or 0)
        if stored != rows_fetched or (hard_cap and rows_fetched >= hard_cap):
            return None
        return {
            **evidence,
            "scope": "exact_trade_date",
            "target_date": target.isoformat(),
            "stored_rows": stored,
            "response_boundary": hard_cap,
        }

    window_by_schedule = {
        # The dedicated collectors iterate the complete local symbol universe
        # and re-fetch an inclusive calendar window for each symbol. Any
        # request exception fails the job, so exact stored/fetched equality
        # proves that every successful response reached normalized storage.
        "fx_daily_daily": ("fx_daily", "fx_obasic", 7),
        "sge_daily_daily": ("sge_daily", "sge_basic", 10),
    }
    if schedule_id in window_by_schedule:
        table, reference_table, lookback_days = window_by_schedule[schedule_id]
        start = target - timedelta(days=lookback_days)
        result = query(
            f"""
            SELECT count(*) AS row_count,
                   count(DISTINCT ts_code) AS observed_symbols,
                   (SELECT count(*) FROM {reference_table}) AS reference_symbols
            FROM {table}
            WHERE trade_date BETWEEN %s AND %s
            """,
            (start, target),
        )[0]
        stored = int(result["row_count"] or 0)
        reference_symbols = int(result["reference_symbols"] or 0)
        observed_symbols = int(result["observed_symbols"] or 0)
        if (
            stored != rows_fetched
            or reference_symbols <= 0
            or observed_symbols > reference_symbols
        ):
            return None
        return {
            **evidence,
            "scope": "dependency_universe_window",
            "requested_start": start.isoformat(),
            "requested_end": target.isoformat(),
            "stored_rows": stored,
            "reference_symbols": reference_symbols,
            "observed_symbols": observed_symbols,
        }

    if schedule_id == "stock_hsgt_daily":
        result = query(
            """
            SELECT type, count(*) AS row_count
            FROM stock_hsgt WHERE trade_date=%s GROUP BY type
            """,
            (target,),
        )
        counts = {row["type"]: int(row["row_count"]) for row in result}
        expected_types = {"HK_SZ", "SZ_HK", "HK_SH", "SH_HK"}
        if set(counts) != expected_types or sum(counts.values()) != rows_fetched:
            return None
        if any(count >= 2000 for count in counts.values()):
            return None
        return {
            **evidence,
            "scope": "bounded_hsgt_type_partitions",
            "target_date": target.isoformat(),
            "partition_rows": counts,
            "documented_row_limit_per_partition": 2000,
        }

    return None
