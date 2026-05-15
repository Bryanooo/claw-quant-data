"""
指数数据历史补齐脚本 v3
正确处理参数依赖：
  - 需要 ts_code 的（daily/weekly/monthly/dailybasic）：按月逐个指数查询
  - 不需要 ts_code 的（ths_daily/global）：直接按月范围查询
  - 全量接口（basic/ths_member）：直接 collect()
"""
import sys
import os
import calendar
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

START = "20200101"
END = datetime.now().strftime("%Y%m%d")

# 主要 A 股指数
MAJOR_INDICES = [
    "000001.SH",  # 上证综指
    "399001.SZ",  # 深证成指
    "399006.SZ",  # 创业板指
    "000016.SH",  # 上证50
    "000300.SH",  # 沪深300
    "000688.SH",  # 科创50
    "000905.SH",  # 中证500
    "000852.SH",  # 中证1000
    "399673.SZ",  # 创业板50
]


def collect_single(collector, **params):
    """单次采集 + 重试"""
    for attempt in range(1, 4):
        try:
            return collector.collect(**params)
        except Exception as e:
            print(f"  ⚠️ 第{attempt}次失败: {e}")
            if attempt < 3:
                time.sleep(10)
    return 0


def backfill_by_month(collector, **extra_params):
    """按月范围补齐（支持额外参数如 ts_code）"""
    s = datetime.strptime(START, "%Y%m%d")
    e = datetime.strptime(END, "%Y%m%d")
    total = 0
    cur = s.replace(day=1)
    while cur <= e:
        _, ld = calendar.monthrange(cur.year, cur.month)
        month_end = min(cur.replace(day=ld), e)
        s_str = cur.strftime("%Y%m%d")
        e_str = month_end.strftime("%Y%m%d")
        try:
            rows = collector.collect(start_date=s_str, end_date=e_str, **extra_params)
            total += rows
        except Exception as ex:
            print(f"  {s_str}~{e_str}: ❌ {ex}")
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
        time.sleep(0.3)
    return total


def backfill_basic():
    """index_basic: 一次全量"""
    print(f"\n{'='*60}")
    print("1️⃣  index_basic — 一次全量")
    from collectors.index.basic import IndexBasicCollector
    c = IndexBasicCollector()
    rows = c.collect()
    print(f"  ✅ {rows} 行")
    return rows


def backfill_index_individually(name, CollectorCls):
    """逐个指数按月补齐"""
    print(f"\n{'='*60}")
    print(f"📊 {name} — {len(MAJOR_INDICES)}个指数按月补齐")
    c = CollectorCls()
    total = 0
    for ts_code in MAJOR_INDICES:
        r = backfill_by_month(c, ts_code=ts_code)
        total += r
        print(f"  {ts_code}: {r} 行 ✅")
        time.sleep(0.3)
    print(f"  {name} 合计: {total} 行")
    return total


def backfill_bulk(name, CollectorCls):
    """无额外参数的全量按月补齐"""
    print(f"\n{'='*60}")
    print(f"📊 {name} — 全量按月补齐")
    c = CollectorCls()
    total = backfill_by_month(c)
    print(f"  {name} 合计: {total} 行")
    return total


def main():
    total = 0

    from collectors.index.basic import IndexBasicCollector
    from collectors.index.daily import IndexDailyCollector
    from collectors.index.weekly import IndexWeeklyCollector
    from collectors.index.monthly import IndexMonthlyCollector
    from collectors.index.dailybasic import IndexDailybasicCollector
    from collectors.index.global_index import IndexGlobalCollector
    from collectors.index.ths_daily import ThsDailyCollector
    from collectors.index.ths_member import ThsMemberCollector

    total += backfill_basic()
    total += backfill_index_individually("index_daily", IndexDailyCollector)
    total += backfill_index_individually("index_weekly", IndexWeeklyCollector)
    total += backfill_index_individually("index_monthly", IndexMonthlyCollector)
    total += backfill_index_individually("index_dailybasic", IndexDailybasicCollector)
    total += backfill_bulk("index_global", IndexGlobalCollector)
    total += backfill_bulk("ths_daily", ThsDailyCollector)
    total += backfill_bulk("ths_member", ThsMemberCollector)

    print(f"\n{'='*60}")
    print(f"🏁 指数数据历史补齐完成，合计入库 {total} 行")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
