"""
指数数据采集模块
├── basic.py           # 指数基本信息 (index_basic)
├── daily.py           # 指数日线行情 (index_daily)
├── weekly.py          # 指数周线行情 (index_weekly)
├── monthly.py         # 指数月线行情 (index_monthly)
├── dailybasic.py      # 大盘指数每日指标 (index_dailybasic)
├── global_index.py    # 国际指数 (index_global)
├── ths_daily.py       # 申万行业日线行情 (ths_daily)
├── ths_member.py      # 申万行业成分构成 (ths_member)
"""

from collectors.index.basic import IndexBasicCollector
from collectors.index.daily import IndexDailyCollector
from collectors.index.weekly import IndexWeeklyCollector
from collectors.index.monthly import IndexMonthlyCollector
from collectors.index.dailybasic import IndexDailybasicCollector
from collectors.index.global_index import IndexGlobalCollector
from collectors.index.ths_daily import ThsDailyCollector
from collectors.index.ths_member import ThsMemberCollector

__all__ = [
    "IndexBasicCollector",
    "IndexDailyCollector",
    "IndexWeeklyCollector",
    "IndexMonthlyCollector",
    "IndexDailybasicCollector",
    "IndexGlobalCollector",
    "ThsDailyCollector",
    "ThsMemberCollector",
]
