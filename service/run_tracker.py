"""
=============================================================================
sys_collector_run 任务运行记录管理器
=============================================================================

用法：
    from service.run_tracker import track_run

    @track_run(task_id="daily_daily", task_name="A股日线行情-盘后全量", trigger_type="cron")
    def run_daily():
        ...

或者手动调用：
    run_id = start_run(task_id="daily_daily", ...)
    ...
    finish_run(run_id, status="success", rows_inserted=1000)
"""

import json
import traceback
from datetime import datetime, timezone
from functools import wraps
from typing import Optional

import psycopg2
import psycopg2.extras

from service.db import DB_CONFIG


def _get_next_trade_date() -> Optional[str]:
    """
    获取最近的一个交易日（从 trade_cal 查今天或之前的最近交易日）。
    如果今天就是交易日，返回今天；否则返回上一个交易日。
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT cal_date FROM trade_cal
                    WHERE cal_date <= CURRENT_DATE AND is_open = 1
                    ORDER BY cal_date DESC LIMIT 1
                """)
                row = cur.fetchone()
                return str(row[0]) if row else None
        finally:
            conn.close()
    except Exception:
        return None


def start_run(task_id: str, task_name: str, trigger_type: str = "cron",
              trade_date: str = None, extra_info: dict = None) -> int:
    """
    创建一条运行记录，返回 run_id。
    """
    if not trade_date:
        trade_date = _get_next_trade_date()

    extra_json = json.dumps(extra_info, ensure_ascii=False) if extra_info else None

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sys_collector_run
                    (task_id, task_name, trigger_type, trade_date, status, extra_info)
                VALUES (%s, %s, %s, %s, 'running', %s::jsonb)
                RETURNING run_id
                """,
                (task_id, task_name, trigger_type, trade_date, extra_json)
            )
            run_id = cur.fetchone()[0]
        conn.commit()
        return run_id
    finally:
        conn.close()


def finish_run(run_id: int, status: str = "success",
               rows_inserted: int = 0, retry_count: int = 0,
               error_message: str = None, extra_info: dict = None):
    """
    更新运行记录的状态和结果。
    status: success / failed / timeout / skipped
    """
    finished_at = datetime.now(timezone.utc)
    duration_sec = None

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        # 先查询 started_at 计算耗时
        with conn.cursor() as cur:
            cur.execute(
                "SELECT started_at FROM sys_collector_run WHERE run_id = %s",
                (run_id,)
            )
            row = cur.fetchone()
            if row:
                # row[0] 可能有时区信息也可能没有，统一处理
                started = row[0]
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                delta = finished_at - started
                duration_sec = int(delta.total_seconds())
                if duration_sec < 0:
                    duration_sec = 0  # 防止时区导致的负值

        extra_json = json.dumps(extra_info, ensure_ascii=False) if extra_info else None

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sys_collector_run SET
                    status = %s,
                    finished_at = %s,
                    duration_sec = %s,
                    rows_inserted = %s,
                    retry_count = %s,
                    error_message = %s,
                    extra_info = COALESCE(%s::jsonb, extra_info)
                WHERE run_id = %s
                """,
                (status, finished_at, duration_sec, rows_inserted,
                 retry_count, error_message, extra_json, run_id)
            )
        conn.commit()
    finally:
        conn.close()


def track_run(task_id: str, task_name: str, trigger_type: str = "cron"):
    """
    装饰器：自动包裹任务函数，创建运行记录、捕获异常、更新结果。

    用法：
        @track_run(task_id="daily_daily", task_name="A股日线行情")
        def run_daily():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            run_id = start_run(task_id, task_name, trigger_type)
            retry_count = 0
            try:
                result = func(*args, **kwargs, _run_id=run_id) if hasattr(func, '__code__') and '_run_id' in func.__code__.co_varnames else func(*args, **kwargs)
                rows = result if isinstance(result, int) else 0
                finish_run(run_id, status="success", rows_inserted=rows)
            except Exception as e:
                retry_count = getattr(e, 'retry_count', 0)
                error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
                finish_run(run_id, status="failed", rows_inserted=0,
                          retry_count=retry_count, error_message=error_msg)
                raise
            return result
        return wrapper
    return decorator


def get_latest_runs(task_id: str = None, status: str = None, limit: int = 20) -> list[dict]:
    """
    查询最新运行记录，用于监控面板。
    """
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            where_clauses = []
            params = []
            if task_id:
                where_clauses.append("task_id = %s")
                params.append(task_id)
            if status:
                where_clauses.append("status = %s")
                params.append(status)

            where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

            cur.execute(
                f"""
                SELECT run_id, task_id, task_name, trigger_type,
                       trade_date, status,
                       started_at, finished_at, duration_sec,
                       rows_inserted, retry_count, error_message
                FROM sys_collector_run
                WHERE {where_sql}
                ORDER BY started_at DESC
                LIMIT %s
                """,
                params + [limit]
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()


def check_timeout_tasks(timeout_minutes: int = 30) -> list[dict]:
    """
    检查所有 running 状态但超时未完成的任务。
    返回超时任务列表，自动标记为 timeout。
    """
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE sys_collector_run
                SET status = 'timeout',
                    finished_at = NOW(),
                    error_message = '自动超时标记（超过 %s 分钟未完成）'
                WHERE status = 'running'
                  AND started_at < NOW() - INTERVAL '%s minutes'
                RETURNING run_id, task_id, task_name, started_at
                """,
                (timeout_minutes, timeout_minutes)
            )
            rows = cur.fetchall()
            conn.commit()
            return [dict(r) for r in rows]
    finally:
        conn.close()


def count_failed_tasks(since_hours: int = 24) -> list[dict]:
    """
    统计最近 N 小时内各任务的失败次数。
    """
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT task_id, task_name, status, count(*) as cnt
                FROM sys_collector_run
                WHERE started_at > NOW() - INTERVAL '%s hours'
                  AND status IN ('failed', 'timeout')
                GROUP BY task_id, task_name, status
                ORDER BY cnt DESC
                """,
                (since_hours,)
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    finally:
        conn.close()
