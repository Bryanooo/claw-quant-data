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
    from collectors.stock.market.stk_limit import STKLimitCollector
    c = STKLimitCollector()
    df = c.fetch()
    c.save(df)
    cnt = len(df) if df is not None else 0
    logger.info(f"  ✅ stk_limit({today}): {cnt} 行")
    return cnt


@track_run(task_id="suspend_d_daily", task_name="每日停复牌信息-盘前更新", trigger_type="cron")
def run_suspend_d():
    """每日停复牌信息：交易日 09:10 跑"""
    today = datetime.now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 suspend_d")
        return 0
    from collectors.stock.market.suspend_d import SuspendDCollector
    c = SuspendDCollector()
    df = c.fetch(today, today)
    c.save(df)
    cnt = len(df) if df is not None else 0
    logger.info(f"  ✅ suspend_d({today}): {cnt} 条")
    return cnt


@track_run(task_id="hsgt_top10_daily", task_name="沪深股通十大成交股-盘后更新", trigger_type="cron")
def run_hsgt_top10():
    """沪深股通十大成交股：交易日 20:00 跑"""
    today = datetime.now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 hsgt_top10")
        return 0
    from collectors.stock.market.hsgt_top10 import HsgtTop10Collector
    c = HsgtTop10Collector()
    df = c.fetch(today)
    c.save(df)
    cnt = len(df) if df is not None else 0
    logger.info(f"  ✅ hsgt_top10({today}): {cnt} 条")
    return cnt


@track_run(task_id="ggt_top10_daily", task_name="港股通十大成交股-盘后更新", trigger_type="cron")
def run_ggt_top10():
    """港股通十大成交股：交易日 20:00 跑"""
    today = datetime.now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 ggt_top10")
        return 0
    from collectors.stock.market.ggt_top10 import GgtTop10Collector
    c = GgtTop10Collector()
    df = c.fetch(today)
    c.save(df)
    cnt = len(df) if df is not None else 0
    logger.info(f"  ✅ ggt_top10({today}): {cnt} 条")
    return cnt


@track_run(task_id="ggt_daily_daily", task_name="港股通每日成交统计-盘后更新", trigger_type="cron")
def run_ggt_daily():
    """港股通每日成交统计：交易日 20:00 跑（取近2天防遗漏）"""
    from collectors.stock.market.ggt_daily import GgtDailyCollector
    today = datetime.now().strftime("%Y%m%d")
    yesterday = (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")
    c = GgtDailyCollector()
    df = c.fetch(yesterday, today)
    c.save(df)
    cnt = len(df) if df is not None else 0
    logger.info(f"  ✅ ggt_daily({today}): {cnt} 条")
    return cnt


@track_run(task_id="ggt_monthly_daily", task_name="港股通每月成交统计-盘后更新", trigger_type="cron")
def run_ggt_monthly():
    """港股通每月成交统计：交易日 20:00 跑（取近3个月）"""
    from collectors.stock.market.ggt_monthly import GgtMonthlyCollector
    today = datetime.now()
    start_m = (today.replace(day=1) - timedelta(days=90)).strftime("%Y%m")
    end_m = today.strftime("%Y%m")
    c = GgtMonthlyCollector()
    df = c.fetch(start_m, end_m)
    c.save(df)
    cnt = len(df) if df is not None else 0
    logger.info(f"  ✅ ggt_monthly({end_m}): {cnt} 条")
    return cnt


@track_run(task_id="stk_weekly_monthly_week", task_name="周线行情-盘后更新", trigger_type="cron")
def run_stk_weekly_monthly_week():
    """周线行情：每个交易日 20:30 用 stk_weekly_monthly 更新"""
    from collectors.stock.market.stk_weekly_monthly import StkWeeklyMonthlyCollector
    today = datetime.now()
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
    today = datetime.now().strftime("%Y%m%d")
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
    today = datetime.now().strftime("%Y%m%d")
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
    today = datetime.now().strftime("%Y%m%d")
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


@track_run(task_id="income_quarterly", task_name="利润表-季度财报更新", trigger_type="cron")
def run_income():
    """利润表：财报季后自动更新"""
    from collectors.finance.income import IncomeCollector
    from service.db import query

    today = datetime.now()
    m = today.month; y = today.year
    if m >= 11:
        period = f"{y}0930"
    elif m >= 9:
        period = f"{y}0630"
    elif m >= 5:
        period = f"{y}0331"
    else:
        period = f"{y-1}1231"

    rows = query(f"SELECT count(*) FROM income WHERE end_date = '{period}'")
    if rows[0]['count'] > 0:
        logger.info(f"⏭️  {period} 已有数据，跳过")
        return rows[0]['count']

    c = IncomeCollector()
    df = c.fetch_period(period)
    c.save(df)
    cnt = len(df) if df is not None else 0
    logger.info(f"  ✅ income({period}): {cnt} 行")
    return cnt


@track_run(task_id="income_bootstrap", task_name="利润表-季度补齐", trigger_type="date")
def run_income_bootstrap():
    """启动时补齐所有缺失的报告期"""
    from collectors.finance.income import IncomeCollector
    from service.db import query
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
        r = query(f"SELECT count(*) FROM income WHERE end_date = '{p}'")
        if r[0]['count'] > 0:
            continue
        df = c.fetch_period(p)
        if df is not None and len(df) > 0:
            c.save(df)
            total += len(df)
        time.sleep(1)
    if total > 0:
        logger.info(f"  ✅ income_bootstrap: 补齐 {total} 行")
    return total


def _run_finance_quarterly(collector_cls, name):
    """通用：财报季后自动更新某张财务表"""
    today = datetime.now()
    m = today.month; y = today.year
    if m >= 11:
        period = f"{y}0930"
    elif m >= 9:
        period = f"{y}0630"
    elif m >= 5:
        period = f"{y}0331"
    else:
        period = f"{y-1}1231"

    from service.db import query
    c = collector_cls()
    tbl = c.TABLE_NAME
    rows = query(f"SELECT count(*) FROM {tbl} WHERE end_date = '{period}'")
    if rows[0]['count'] > 0:
        logger.info(f"⏭️  {name}({period}) 已有数据，跳过")
        return rows[0]['count']
    df = c.fetch_period(period)
    c.save(df)
    cnt = len(df) if df is not None else 0
    logger.info(f"  ✅ {name}({period}): {cnt} 行")
    return cnt


@track_run(task_id="balancesheet_quarterly", task_name="资产负债表-季度更新", trigger_type="cron")
def run_balancesheet():
    from collectors.finance.balancesheet import BalancesheetCollector
    return _run_finance_quarterly(BalancesheetCollector, "资产负债表")


@track_run(task_id="cashflow_quarterly", task_name="现金流量表-季度更新", trigger_type="cron")
def run_cashflow():
    from collectors.finance.cashflow import CashflowCollector
    return _run_finance_quarterly(CashflowCollector, "现金流量表")


@track_run(task_id="fina_indicator_quarterly", task_name="财务指标-季度更新", trigger_type="cron")
def run_fina_indicator():
    from collectors.finance.fina_indicator import FinaIndicatorCollector
    return _run_finance_quarterly(FinaIndicatorCollector, "财务指标")


@track_run(task_id="express_annual", task_name="业绩快报-年报更新", trigger_type="cron")
def run_express():
    """业绩快报通常在1~4月发布"""
    today = datetime.now()
    m = today.month; y = today.year
    if m < 5:
        period = f"{y-1}1231"
    else:
        logger.info("⏭️  非年报季，跳过业绩快报")
        return 0
    from collectors.finance.express import ExpressCollector
    from service.db import query
    rows = query(f"SELECT count(*) FROM express WHERE end_date = '{period}'")
    if rows[0]['count'] > 0:
        logger.info(f"⏭️  业绩快报({period}) 已有数据，跳过")
        return rows[0]['count']
    c = ExpressCollector()
    df = c.fetch_period(period)
    c.save(df)
    cnt = len(df) if df is not None else 0
    logger.info(f"  ✅ express({period}): {cnt} 行")
    return cnt


@track_run(task_id="forecast_seasonal", task_name="业绩预告-季度更新", trigger_type="cron")
def run_forecast():
    """业绩预告通常在1月(年报)、4月(Q1)、7月(半年报)、10月(Q3)批量发布"""
    today = datetime.now()
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
    from collectors.finance.forecast import ForecastCollector
    from service.db import query
    rows = query(f"SELECT count(*) FROM forecast WHERE end_date = '{period}'")
    if rows[0]['count'] > 0:
        logger.info(f"⏭️  业绩预告({period}) 已有数据，跳过")
        return rows[0]['count']
    c = ForecastCollector()
    df = c.fetch_period(period)
    c.save(df)
    cnt = len(df) if df is not None else 0
    logger.info(f"  ✅ forecast({period}): {cnt} 行")
    return cnt


@track_run(task_id="mainbz_annual", task_name="主营业务构成-年报更新", trigger_type="cron")
def run_mainbz():
    """主营业务构成：年报为主"""
    y = datetime.now().year
    period = f"{y-1}1231"
    from collectors.finance.fina_mainbz import FinaMainbzCollector
    from service.db import query
    rows = query(f"SELECT count(*) FROM fina_mainbz WHERE end_date = '{period}'")
    if rows[0]['count'] > 0:
        logger.info(f"⏭️  主营业务({period}) 已有数据，跳过")
        return rows[0]['count']
    c = FinaMainbzCollector()
    df = c.fetch_period(period)
    c.save(df)
    cnt = len(df) if df is not None else 0
    logger.info(f"  ✅ mainbz({period}): {cnt} 行")
    return cnt


@track_run(task_id="dividend_bootstrap", task_name="分红送股-全量补齐", trigger_type="date")
def run_dividend_bootstrap():
    """分红送股：按股票逐个取（无vip接口），只在启动时补齐"""
    from collectors.finance.dividend import DividendCollector
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
            c.save(df)
            total += len(df)

    if total > 0:
        logger.info(f"  ✅ dividend_bootstrap: 补齐 {total} 行")
    return total


@track_run(task_id="disclosure_date_quarterly", task_name="财报披露计划-季度更新", trigger_type="cron")
def run_disclosure_date():
    """财报披露计划：按 end_date 取"""
    today = datetime.now()
    y = today.year
    # 取当期+展望一个季度
    from collectors.finance.disclosure_date import DisclosureDateCollector
    from service.db import query
    c = DisclosureDateCollector()
    total = 0
    for p in [f"{y}0331", f"{y}0630", f"{y}0930", f"{y}1231"]:
        rows = query(f"SELECT count(*) FROM disclosure_date WHERE end_date = '{p}'")
        if rows[0]['count'] > 0:
            continue
        df = c.fetch_period(p)
        c.save(df)
        total += len(df) if df is not None else 0
    logger.info(f"  ✅ disclosure_date: {total} 行")
    return total


@track_run(task_id="daily_daily", task_name="A股日线行情-盘后全量", trigger_type="cron")
def run_daily():
    """A股日线行情：每天 16:00 盘后取当日全市场（分组100只/组，限交易日）"""
    today = datetime.now().strftime("%Y%m%d")
    if not _is_trade_day(today):
        logger.info(f"⏭️  非交易日({today})，跳过 daily")
        return 0
    from collectors.stock.market.daily import DailyCollector
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

    # ── 财务数据：利润表 — 季度财报季更新 ──

    scheduler.add_job(
        run_income,
        trigger="cron",
        month="5,9,11",
        day=5,
        hour=21,
        minute=0,
        id="income_quarterly",
        name="利润表-季度财报更新",
        replace_existing=True,
        misfire_grace_time=86400,  # 24小时容错
    )

    scheduler.add_job(
        run_income,
        trigger="cron",
        month="1,2,3",
        day=5,
        hour=21,
        minute=0,
        id="income_annual_update",
        name="利润表-年报更新",
        replace_existing=True,
        misfire_grace_time=86400,
    )

    # ── 财务数据：资产负债表 + 现金流量表 + 财务指标 ──
    scheduler.add_job(
        run_balancesheet,
        trigger="cron",
        month="5,9,11",
        day=5,
        hour=21,
        minute=10,
        id="balancesheet_quarterly",
        name="资产负债表-季度更新",
        replace_existing=True,
        misfire_grace_time=86400,
    )
    scheduler.add_job(
        run_balancesheet,
        trigger="cron",
        month="1,2,3",
        day=5,
        hour=21,
        minute=10,
        id="balancesheet_annual",
        name="资产负债表-年报更新",
        replace_existing=True,
        misfire_grace_time=86400,
    )

    scheduler.add_job(
        run_cashflow,
        trigger="cron",
        month="5,9,11",
        day=5,
        hour=21,
        minute=20,
        id="cashflow_quarterly",
        name="现金流量表-季度更新",
        replace_existing=True,
        misfire_grace_time=86400,
    )
    scheduler.add_job(
        run_cashflow,
        trigger="cron",
        month="1,2,3",
        day=5,
        hour=21,
        minute=20,
        id="cashflow_annual",
        name="现金流量表-年报更新",
        replace_existing=True,
        misfire_grace_time=86400,
    )

    scheduler.add_job(
        run_fina_indicator,
        trigger="cron",
        month="5,9,11",
        day=5,
        hour=21,
        minute=30,
        id="fina_indicator_quarterly",
        name="财务指标-季度更新",
        replace_existing=True,
        misfire_grace_time=86400,
    )
    scheduler.add_job(
        run_fina_indicator,
        trigger="cron",
        month="1,2,3",
        day=5,
        hour=21,
        minute=30,
        id="fina_indicator_annual",
        name="财务指标-年报更新",
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
