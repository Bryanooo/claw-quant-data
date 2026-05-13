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
from datetime import datetime, timedelta

sys.path.insert(0, '/home/ecs-user/.openclaw/workspace/claw-quant-data')

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

from collectors.base import setup_logger, get_config
from service.run_tracker import track_run, check_timeout_tasks, count_failed_tasks, get_latest_runs


logger = setup_logger("scheduler")


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
    """交易日历：每天跑一次，取今天~下个月"""
    from collectors.stock.basic.trade_cal import TradeCalCollector
    from service.run_tracker import start_run, finish_run
    today = datetime.now().strftime("%Y%m%d")
    end = (datetime.now() + timedelta(days=31)).strftime("%Y%m%d")
    total = 0
    for ex in ["SSE", "SZSE"]:
        c = TradeCalCollector()
        rows = c.collect(exchange=ex, start_date=today, end_date=end)
        logger.info(f"  ✅ trade_cal({ex}): {rows} 行")
        total += rows
    return total


@track_run(task_id="stock_st_daily", task_name="ST股票列表-每日更新", trigger_type="cron")
def run_stock_st():
    """ST股票列表+风险警示板明细：每天 09:20 跑（只限交易日）"""
    today = datetime.now().strftime("%Y%m%d")
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
    today = datetime.now().strftime("%Y%m%d")
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
    today = datetime.now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 stk_limit")
        return 0
    from collectors.stock.basic.stk_limit import STKLimitCollector
    c = STKLimitCollector()
    df = c.fetch()
    c.save(df)
    cnt = len(df) if df is not None else 0
    logger.info(f"  ✅ stk_limit({today}): {cnt} 行")
    return cnt


@track_run(task_id="new_share_weekly", task_name="IPO新股列表-每周更新", trigger_type="cron")
def run_new_share():
    """IPO新股列表：每周一交易日补一次（近1个月增量）"""
    today = datetime.now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 new_share")
        return 0
    from collectors.stock.basic.new_share import NewShareCollector
    start = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    end = (datetime.now() + timedelta(days=7)).strftime("%Y%m%d")
    c = NewShareCollector()
    rows = c.collect(start_date=start, end_date=end)
    logger.info(f"  ✅ new_share({start}~{end}): {rows} 行")
    return rows


@track_run(task_id="stock_basic_daily", task_name="股票基础信息-每日全量", trigger_type="cron")
def run_stock_basic():
    """股票基础信息：每天全量刷新（只限交易日）"""
    today = datetime.now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 stock_basic")
        return 0
    from collectors.stock.basic.stock_basic import StockBasicCollector
    c = StockBasicCollector()
    rows = c.collect()
    logger.info(f"  ✅ stock_basic: {rows} 行")
    return rows


@track_run(task_id="stock_company_weekly", task_name="上市公司基本信息-每周更新", trigger_type="cron")
def run_stock_company():
    """上市公司基本信息：每周一次（周一交易日，全量覆盖）"""
    today = datetime.now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 stock_company")
        return 0
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
    """股票每日基本面（盘后）：每天 16:00 跑（只限交易日）"""
    today = datetime.now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 bak_basic")
        return 0
    from collectors.stock.basic.bak_basic import BakBasicCollector
    c = BakBasicCollector()
    rows = c.collect(trade_date=today)
    logger.info(f"  ✅ bak_basic({today}): {rows} 行")
    return rows


@track_run(task_id="daily_daily", task_name="A股日线行情-盘后全量", trigger_type="cron")
def run_daily():
    """A股日线行情：每天 16:00 盘后取当日全市场（分组100只/组，限交易日）"""
    today = datetime.now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 daily")
        return 0
    from collectors.stock.daily.daily import DailyCollector
    c = DailyCollector()
    rows = c.collect_by_date(trade_date=today)
    logger.info(f"  ✅ daily({today}): {rows} 行")
    return rows


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

    # 2. 近 6 小时失败任务
    failed = count_failed_tasks(since_hours=6)
    if failed:
        total_fails = sum(r["cnt"] for r in failed)
        if total_fails >= 1:
            fail_lines = "\n".join(f"  · {r['task_name']} → 失败 {r['cnt']} 次" for r in failed)
            alerts.append(f"❌ 任务失败（近6h）:\n{fail_lines}")

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

    if alerts:
        header = f"📊 数据巡检\n{'─'*16}"
        message = header + "\n" + "\n".join(alerts)
        _send_alert(message)
        logger.info(f"📊 巡检发现 {len(alerts)} 个问题，已发出告警")
    else:
        logger.info("✅ 巡检：所有任务正常")


# ──────────────────────────────────────────────
# 调度器配置
# ──────────────────────────────────────────────
def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(
        executors={"default": ThreadPoolExecutor(max_workers=3)},
        timezone="Asia/Shanghai",
    )

    # ── 任务注册 ──

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

    # 每日涨跌停价格：交易日 09:00 跑（数据 08:40 已更新）
    scheduler.add_job(
        run_stk_limit,
        trigger="cron",
        hour=9,
        minute=0,
        id="stk_limit_daily",
        name="每日涨跌停价格-盘前更新",
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

    # A股日线行情（盘后）：每天 16:00 跑（100只/组，限交易日）
    scheduler.add_job(
        run_daily,
        trigger="cron",
        hour=16,
        minute=0,
        id="daily_daily",
        name="A股日线行情-盘后全量",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # 股票每日基本面（盘后）：每天 16:00 跑（只限交易日）
    scheduler.add_job(
        run_bak_basic,
        trigger="cron",
        hour=16,
        minute=0,
        id="bak_basic_daily",
        name="股票每日基本面-盘后更新",
        replace_existing=True,
        misfire_grace_time=600,
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

    return scheduler


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────
if __name__ == "__main__":
    # ── 初始化通知器 ──
    from service.notifier import Notifier
    Notifier.init(type="dingtalk", user_id="1830664110642027")

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
