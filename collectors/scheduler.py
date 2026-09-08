"""
=============================================================================
claw-quant-data 定时调度器
=============================================================================

基于 APScheduler，统一管理所有采集任务的触发时间和调度逻辑。
每次任务执行都会记录到 sys_collector_run 表，支持运行状态追溯。

调度策略：
  trade_cal     → 每天 08:30 运行一次，取当日往后一个月
  stock_basic   → 每天 08:30 全量刷新
  stock_st      → 交易日 09:20
  stock_hsgt    → 交易日 09:20
  stock_company → 每周一 08:30
  new_share     → 每周一 08:30
  daily         → 交易日 16:00（盘后全量）
  bak_basic     → 交易日 16:00（盘后全量）

启动方式：
  python3.11 collectors/scheduler.py

运行记录查询：
  SELECT * FROM sys_collector_run ORDER BY started_at DESC LIMIT 20;
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
from collections.abc import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

from collectors.base import setup_logger, get_config
from service.run_tracker import track_run, check_timeout_tasks, count_failed_tasks, get_latest_runs
from service.config import SCHEDULE_RECONCILE_LOOKBACK_DAYS
from service.clock import business_now
from service.tushare_scheduling import DEDICATED_API_BY_RUN_ID


logger = setup_logger("scheduler")


# APScheduler is deliberately only a trigger/dispatcher. The original
# collection callables are kept in this process-local whitelist so the durable
# worker can execute them by schedule id without accepting arbitrary imports.
_SCHEDULED_COLLECTION_TASKS: dict[str, Callable[[], int]] = {}
_CONTROL_JOB_IDS = {
    "inspector_15min",
    "tushare_policy_dispatch",
    "data_coverage_dispatch",
    "service_heartbeat",
    "collection_schedule_reconciler",
    "collection_initialization_reconciler",
    "fanout_campaign_reconciler",
    "delivery_plan_reconciler",
    "scheduled_completion_reconciler",
    "coverage_rule_reconciler",
}
_ACTIVE_SCHEDULER: BackgroundScheduler | None = None
_SCHEDULED_COLLECTION_FUNCTION_NAMES = {
    "bak_basic_daily": "run_bak_basic",
    "balancesheet_quarterly": "run_balancesheet",
    "cashflow_quarterly": "run_cashflow",
    "daily_daily": "run_daily",
    "disclosure_date_quarterly": "run_disclosure_date",
    "express_annual": "run_express",
    "fina_indicator_quarterly": "run_fina_indicator",
    "forecast_seasonal": "run_forecast",
    "fx_daily_daily": "run_fx_daily_daily",
    "fx_obasic_weekly": "run_fx_obasic",
    "ggt_daily_daily": "run_ggt_daily",
    "ggt_monthly_daily": "run_ggt_monthly",
    "ggt_top10_daily": "run_ggt_top10",
    "hsgt_top10_daily": "run_hsgt_top10",
    "income_quarterly": "run_income",
    "index_basic_weekly": "run_index_basic",
    "index_daily_daily": "run_index_daily",
    "index_daily_finalize": "run_index_daily_finalize",
    "index_dailybasic_daily": "run_index_dailybasic",
    "index_global_daily": "run_index_global",
    "mainbz_annual": "run_mainbz",
    "new_share_weekly": "run_new_share",
    "sge_basic_weekly": "run_sge_basic",
    "sge_daily_daily": "run_sge_daily_daily",
    "stk_limit_daily": "run_stk_limit",
    "stk_monthly_monthly_eom": "run_stk_monthly_monthly",
    "stk_weekly_monthly_month_daily": "run_stk_weekly_monthly_month",
    "stk_weekly_monthly_week_daily": "run_stk_weekly_monthly_week",
    "stk_weekly_weekly_fri": "run_stk_weekly_weekly",
    "stock_basic_daily": "run_stock_basic",
    "stock_company_weekly": "run_stock_company",
    "stock_hsgt_daily": "run_stock_hsgt",
    "stock_st_daily": "run_stock_st",
    "suspend_d_daily": "run_suspend_d",
    "ths_daily_daily": "run_ths_daily",
    "trade_cal_daily": "run_trade_cal",
}


def enqueue_scheduled_collection(
    schedule_id: str,
    scheduled_for: datetime | None = None,
    *,
    repository=None,
    cursor_repository=None,
) -> int:
    """Idempotently persist one APScheduler firing for worker execution."""
    from service.initialization.repository import routine_collection_enabled

    if not routine_collection_enabled():
        logger.info("⏸️ 初始化尚未完成，跳过日常专项派发：%s", schedule_id)
        return 0
    from service.collection_jobs.repository import JobRepository
    from service.collection_jobs.registry import TASKS
    from service.collection_jobs.schedules import ScheduleCursorRepository

    fire_time = (scheduled_for or business_now()).replace(
        second=0, microsecond=0
    )
    scope = fire_time.strftime("%Y%m%dT%H%M%z")
    parameters = {
        "schedule_id": schedule_id,
        "scheduled_for": fire_time.isoformat(),
    }
    handler = TASKS.handler_metadata("scheduled_collector", parameters)
    job_repository = repository or JobRepository()
    cursor_store = cursor_repository or ScheduleCursorRepository()
    job, created = job_repository.create(
        "scheduled_collector",
        parameters,
        max_attempts=3,
        idempotency_key=f"scheduled-{schedule_id}-{scope}"[:128],
        api_name=DEDICATED_API_BY_RUN_ID.get(schedule_id),
        cadence="scheduled",
        period_key=scope,
        expected_for=fire_time.date(),
        handler_type=handler.handler_type,
        handler_key=handler.handler_key,
        handler_version=handler.handler_version,
        code_revision=handler.code_revision,
        priority=90,
        resource_class="scheduled",
    )
    cursor_store.advance(
        schedule_id,
        fire_time,
        job_id=job["job_id"],
        handler_key=handler.handler_key,
        handler_version=handler.handler_version,
    )
    if created:
        logger.info("✅ 专项采集任务已持久化：%s (%s)", schedule_id, scope)
    else:
        logger.info("⏭️ 专项采集任务已存在：%s (%s)", schedule_id, scope)
    return int(created)


def execute_scheduled_collection(
    schedule_id: str, scheduled_for: str | None = None
):
    """Execute a whitelisted scheduled collector inside the durable worker."""
    from service.collection_jobs.models import TaskExecutionResult
    from service.clock import business_time

    try:
        function_name = _SCHEDULED_COLLECTION_FUNCTION_NAMES[schedule_id]
        task = globals()[function_name]
    except KeyError as exc:
        raise ValueError(f"unknown scheduled collector: {schedule_id}") from exc
    with business_time(scheduled_for):
        rows = int(task() or 0)
    from service.collection_jobs.scheduled_verification import (
        verify_scheduled_transport,
    )

    strict_evidence = verify_scheduled_transport(
        schedule_id, scheduled_for, rows
    )
    if strict_evidence:
        return TaskExecutionResult(
            rows_inserted=rows,
            rows_fetched=rows,
            completion_status=(
                "empty" if strict_evidence.get("empty") else "complete"
            ),
            completion_evidence=strict_evidence,
        )
    return TaskExecutionResult(
        rows_inserted=rows,
        rows_fetched=rows,
        completion_status="unverified",
        completion_evidence={
            "verified": False,
            "reason": (
                "dedicated collector returned zero; this can mean an upstream "
                "empty result or a non-trading-day no-op, so it is not proof of empty"
                if rows == 0
                else "dedicated collector execution completed; coverage audit is required"
            ),
            **(
                {"zero_result_reason": "scheduled_collector_zero_is_ambiguous"}
                if rows == 0 else {}
            ),
            "schedule_id": schedule_id,
            "scheduled_for": scheduled_for,
            "callable": function_name,
        },
    )


def scheduled_collection_ids() -> frozenset[str]:
    return frozenset(_SCHEDULED_COLLECTION_FUNCTION_NAMES)


def _latest_fire_times_by_date(
    trigger,
    start: datetime,
    end: datetime,
) -> list[datetime]:
    """Return the latest trigger occurrence for every missed business date.

    Keeping only one occurrence per date avoids replaying every hourly retry,
    while retaining Friday when a scheduler comes back on Saturday or Sunday.
    The old single-latest implementation could let a harmless weekend skip
    conceal a genuinely missed trading-day collection.
    """
    latest_by_date: dict[object, datetime] = {}
    fire_time = trigger.get_next_fire_time(None, start)
    while fire_time is not None and fire_time <= end:
        latest_by_date[fire_time.date()] = fire_time
        fire_time = trigger.get_next_fire_time(
            fire_time, fire_time + timedelta(microseconds=1)
        )
    return [latest_by_date[key] for key in sorted(latest_by_date)]


def reconcile_collection_schedules(
    scheduler: BackgroundScheduler | None = None,
    *,
    now: datetime | None = None,
    cursor_repository=None,
) -> int:
    """Submit every missed date for every dedicated schedule.

    A cursor with no durable job is an installation-era bootstrap marker, not
    proof that collection happened.  Such cursors are reconciled from the
    bounded lookback window just like a newly discovered schedule.
    """
    from service.initialization.repository import routine_collection_enabled

    if not routine_collection_enabled():
        return 0
    from service.collection_jobs.registry import TASKS
    from service.collection_jobs.schedules import ScheduleCursorRepository

    active = scheduler or _ACTIVE_SCHEDULER
    if active is None:
        raise RuntimeError("collection scheduler is not initialized")
    current = now or business_now()
    cursors = cursor_repository or ScheduleCursorRepository()
    submitted = 0
    for job in active.get_jobs():
        if job.id in _CONTROL_JOB_IDS:
            continue
        cursor = cursors.get(job.id)
        if cursor is None or cursor.get("last_job_id") is None:
            missed = _latest_fire_times_by_date(
                job.trigger,
                current - timedelta(days=SCHEDULE_RECONCILE_LOOKBACK_DAYS),
                current,
            )
            if missed:
                for fire_time in missed:
                    submitted += enqueue_scheduled_collection(
                        job.id,
                        fire_time,
                        cursor_repository=cursors,
                    )
            elif cursor is None:
                # No occurrence exists inside the deliberately bounded replay
                # window. Seed at the current time to avoid repeatedly scanning
                # old history; the next real firing will advance the cursor.
                parameters = {
                    "schedule_id": job.id,
                    "scheduled_for": current.isoformat(),
                }
                handler = TASKS.handler_metadata("scheduled_collector", parameters)
                cursors.bootstrap(
                    job.id,
                    current,
                    handler_key=handler.handler_key,
                    handler_version=handler.handler_version,
                )
            continue
        after = cursor["last_dispatched_for"] + timedelta(microseconds=1)
        for fire_time in _latest_fire_times_by_date(job.trigger, after, current):
            submitted += enqueue_scheduled_collection(
                job.id,
                fire_time,
                cursor_repository=cursors,
            )
    return submitted


def run_collection_schedule_reconciler() -> None:
    submitted = reconcile_collection_schedules()
    if submitted:
        logger.warning("♻️ 已补发 %s 个错过的专项采集任务", submitted)


def run_scheduled_completion_reconciler() -> None:
    from service.collection_jobs.scheduled_reconciliation import (
        ScheduledCompletionReconciler,
    )

    result = ScheduledCompletionReconciler().reconcile()
    if result["promoted"] or result["audits_queued"]:
        logger.info(
            "🔎 专项完成证据对账：严格完成 %s，进入覆盖审计 %s",
            result["promoted"],
            result["audits_queued"],
        )


def run_coverage_rule_reconciler() -> None:
    """Re-audit results made obsolete by a versioned coverage-rule fix."""
    from service.data_coverage.reconciliation import CoverageRuleReconciler

    requeued = CoverageRuleReconciler().reconcile()
    if requeued:
        logger.warning("🧭 覆盖规则升级重审：%s", requeued)


def _durabilize_collection_jobs(scheduler: BackgroundScheduler) -> None:
    """Replace direct collection execution with durable queue submissions."""
    _SCHEDULED_COLLECTION_TASKS.clear()
    for job in scheduler.get_jobs():
        if job.id in _CONTROL_JOB_IDS:
            continue
        _SCHEDULED_COLLECTION_TASKS[job.id] = job.func
        scheduler.modify_job(
            job.id,
            func=enqueue_scheduled_collection,
            args=(job.id,),
            kwargs={},
        )
    if set(_SCHEDULED_COLLECTION_TASKS) != set(_SCHEDULED_COLLECTION_FUNCTION_NAMES):
        missing = set(_SCHEDULED_COLLECTION_FUNCTION_NAMES) - set(_SCHEDULED_COLLECTION_TASKS)
        unexpected = set(_SCHEDULED_COLLECTION_TASKS) - set(_SCHEDULED_COLLECTION_FUNCTION_NAMES)
        raise RuntimeError(
            f"scheduled collector whitelist mismatch: missing={sorted(missing)}, "
            f"unexpected={sorted(unexpected)}"
        )


# ──────────────────────────────────────────────
# 交易日判断
# ──────────────────────────────────────────────
def _is_trade_day(date_str: str) -> bool:
    """检查某个日期是否为交易日（查已入库的 trade_cal）"""
    from service.db import query
    rows = query(
        "SELECT 1 FROM trade_cal WHERE cal_date = %s AND is_open = 1 LIMIT 1",
        (date_str,)
    )
    return len(rows) > 0


# ──────────────────────────────────────────────
# 每个采集任务是一个独立函数
# ──────────────────────────────────────────────
@track_run(task_id="trade_cal_daily", task_name="交易日历-每日更新", trigger_type="cron")
def run_trade_cal():
    """Maintain a bounded ten-year calendar plus one future year."""
    from collectors.stock.basic.trade_cal import TradeCalCollector
    from service.run_tracker import start_run, finish_run
    now = business_now()
    start = (now - timedelta(days=3650)).strftime("%Y%m%d")
    end = (now + timedelta(days=366)).strftime("%Y%m%d")
    total = 0
    for ex in ["SSE", "SZSE"]:
        c = TradeCalCollector()
        rows = c.collect(exchange=ex, start_date=start, end_date=end)
        logger.info(f"  ✅ trade_cal({ex}, {start}~{end}): {rows} 行")
        total += rows
    return total


@track_run(task_id="stock_st_daily", task_name="ST股票列表-每日更新", trigger_type="cron")
def run_stock_st():
    """ST股票列表+风险警示板明细：每天 09:20 跑（只限交易日）"""
    today = business_now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 stock_st")
        return 0
    from collectors.stock.basic.stock_st import StockSTCollector
    c = StockSTCollector()
    rows = c.collect(trade_date=today)
    logger.info(f"  ✅ stock_st({today}): {rows} 行")
    return rows


@track_run(task_id="stock_hsgt_daily", task_name="沪深港通列表-每日更新", trigger_type="cron")
def run_stock_hsgt():
    """沪深港通股票列表：每天 09:20 跑（只限交易日）"""
    today = business_now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 stock_hsgt")
        return 0
    from collectors.stock.basic.stock_hsgt import StockHsgtCollector
    total = 0
    for t in ["HK_SZ", "SZ_HK", "HK_SH", "SH_HK"]:
        c = StockHsgtCollector()
        rows = c.collect(trade_date=today, type=t)
        logger.info(f"  ✅ stock_hsgt({t}): {rows} 行")
        total += rows
    logger.info(f"✅ stock_hsgt({today}) 合计: {total} 行")
    return total


@track_run(task_id="stk_limit_daily", task_name="每日涨跌停价格-盘前更新", trigger_type="cron")
def run_stk_limit():
    """每日涨跌停价格：交易日 09:00 跑（数据 08:40 已更新）"""
    today = business_now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 stk_limit")
        return 0
    from collectors.stock.market.stk_limit import STKLimitCollector
    from service.tushare_policy import TusharePolicyRegistry

    c = STKLimitCollector()
    policy = TusharePolicyRegistry().get("stk_limit")
    result = c.run_offset_paginated(
        page_size=policy.page_size,
        max_pages=policy.max_pages,
        trade_date=today,
    )
    cnt = result.stored_rows
    logger.info(f"  ✅ stk_limit({today}): {cnt} 行")
    return cnt


@track_run(task_id="suspend_d_daily", task_name="每日停复牌信息-盘前更新", trigger_type="cron")
def run_suspend_d():
    """每日停复牌信息：交易日 09:10 跑"""
    today = business_now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 suspend_d")
        return 0
    from collectors.stock.market.suspend_d import SuspendDCollector
    c = SuspendDCollector()
    cnt = c.collect(trade_date=today)
    logger.info(f"  ✅ suspend_d({today}): {cnt} 条")
    return cnt


@track_run(task_id="hsgt_top10_daily", task_name="沪深股通十大成交股-盘后更新", trigger_type="cron")
def run_hsgt_top10():
    """沪深股通十大成交股：交易日 20:00 跑"""
    today = business_now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 hsgt_top10")
        return 0
    from collectors.stock.market.hsgt_top10 import HsgtTop10Collector
    c = HsgtTop10Collector()
    cnt = c.collect(trade_date=today)
    logger.info(f"  ✅ hsgt_top10({today}): {cnt} 条")
    return cnt


@track_run(task_id="ggt_top10_daily", task_name="港股通十大成交股-盘后更新", trigger_type="cron")
def run_ggt_top10():
    """港股通十大成交股：交易日 20:00 跑"""
    today = business_now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 ggt_top10")
        return 0
    from collectors.stock.market.ggt_top10 import GgtTop10Collector
    c = GgtTop10Collector()
    cnt = c.collect(trade_date=today)
    logger.info(f"  ✅ ggt_top10({today}): {cnt} 条")
    return cnt


@track_run(task_id="ggt_daily_daily", task_name="港股通每日成交统计-盘后更新", trigger_type="cron")
def run_ggt_daily():
    """港股通每日成交统计：交易日 20:00 跑（取近2天防遗漏）"""
    from collectors.stock.market.ggt_daily import GgtDailyCollector
    today = business_now().strftime("%Y%m%d")
    yesterday = (business_now() - timedelta(days=3)).strftime("%Y%m%d")
    c = GgtDailyCollector()
    cnt = c.collect(start_date=yesterday, end_date=today)
    logger.info(f"  ✅ ggt_daily({today}): {cnt} 条")
    return cnt


@track_run(task_id="ggt_monthly_daily", task_name="港股通每月成交统计-盘后更新", trigger_type="cron")
def run_ggt_monthly():
    """港股通每月成交统计：交易日 20:00 跑（取近3个月）"""
    from collectors.stock.market.ggt_monthly import GgtMonthlyCollector
    today = business_now()
    start_m = (today.replace(day=1) - timedelta(days=90)).strftime("%Y%m")
    end_m = today.strftime("%Y%m")
    c = GgtMonthlyCollector()
    cnt = c.collect(start_month=start_m, end_month=end_m)
    logger.info(f"  ✅ ggt_monthly({end_m}): {cnt} 条")
    return cnt


@track_run(task_id="stk_weekly_monthly_week", task_name="周线行情-盘后更新", trigger_type="cron")
def run_stk_weekly_monthly_week():
    """周线行情：每个交易日 20:30 用 stk_weekly_monthly 更新"""
    from collectors.stock.market.stk_weekly_monthly import StkWeeklyMonthlyCollector
    today = business_now()
    ds = today.strftime("%Y%m%d")
    c = StkWeeklyMonthlyCollector()
    df = c.fetch_daily(ds, "week")
    if df is not None:
        c.save_daily(df, ds, "week")
        cnt = len(df)
    else:
        cnt = 0
    logger.info(f"  ✅ stk_weekly_monthly(week {ds}): {cnt} 行")
    return cnt


@track_run(task_id="stk_weekly_monthly_month", task_name="月线行情-盘后更新", trigger_type="cron")
def run_stk_weekly_monthly_month():
    """月线行情：每个交易日 20:35 用 stk_weekly_monthly 更新（仅月末）"""
    from collectors.stock.market.stk_weekly_monthly import StkWeeklyMonthlyCollector
    from service.db import query
    today = business_now().strftime("%Y%m%d")
    rows = query(f"""
        SELECT cal_date FROM trade_cal
        WHERE exchange='SSE' AND is_open=1
        AND date_trunc('month', cal_date::date) = date_trunc('month', DATE '{today}')
        ORDER BY cal_date DESC LIMIT 1
    """)
    if not rows or rows[0]['cal_date'].strftime("%Y%m%d") != today:
        logger.info(f"⏭️  {today} 不是月末交易日，跳过月线")
        return 0
    c = StkWeeklyMonthlyCollector()
    df = c.fetch_daily(today, "month")
    if df is not None:
        c.save_daily(df, today, "month")
        cnt = len(df)
    else:
        cnt = 0
    logger.info(f"  ✅ stk_weekly_monthly(month {today}): {cnt} 行")
    return cnt


@track_run(task_id="stk_weekly_weekly_fri", task_name="周线行情-周收盘校订", trigger_type="cron")
def run_stk_weekly_weekly():
    """周线行情：周五 20:40 用 weekly 接口覆盖"""
    from collectors.stock.market.stk_weekly_monthly import StkWeeklyMonthlyCollector
    today = business_now().strftime("%Y%m%d")
    c = StkWeeklyMonthlyCollector()
    df = c.fetch_weekly(today)
    if df is not None:
        c.save_weekly(df, today)
        cnt = len(df)
    else:
        cnt = 0
    logger.info(f"  ✅ weekly(fri {today}): {cnt} 行")
    return cnt


@track_run(task_id="stk_monthly_monthly_eom", task_name="月线行情-月收盘校订", trigger_type="cron")
def run_stk_monthly_monthly():
    """月线行情：月末交易日 20:45 用 monthly 接口覆盖"""
    from collectors.stock.market.stk_weekly_monthly import StkWeeklyMonthlyCollector
    from service.db import query
    today = business_now().strftime("%Y%m%d")
    rows = query(f"""
        SELECT cal_date FROM trade_cal
        WHERE exchange='SSE' AND is_open=1
        AND date_trunc('month', cal_date::date) = date_trunc('month', DATE '{today}')
        ORDER BY cal_date DESC LIMIT 1
    """)
    if not rows or rows[0]['cal_date'].strftime("%Y%m%d") != today:
        logger.info(f"⏭️  {today} 不是月末交易日，跳过月线校订")
        return 0
    c = StkWeeklyMonthlyCollector()
    df = c.fetch_monthly(today)
    if df is not None:
        c.save_monthly(df, today)
        cnt = len(df)
    else:
        cnt = 0
    logger.info(f"  ✅ monthly(eom {today}): {cnt} 行")
    return cnt


@track_run(task_id="new_share_weekly", task_name="IPO新股列表-每周更新", trigger_type="cron")
def run_new_share():
    """IPO新股列表：每周补一次（近1个月增量）。"""
    from collectors.stock.basic.new_share import NewShareCollector
    start = (business_now() - timedelta(days=30)).strftime("%Y%m%d")
    end = (business_now() + timedelta(days=7)).strftime("%Y%m%d")
    c = NewShareCollector()
    rows = c.collect(start_date=start, end_date=end)
    logger.info(f"  ✅ new_share({start}~{end}): {rows} 行")
    return rows


@track_run(task_id="stock_basic_daily", task_name="股票基础信息-每日全量", trigger_type="cron")
def run_stock_basic():
    """股票基础信息：每天全量刷新，非交易日同样可运行。"""
    from collectors.stock.basic.stock_basic import StockBasicCollector
    c = StockBasicCollector()
    rows = c.collect()
    logger.info(f"  ✅ stock_basic: {rows} 行")
    return rows


@track_run(task_id="stock_company_weekly", task_name="上市公司基本信息-每周更新", trigger_type="cron")
def run_stock_company():
    """上市公司基本信息：每周一次全量覆盖。"""
    from collectors.stock.basic.stock_company import StockCompanyCollector
    total = 0
    for ex in ["SSE", "SZSE", "BSE"]:
        c = StockCompanyCollector()
        rows = c.collect(exchange=ex)
        logger.info(f"  ✅ stock_company({ex}): {rows} 行")
        total += rows
    logger.info(f"✅ stock_company 合计: {total} 行")
    return total


@track_run(task_id="bak_basic_daily", task_name="股票每日基本面-盘后更新", trigger_type="cron")
def run_bak_basic():
    """股票每日基本面：盘后同日多次幂等刷新（只限交易日）。"""
    today = business_now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 bak_basic")
        return 0
    from collectors.stock.basic.bak_basic import BakBasicCollector
    c = BakBasicCollector()
    rows = c.collect(trade_date=today)
    logger.info(f"  ✅ bak_basic({today}): {rows} 行")
    return rows


@track_run(task_id="income_quarterly", task_name="利润表-季度财报更新", trigger_type="cron")
def run_income():
    """利润表：财报季后自动更新"""
    from collectors.stock.finance.income import IncomeCollector
    today = business_now()
    m = today.month; y = today.year
    if m >= 10:
        period = f"{y}0930"
    elif m >= 7:
        period = f"{y}0630"
    elif m >= 4:
        period = f"{y}0331"
    else:
        period = f"{y-1}1231"

    c = IncomeCollector()
    cnt = c.collect(period=period)
    logger.info(f"  ✅ income({period}): {cnt} 行")
    return cnt


@track_run(task_id="income_bootstrap", task_name="利润表-季度补齐", trigger_type="date")
def run_income_bootstrap():
    """启动时幂等重采所有目标报告期。

    不能用“该报告期已有任意一行”作为完整性判断：中断或旧版本截断都
    会留下非空但不完整的分区。财务采集器本身使用 upsert，因此安全的
    做法是重新穷尽每个有界报告期，并由采集任务保存完整性证据。
    """
    from collectors.stock.finance.income import IncomeCollector
    import time

    c = IncomeCollector()
    periods = []
    for y in range(2020, 2026):
        for m in ['0331', '0630', '0930', '1231']:
            p = f"{y}{m}"
            if p > '20250331':
                break
            if p >= '20200101':
                periods.append(p)

    total = 0
    for p in periods:
        total += c.collect(period=p)
        time.sleep(1)
    if total > 0:
        logger.info(f"  ✅ income_bootstrap: 补齐 {total} 行")
    return total


def _run_finance_quarterly(collector_cls, name):
    """通用：财报季后自动更新某张财务表"""
    today = business_now()
    m = today.month; y = today.year
    if m >= 10:
        period = f"{y}0930"
    elif m >= 7:
        period = f"{y}0630"
    elif m >= 4:
        period = f"{y}0331"
    else:
        period = f"{y-1}1231"

    c = collector_cls()
    cnt = c.collect(period=period)
    logger.info(f"  ✅ {name}({period}): {cnt} 行")
    return cnt


@track_run(task_id="balancesheet_quarterly", task_name="资产负债表-季度更新", trigger_type="cron")
def run_balancesheet():
    from collectors.stock.finance.balancesheet import BalancesheetCollector
    return _run_finance_quarterly(BalancesheetCollector, "资产负债表")


@track_run(task_id="cashflow_quarterly", task_name="现金流量表-季度更新", trigger_type="cron")
def run_cashflow():
    from collectors.stock.finance.cashflow import CashflowCollector
    return _run_finance_quarterly(CashflowCollector, "现金流量表")


@track_run(task_id="fina_indicator_quarterly", task_name="财务指标-季度更新", trigger_type="cron")
def run_fina_indicator():
    from collectors.stock.finance.fina_indicator import FinaIndicatorCollector
    return _run_finance_quarterly(FinaIndicatorCollector, "财务指标")


@track_run(task_id="express_annual", task_name="业绩快报-年报更新", trigger_type="cron")
def run_express():
    """业绩快报通常在1~4月发布"""
    today = business_now()
    m = today.month; y = today.year
    if m < 5:
        period = f"{y-1}1231"
    else:
        logger.info("⏭️  非年报季，跳过业绩快报")
        return 0
    from collectors.stock.finance.express import ExpressCollector
    c = ExpressCollector()
    cnt = c.collect(period=period)
    logger.info(f"  ✅ express({period}): {cnt} 行")
    return cnt


@track_run(task_id="forecast_seasonal", task_name="业绩预告-季度更新", trigger_type="cron")
def run_forecast():
    """业绩预告通常在1月(年报)、4月(Q1)、7月(半年报)、10月(Q3)批量发布"""
    today = business_now()
    m = today.month; y = today.year
    # 预告是按公告日而不是报告期取的，取最近的一个完整报告期
    if m >= 10:
        period = f"{y}0930"
    elif m >= 7:
        period = f"{y}0630"
    elif m >= 4:
        period = f"{y}0331"
    else:
        period = f"{y-1}1231"
    from collectors.stock.finance.forecast import ForecastCollector
    c = ForecastCollector()
    cnt = c.collect(period=period)
    logger.info(f"  ✅ forecast({period}): {cnt} 行")
    return cnt


@track_run(task_id="mainbz_annual", task_name="主营业务构成-年报更新", trigger_type="cron")
def run_mainbz():
    """主营业务构成：年报为主"""
    y = business_now().year
    period = f"{y-1}1231"
    from collectors.stock.finance.fina_mainbz import FinaMainbzCollector
    c = FinaMainbzCollector()
    cnt = c.collect(period=period)
    logger.info(f"  ✅ mainbz({period}): {cnt} 行")
    return cnt


@track_run(task_id="dividend_bootstrap", task_name="分红送股-全量补齐", trigger_type="date")
def run_dividend_bootstrap():
    """分红送股：按股票逐个取（无vip接口），只在启动时补齐"""
    from collectors.stock.finance.dividend import DividendCollector
    from service.db import query
    import pandas as pd

    c = DividendCollector()
    stocks = query("SELECT ts_code FROM stock_basic WHERE list_status IN ('L','D') ORDER BY ts_code")
    if not stocks:
        logger.warning("⚠️  stock_basic 无数据，跳过分红")
        return 0

    total = 0
    for s in stocks:
        code = s['ts_code']
        df = c.fetch(ts_code=code)
        if df is not None and len(df) > 0:
            total += c.store(c.transform(df))

    if total > 0:
        logger.info(f"  ✅ dividend_bootstrap: 补齐 {total} 行")
    return total


@track_run(task_id="disclosure_date_quarterly", task_name="财报披露计划-季度更新", trigger_type="cron")
def run_disclosure_date():
    """财报披露计划：按 end_date 取"""
    today = business_now()
    y = today.year
    # 取当期+展望一个季度
    from collectors.stock.finance.disclosure_date import DisclosureDateCollector
    c = DisclosureDateCollector()
    total = 0
    for p in [f"{y}0331", f"{y}0630", f"{y}0930", f"{y}1231"]:
        total += c.collect(period=p)
    logger.info(f"  ✅ disclosure_date: {total} 行")
    return total


@track_run(task_id="daily_daily", task_name="A股日线行情-盘后全量", trigger_type="cron")
def run_daily():
    """A股日线行情：盘后同日多次幂等获取当日全市场。"""
    today = business_now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 daily")
        return 0
    from collectors.stock.market.daily import DailyCollector
    c = DailyCollector()
    rows = c.collect_by_date(trade_date=today)
    logger.info(f"  ✅ daily({today}): {rows} 行")
    return rows


@track_run(task_id="index_basic_weekly", task_name="指数基本信息-周更新", trigger_type="cron")
def run_index_basic():
    from collectors.index.basic import IndexBasicCollector

    return IndexBasicCollector().collect()


@track_run(task_id="index_daily_daily", task_name="指数日线行情-盘后增量", trigger_type="cron")
def run_index_daily():
    """Index daily: exhaust the full market partition for the trade date."""
    from collectors.index.daily import IndexDailyCollector

    trade_date = business_now().strftime("%Y%m%d")
    if not _is_trade_day(trade_date):
        logger.info(f"⏭️  非交易日({trade_date})，跳过 index_daily")
        return 0
    from service.tushare_policy import TusharePolicyRegistry

    policy = TusharePolicyRegistry().get("index_daily")
    result = IndexDailyCollector().run_offset_paginated(
        trade_date=trade_date,
        page_size=policy.page_size,
        max_pages=policy.max_pages,
    )
    logger.info(
        "  ✅ index_daily(%s): %s 行 / %s 页（已穷尽）",
        trade_date,
        result.stored_rows,
        result.evidence["pages_completed"],
    )
    return result.stored_rows


@track_run(
    task_id="index_daily_finalize",
    task_name="指数日线行情-T+1稳定性复采",
    trigger_type="cron",
)
def run_index_daily_finalize():
    """Recollect the latest closed partition after all index venues publish.

    Same-day offset exhaustion only proves completeness at request time. Some
    index venues publish hundreds of rows later in the evening or next
    morning, so one durable T+1 pass is required before treating the partition
    as stable.
    """
    from collectors.index.daily import IndexDailyCollector
    from service.tushare_policy import TusharePolicyRegistry
    from service.tushare_scheduling import _latest_trade_date

    previous_day = business_now().date() - timedelta(days=1)
    trade_date = _latest_trade_date(previous_day)
    policy = TusharePolicyRegistry().get("index_daily")
    result = IndexDailyCollector().run_offset_paginated(
        trade_date=trade_date,
        page_size=policy.page_size,
        max_pages=policy.max_pages,
    )
    logger.info(
        "  ✅ index_daily T+1(%s): %s 行 / %s 页（已穷尽）",
        trade_date,
        result.stored_rows,
        result.evidence["pages_completed"],
    )
    return result.stored_rows


@track_run(task_id="index_dailybasic_daily", task_name="大盘指数每日指标-盘后增量", trigger_type="cron")
def run_index_dailybasic():
    from collectors.index.dailybasic import IndexDailybasicCollector

    return IndexDailybasicCollector().collect(
        trade_date=business_now().strftime("%Y%m%d")
    )


@track_run(task_id="index_global_daily", task_name="国际指数-盘后增量", trigger_type="cron")
def run_index_global():
    from collectors.index.global_index import IndexGlobalCollector

    return IndexGlobalCollector().collect(
        trade_date=business_now().strftime("%Y%m%d")
    )


@track_run(task_id="ths_daily_daily", task_name="申万行业日线-盘后增量", trigger_type="cron")
def run_ths_daily():
    from collectors.index.ths_daily import ThsDailyCollector

    return ThsDailyCollector().collect(trade_date=business_now().strftime("%Y%m%d"))


@track_run(task_id="fx_obasic_weekly", task_name="外汇基础信息-周更新", trigger_type="cron")
def run_fx_obasic():
    from collectors.forex.fx_obasic import FxObasicCollector

    return FxObasicCollector().collect_full()


@track_run(task_id="fx_daily_daily", task_name="外汇日线-隔日增量", trigger_type="cron")
def run_fx_daily_daily():
    from collectors.forex.fx_daily import FxDailyCollector

    return FxDailyCollector().refresh_latest(days=7)


@track_run(task_id="sge_basic_weekly", task_name="SGE现货基础信息-周更新", trigger_type="cron")
def run_sge_basic():
    from collectors.sge.sge_basic import SgeBasicCollector

    return SgeBasicCollector().collect_full()


@track_run(task_id="sge_daily_daily", task_name="SGE日线-日增量", trigger_type="cron")
def run_sge_daily_daily():
    from collectors.sge.sge_daily import SgeDailyCollector

    return SgeDailyCollector().refresh_latest(days=10)


@track_run(
    task_id="tushare_policy_dispatch",
    task_name="Tushare目录接口-策略补采",
    trigger_type="cron",
)
def run_tushare_policy_dispatch():
    """幂等提交最新日/周/月/季度目录接口任务。

    日任务固定采集最近已完成交易日，避免盘中取得尚未发布的数据；其余
    周期依靠任务幂等键保证重复巡航不会产生重复采集。
    """
    from service.fanout_scheduling import submit_latest_scheduled_fanouts
    from service.tushare_scheduling import submit_latest_policy_batches

    now = business_now()
    # Tushare's daily market datasets are normally published after the close.
    # The 19:10 and 23:10 patrols must target today so Monday data is not first
    # discovered on Tuesday. Earlier patrols retain the closed-day safeguard.
    include_current_daily = now.hour >= 19
    submitted = sum(
        submit_latest_policy_batches(
            today=now.date(),
            include_current_daily=include_current_daily,
        ).values()
    )
    fanout = submit_latest_scheduled_fanouts(
        today=now.date(),
        include_current_daily=include_current_daily,
    )
    submitted += sum(item["created"] for item in fanout.values())
    failed = sum(item["failed"] for item in fanout.values())
    logger.info(
        "✅ Tushare策略补采：新增 %s 个持久化任务，扇出配方失败 %s 个",
        submitted,
        failed,
    )
    return submitted


@track_run(
    task_id="data_coverage_dispatch",
    task_name="数据日期覆盖审计-任务生成",
    trigger_type="cron",
)
def run_data_coverage_dispatch():
    """Submit bounded coverage audits; the auditor performs the heavy queries."""
    from service.initialization.repository import routine_collection_enabled

    if not routine_collection_enabled():
        logger.info("⏸️ 初始化尚未完成，跳过日常覆盖审计派发")
        return 0
    from service.data_coverage.service import submit_scheduled_coverage_audits

    result = submit_scheduled_coverage_audits()
    logger.info(
        "✅ 数据覆盖审计：新增 %s/%s 个持久化任务",
        result["created"],
        result["total"],
    )
    return result["created"]


# ──────────────────────────────────────────────
# 巡检 + 钉钉告警
# ──────────────────────────────────────────────
# 巡检 + 通知（通过 Notifier 抽象层，不绑定具体渠道）
# ──────────────────────────────────────────────
def _send_alert(message: str):
    """通过 Notifier 抽象层发送通知"""
    from service.notifier import Notifier
    try:
        ok = Notifier.send(message, title="数据采集告警")
        if ok:
            logger.info(f"✅ 巡检告警已发送: {message[:60]}...")
        else:
            logger.warning(f"⚠️ 巡检告警发送失败（未配置通知渠道）")
    except Exception as e:
        logger.error(f"❌ 巡检告警异常: {e}")


def run_inspector():
    """
    数据巡检：检查失败/超时任务，发现问题发通知。
    定时频率：每 15 分钟跑一次（交易日 08:00-22:00）。

    通知渠道通过 Notifier 抽象层决定，当前为钉钉。
    """
    alerts = []

    # 1. 超时任务（超过 45 分钟未完成的 running 任务）
    timed_out = check_timeout_tasks(timeout_minutes=45)
    for t in timed_out:
        started = t["started_at"].strftime("%H:%M") if t["started_at"] else "?"
        alerts.append(f"⚠️ 超时：{t['task_name']}（{started} 启动）")

    # 2. 近 6 小时内最新一次运行仍失败的任务；已被持久化重试恢复的旧
    #    attempt 不再重复告警。
    failed = count_failed_tasks(since_hours=6)
    if failed:
        total_fails = sum(r["cnt"] for r in failed)
        if total_fails >= 1:
            fail_lines = "\n".join(f"  · {r['task_name']} → 失败 {r['cnt']} 次" for r in failed)
            alerts.append(f"❌ 任务失败且尚未恢复（近6h）:\n{fail_lines}")

    # 3. 核心任务 daily 最近一次状态
    daily_runs = get_latest_runs(task_id="daily_daily", limit=1)
    if daily_runs:
        r = daily_runs[0]
        if r["status"] == "failed":
            alerts.append(f"🚨 日线行情(daily)采集失败，请尽快处理！")
        elif r["status"] == "timeout":
            alerts.append(f"⚠️ 日线行情(daily)采集超时")

    # 4. bak_basic 最近一次状态
    bak_runs = get_latest_runs(task_id="bak_basic_daily", limit=1)
    if bak_runs:
        r = bak_runs[0]
        if r["status"] == "failed":
            alerts.append(f"⚠️ 每日基本面(bak_basic)采集失败")

    # 5. 持久化采集队列积压、卡住和近期失败
    from service.collection_jobs.repository import JobRepository

    queue = JobRepository().health_snapshot()
    if queue["recent_failed"]:
        alerts.append(f"❌ 持久化采集队列近6小时失败 {queue['recent_failed']} 个")
    if queue["stale_queued"]:
        alerts.append(f"⚠️ 持久化采集队列积压超过1小时 {queue['stale_queued']} 个")
    if queue["stale_running"]:
        alerts.append(f"⚠️ 持久化采集任务运行超过45分钟 {queue['stale_running']} 个")

    # 6. 只告警本次巡检窗口中新产生的覆盖问题，避免对历史缺口刷屏。
    from service.db import query

    coverage = query(
        """
        SELECT
            count(*) FILTER (WHERE job_status = 'failed') AS recent_failed,
            COALESCE(sum(missing_partitions + partial_partitions)
                FILTER (WHERE audit_status = 'gaps'), 0) AS recent_gaps
        FROM (
            SELECT job.status AS job_status, NULL::text AS audit_status,
                   0 AS missing_partitions, 0 AS partial_partitions
            FROM sys_data_coverage_job job
            WHERE job.finished_at >= NOW() - INTERVAL '20 minutes'
            UNION ALL
            SELECT NULL, audit.status, audit.missing_partitions,
                   audit.partial_partitions
            FROM sys_data_coverage_audit audit
            WHERE audit.finished_at >= NOW() - INTERVAL '20 minutes'
        ) recent
        """
    )[0]
    if coverage["recent_failed"]:
        alerts.append(f"❌ 覆盖审计近期失败 {coverage['recent_failed']} 个")
    if coverage["recent_gaps"]:
        alerts.append(f"⚠️ 新审计发现缺失或不完整分区 {coverage['recent_gaps']} 个")

    if alerts:
        header = f"📊 数据巡检\n{'─'*16}"
        message = header + "\n" + "\n".join(alerts)
        _send_alert(message)
        logger.info(f"📊 巡检发现 {len(alerts)} 个问题，已发出告警")
    else:
        logger.info("✅ 巡检：所有任务正常")


def run_scheduler_heartbeat():
    from service.heartbeat import Heartbeat

    heartbeat = getattr(run_scheduler_heartbeat, "_heartbeat", None)
    if heartbeat is None:
        heartbeat = Heartbeat("scheduler")
        run_scheduler_heartbeat._heartbeat = heartbeat
    heartbeat.beat()


def run_collection_initialization_reconciler():
    """Advance the active durable initialization campaign by one state step."""
    from service.initialization.service import InitializationService

    campaign = InitializationService().reconcile_active()
    if campaign:
        logger.info(
            "🧱 初始化 #%s：%s / %s (%s/%s)",
            campaign["initialization_id"],
            campaign["phase_name"],
            campaign["status"],
            campaign["completed_steps"],
            campaign["planned_steps"],
        )


def run_fanout_campaign_reconciler():
    """Advance bounded pages for every runnable whole-universe campaign."""
    from service.collection_jobs.fanout_campaigns import FanoutCampaignService

    reconciled = FanoutCampaignService().reconcile_active(limit=20)
    if reconciled:
        logger.info("🧩 已对账 %s 个全量扇出活动", reconciled)


# ──────────────────────────────────────────────
# 调度器配置
# ──────────────────────────────────────────────
def create_scheduler(
    *, durabilize: bool = True, set_active: bool = True
) -> BackgroundScheduler:
    global _ACTIVE_SCHEDULER
    scheduler = BackgroundScheduler(
        executors={"default": ThreadPoolExecutor(max_workers=3)},
        timezone="Asia/Shanghai",
    )

    # ── 任务注册 ──

    scheduler.add_job(
        run_scheduler_heartbeat,
        trigger="interval",
        seconds=15,
        id="service_heartbeat",
        name="调度器进程心跳",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        next_run_time=business_now(),
    )

    scheduler.add_job(
        run_collection_schedule_reconciler,
        trigger="interval",
        minutes=1,
        id="collection_schedule_reconciler",
        name="专项采集计划持久化对账",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        next_run_time=business_now() + timedelta(seconds=5),
    )

    scheduler.add_job(
        run_scheduled_completion_reconciler,
        trigger="interval",
        minutes=15,
        id="scheduled_completion_reconciler",
        name="专项采集完成证据对账",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        next_run_time=business_now() + timedelta(seconds=9),
    )

    scheduler.add_job(
        run_coverage_rule_reconciler,
        trigger="interval",
        minutes=15,
        id="coverage_rule_reconciler",
        name="覆盖规则版本重审",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        next_run_time=business_now() + timedelta(seconds=2),
    )

    scheduler.add_job(
        run_collection_initialization_reconciler,
        trigger="interval",
        seconds=30,
        id="collection_initialization_reconciler",
        name="初始采集持久化协调器",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        next_run_time=business_now() + timedelta(seconds=3),
    )

    scheduler.add_job(
        run_fanout_campaign_reconciler,
        trigger="interval",
        seconds=20,
        id="fanout_campaign_reconciler",
        name="全量扇出活动续跑协调器",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        next_run_time=business_now() + timedelta(seconds=7),
    )

    def reconcile_delivery_plan() -> None:
        from service.delivery_monitor import DeliveryMonitorService

        count = DeliveryMonitorService().materialize(business_now().date())
        logger.info("📅 当日交付计划已对账：%s 项", count)

    scheduler.add_job(
        reconcile_delivery_plan,
        trigger="interval",
        hours=1,
        id="delivery_plan_reconciler",
        name="当日数据交付计划对账",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        next_run_time=business_now() + timedelta(seconds=12),
    )

    # 交易日历：每天 08:30 跑
    scheduler.add_job(
        run_trade_cal,
        trigger="cron",
        hour=8,
        minute=30,
        id="trade_cal_daily",
        name="交易日历-每日更新",
        replace_existing=True,
        misfire_grace_time=600,  # 允许延迟 10 分钟
    )

    # 每日涨跌停价格：盘前首采，并在上午重采两次。若上游 08:40 数据
    # 发布延迟，空结果会作为 empty 留证，不会触发过早的覆盖缺口修复。
    scheduler.add_job(
        run_stk_limit,
        trigger="cron",
        hour="9,10,12",
        minute=0,
        id="stk_limit_daily",
        name="每日涨跌停价格-盘前及上午重采",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # 每日停复牌信息：交易日 09:10 跑
    scheduler.add_job(
        run_suspend_d,
        trigger="cron",
        hour=9,
        minute=10,
        id="suspend_d_daily",
        name="每日停复牌信息-盘前更新",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # ST股票列表+风险警示板明细：每天 09:20 跑
    scheduler.add_job(
        run_stock_st,
        trigger="cron",
        hour=9,
        minute=20,
        id="stock_st_daily",
        name="ST股票列表-每日更新",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # 沪深港通股票列表：每天 09:20 跑
    scheduler.add_job(
        run_stock_hsgt,
        trigger="cron",
        hour=9,
        minute=20,
        id="stock_hsgt_daily",
        name="沪深港通列表-每日更新",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # 上市公司基本信息：每周一 08:30 跑（全量覆盖）
    scheduler.add_job(
        run_stock_company,
        trigger="cron",
        day_of_week="mon",
        hour=8,
        minute=30,
        id="stock_company_weekly",
        name="上市公司基本信息-每周一",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # IPO新股列表：每周一 08:30 跑（增量，取近1个月）
    scheduler.add_job(
        run_new_share,
        trigger="cron",
        day_of_week="mon",
        hour=8,
        minute=30,
        id="new_share_weekly",
        name="IPO新股列表-每周一",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # 股票基础信息：每天 08:30 跑
    scheduler.add_job(
        run_stock_basic,
        trigger="cron",
        hour=8,
        minute=30,
        id="stock_basic_daily",
        name="股票基础信息-每日全量",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # 核心盘后数据在 16:00 首采，并于 19:00、23:00 同日重采。
    # 上游偶发延迟或首轮空结果不会因此拖到第二天才被覆盖审计修复；
    # 全部写入均为主键 upsert，重复成功不会制造重复数据。
    scheduler.add_job(
        run_daily,
        trigger="cron",
        hour="16,19,23",
        minute=0,
        id="daily_daily",
        name="A股日线行情-盘后全量",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # 旧版 bak_basic 数据集沿用同样的同日重采窗口。
    scheduler.add_job(
        run_bak_basic,
        trigger="cron",
        hour="16,19,23",
        minute=0,
        id="bak_basic_daily",
        name="股票每日基本面-盘后更新",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # ── 沪深港通/港股通：交易日 20:00 跑（数据 18:00~20:00 更新） ──

    scheduler.add_job(
        run_hsgt_top10,
        trigger="cron",
        hour=20,
        minute=0,
        id="hsgt_top10_daily",
        name="沪深股通十大成交股-盘后更新",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    scheduler.add_job(
        run_ggt_top10,
        trigger="cron",
        hour=20,
        minute=5,
        id="ggt_top10_daily",
        name="港股通十大成交股-盘后更新",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    scheduler.add_job(
        run_ggt_daily,
        trigger="cron",
        hour=20,
        minute=10,
        id="ggt_daily_daily",
        name="港股通每日成交统计-盘后更新",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    scheduler.add_job(
        run_ggt_monthly,
        trigger="cron",
        hour=20,
        minute=15,
        id="ggt_monthly_daily",
        name="港股通每月成交统计-盘后更新",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    # ── 周/月线行情：盘后更新 ──

    scheduler.add_job(
        run_stk_weekly_monthly_week,
        trigger="cron",
        hour=20,
        minute=30,
        day_of_week="mon-fri",
        id="stk_weekly_monthly_week_daily",
        name="周线行情-盘后更新（每日）",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    scheduler.add_job(
        run_stk_weekly_monthly_month,
        trigger="cron",
        hour=20,
        minute=35,
        day_of_week="mon-fri",
        id="stk_weekly_monthly_month_daily",
        name="月线行情-盘后更新（每日）",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    # ── 周/月线 — 周五/月末专用（用 official 接口覆盖） ──

    scheduler.add_job(
        run_stk_weekly_weekly,
        trigger="cron",
        hour=20,
        minute=40,
        day_of_week="fri",
        id="stk_weekly_weekly_fri",
        name="周线行情-周收盘校订（周五）",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        run_stk_monthly_monthly,
        trigger="cron",
        hour=20,
        minute=45,
        day_of_week="mon-fri",
        id="stk_monthly_monthly_eom",
        name="月线行情-月收盘校订（月末）",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # ── 财务数据：工作日晚间滚动更新 ──
    # 财报会在法定截止日前逐家公司披露。只在截止后的固定日期采集会
    # 造成数周延迟，因此每天幂等刷新当前披露期，并由覆盖审计在法定
    # 截止日之后判断最终截面完整性。

    scheduler.add_job(
        run_income,
        trigger="cron",
        day_of_week="mon-fri",
        hour=21,
        minute=0,
        id="income_quarterly",
        name="利润表-披露期滚动更新",
        replace_existing=True,
        misfire_grace_time=86400,
    )

    # ── 财务数据：资产负债表 + 现金流量表 + 财务指标 ──
    scheduler.add_job(
        run_balancesheet,
        trigger="cron",
        day_of_week="mon-fri",
        hour=21,
        minute=10,
        id="balancesheet_quarterly",
        name="资产负债表-披露期滚动更新",
        replace_existing=True,
        misfire_grace_time=86400,
    )

    scheduler.add_job(
        run_cashflow,
        trigger="cron",
        day_of_week="mon-fri",
        hour=21,
        minute=20,
        id="cashflow_quarterly",
        name="现金流量表-披露期滚动更新",
        replace_existing=True,
        misfire_grace_time=86400,
    )

    scheduler.add_job(
        run_fina_indicator,
        trigger="cron",
        day_of_week="mon-fri",
        hour=21,
        minute=30,
        id="fina_indicator_quarterly",
        name="财务指标-披露期滚动更新",
        replace_existing=True,
        misfire_grace_time=86400,
    )

    # ── 财务数据：业绩预告（1/4/7/10月15日发布高峰） ──
    scheduler.add_job(
        run_forecast,
        trigger="cron",
        month="1,4,7,10",
        day=15,
        hour=21,
        minute=0,
        id="forecast_seasonal",
        name="业绩预告-季度更新",
        replace_existing=True,
        misfire_grace_time=86400,
    )

    # ── 财务数据：业绩快报（年报季后） ──
    scheduler.add_job(
        run_express,
        trigger="cron",
        month="1,2,3,4",
        day=20,
        hour=21,
        minute=0,
        id="express_annual",
        name="业绩快报-年报更新",
        replace_existing=True,
        misfire_grace_time=86400,
    )

    # ── 财务数据：主营业务构成（年报后） ──
    scheduler.add_job(
        run_mainbz,
        trigger="cron",
        month="5",
        day=5,
        hour=21,
        minute=40,
        id="mainbz_annual",
        name="主营业务-年报更新",
        replace_existing=True,
        misfire_grace_time=86400,
    )

    # ── 财务数据：财报披露计划（季度初更新） ──
    scheduler.add_job(
        run_disclosure_date,
        trigger="cron",
        month="1,4,7,10",
        day=5,
        hour=21,
        minute=50,
        id="disclosure_date_quarterly",
        name="财报披露计划-季度更新",
        replace_existing=True,
        misfire_grace_time=86400,
    )

    # ── 巡检任务（每 15 分钟，交易日 08:00-21:45） ──
    scheduler.add_job(
        run_inspector,
        trigger="cron",
        minute="*/15",
        hour="8-21",
        day_of_week="mon-fri",
        id="inspector_15min",
        name="采集任务巡检告警",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 每日多次幂等巡航，并在调度器启动后立即补一次。即使容器错过某个
    # 固定时点，仍会把最近日/周/月/季度任务补入持久化队列。
    scheduler.add_job(
        run_tushare_policy_dispatch,
        trigger="cron",
        hour="7,9,13,19,23",
        minute=15,
        id="tushare_policy_dispatch",
        name="Tushare目录接口-策略补采",
        replace_existing=True,
        misfire_grace_time=21600,
        coalesce=True,
        max_instances=1,
        next_run_time=business_now() + timedelta(seconds=10),
    )

    # Scheduler only creates bounded audit jobs. Heavy table scans run in the
    # independent auditor process so collection scheduling cannot be blocked.
    scheduler.add_job(
        run_data_coverage_dispatch,
        trigger="cron",
        hour=9,
        minute=30,
        id="data_coverage_dispatch",
        name="数据日期覆盖审计-任务生成",
        replace_existing=True,
        misfire_grace_time=21600,
        coalesce=True,
        max_instances=1,
        next_run_time=business_now() + timedelta(seconds=20),
    )

    # ── 指数数据 ──

    scheduler.add_job(
        run_index_basic,
        trigger="cron",
        day_of_week="mon",
        hour=7,
        minute=0,
        id="index_basic_weekly",
        name="指数基本信息-周更新",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        run_index_daily,
        trigger="cron",
        # CSI/CNI index partitions are published in waves. Live runs have
        # shown that 20:05 can still be materially smaller than the stable
        # ~10k-row partition, so keep same-day recovery active through 23:05.
        # The T+1 finalizer remains the last-resort stability pass.
        hour="15-23/1",
        minute=5,
        day_of_week="mon-fri",
        id="index_daily_daily",
        name="指数日线行情-盘后增量",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        run_index_daily_finalize,
        trigger="cron",
        hour=9,
        minute=35,
        day_of_week="mon-fri",
        id="index_daily_finalize",
        name="指数日线行情-T+1稳定性复采",
        replace_existing=True,
        misfire_grace_time=4 * 3600,
    )

    scheduler.add_job(
        run_index_dailybasic,
        trigger="cron",
        hour="15-20/1",
        minute=10,
        day_of_week="mon-fri",
        id="index_dailybasic_daily",
        name="大盘指数每日指标-盘后增量",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        run_index_global,
        trigger="cron",
        hour="15-22/1",
        minute=15,
        day_of_week="mon-fri",
        id="index_global_daily",
        name="国际指数-盘后增量",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        run_ths_daily,
        trigger="cron",
        hour="15-20/1",
        minute=20,
        day_of_week="mon-fri",
        id="ths_daily_daily",
        name="申万行业日线-盘后增量",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # ── 外汇数据 ──

    scheduler.add_job(
        run_fx_obasic,
        trigger="cron",
        day_of_week="mon",
        hour=7,
        minute=30,
        id="fx_obasic_weekly",
        name="外汇基础信息-周更新",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        run_fx_daily_daily,
        trigger="cron",
        hour="8-21/2",
        minute=30,
        day_of_week="mon-fri",
        id="fx_daily_daily",
        name="外汇日线-隔日增量",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # ── SGE 黄金现货 ──
    scheduler.add_job(
        run_sge_basic,
        trigger="cron",
        day_of_week="mon",
        hour=7,
        minute=35,
        id="sge_basic_weekly",
        name="SGE现货基础信息-周更新",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        run_sge_daily_daily,
        trigger="cron",
        hour="9-22/2",
        minute=30,
        day_of_week="mon-fri",
        id="sge_daily_daily",
        name="SGE日线-日增量",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    if durabilize:
        _durabilize_collection_jobs(scheduler)
    if set_active:
        _ACTIVE_SCHEDULER = scheduler
    return scheduler
if __name__ == "__main__":
    # ── 初始化通知器 ──
    from service.notifier import Notifier
    notifier_type = os.getenv("NOTIFIER_TYPE", "log").lower()
    notifier_kwargs = {}
    if notifier_type == "dingtalk" and os.getenv("DINGTALK_USER_ID"):
        notifier_kwargs["user_id"] = os.environ["DINGTALK_USER_ID"]
    Notifier.init(type=notifier_type, **notifier_kwargs)

    logger.info("🚀 claw-quant-data 调度器启动...")
    scheduler = create_scheduler()
    scheduler.start()

    print("=" * 60)
    print("  调度器已启动，任务列表：")
    for job in scheduler.get_jobs():
        trigger_desc = str(job.trigger) if job.trigger else "date(立即)"
        print(f"    - {job.id}: {trigger_desc}")
    print("=" * 60)
    print("  按 Ctrl+C 停止")
    print("=" * 60)

    try:
        # 保持主进程运行
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("🛑 收到停止信号，正在关闭调度器...")
        scheduler.shutdown(wait=False)
        logger.info("👋 调度器已关闭")
