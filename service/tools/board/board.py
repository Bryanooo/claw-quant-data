"""
打板数据查询接口（23张表）
"""

from typing import Optional
from service.db import query


def _generic(table, order, conds, vals, limit=100):
    where = " AND ".join(conds) if conds else "1=1"
    return [dict(r) for r in query(f"SELECT * FROM {table} WHERE {where} ORDER BY {order} DESC LIMIT %s", (*vals, limit))]


# ═══ 1. top_list — 龙虎榜每日明细 ═══
def get_top_list(trade_date: Optional[str] = None, ts_code: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    return _generic("top_list", "trade_date", conds, vals, limit)

def get_top_list_by_stock(ts_code: str, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = ["ts_code = %s"], [ts_code]
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    return _generic("top_list", "trade_date", conds, vals, limit)


# ═══ 2. top_inst — 龙虎榜机构明细 ═══
def get_top_inst(trade_date: Optional[str] = None, ts_code: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    return _generic("top_inst", "trade_date", conds, vals, limit)


# ═══ 3. limit_list_d — 涨跌停列表 ═══
def get_limit_list(trade_date: Optional[str] = None, limit_type: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if limit_type: conds.append('"limit" = %s'); vals.append(limit_type)
    return _generic("limit_list_d", "trade_date", conds, vals, limit)


# ═══ 4. limit_step — 连板天梯 ═══
def get_limit_step(trade_date: Optional[str] = None, nums: Optional[int] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if nums: conds.append("nums = %s"); vals.append(nums)
    return _generic("limit_step", "trade_date", conds, vals, limit)


# ═══ 5. limit_cpt_list — 最强板块统计 ═══
def get_limit_cpt_list(trade_date: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    return _generic("limit_cpt_list", "trade_date", conds, vals, limit)


# ═══ 6. ths_index — 同花顺板块指数 ═══
def get_ths_index(ts_code: Optional[str] = None, type_: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if type_: conds.append('"type" = %s'); vals.append(type_)
    return _generic("ths_index", "ts_code", conds, vals, limit)


# ═══ 7. ths_daily — 同花顺板块指数行情 ═══
def get_ths_daily(ts_code: Optional[str] = None, trade_date: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    return _generic("ths_daily", "trade_date", conds, vals, limit)


# ═══ 8. ths_member — 同花顺概念板块成分 ═══
def get_ths_member(ts_code: Optional[str] = None, con_code: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if con_code: conds.append("con_code = %s"); vals.append(con_code)
    return _generic("ths_member", "ts_code", conds, vals, limit)


# ═══ 9. dc_index — 东方财富概念板块 ═══
def get_dc_index(trade_date: Optional[str] = None, idx_type: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if idx_type: conds.append("idx_type = %s"); vals.append(idx_type)
    return _generic("dc_index", "trade_date", conds, vals, limit)


# ═══ 10. dc_member — 东方财富板块成分 ═══
def get_dc_member(trade_date: Optional[str] = None, ts_code: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    return _generic("dc_member", "trade_date", conds, vals, limit)


# ═══ 11. dc_daily — 东财概念板块行情 ═══
def get_dc_daily(ts_code: Optional[str] = None, trade_date: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    return _generic("dc_daily", "trade_date", conds, vals, limit)


# ═══ 12. stk_auction — 当日集合竞价 ═══
def get_stk_auction(trade_date: Optional[str] = None, ts_code: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    return _generic("stk_auction", "trade_date", conds, vals, limit)


# ═══ 13. hm_list — 游资名录 ═══
def get_hm_list(name: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if name: conds.append('"name" = %s'); vals.append(name)
    return _generic("hm_list", "name", conds, vals, limit)




# ═══ 15. ths_hot — 同花顺热榜 ═══
def get_ths_hot(trade_date: Optional[str] = None, market: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if market: conds.append("data_type = %s"); vals.append(market)
    return _generic("ths_hot", "rank", conds, vals, limit)


# ═══ 16. dc_hot — 东方财富热榜 ═══
def get_dc_hot(trade_date: Optional[str] = None, market: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if market: conds.append("data_type = %s"); vals.append(market)
    return _generic("dc_hot", "rank", conds, vals, limit)


# ═══ 17. tdx_index — 通达信板块信息 ═══
def get_tdx_index(trade_date: Optional[str] = None, idx_type: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if idx_type: conds.append("idx_type = %s"); vals.append(idx_type)
    return _generic("tdx_index", "trade_date", conds, vals, limit)


# ═══ 18. tdx_member — 通达信板块成分 ═══
def get_tdx_member(trade_date: Optional[str] = None, ts_code: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    return _generic("tdx_member", "trade_date", conds, vals, limit)


# ═══ 19. tdx_daily — 通达信板块行情 ═══
def get_tdx_daily(ts_code: Optional[str] = None, trade_date: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if start_date: conds.append("trade_date >= %s"); vals.append(start_date)
    if end_date: conds.append("trade_date <= %s"); vals.append(end_date)
    return _generic("tdx_daily", "trade_date", conds, vals, limit)


# ═══ 20. kpl_list — 开盘啦榜单数据 ═══
def get_kpl_list(trade_date: Optional[str] = None, tag: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if tag: conds.append("tag = %s"); vals.append(tag)
    return _generic("kpl_list", "trade_date", conds, vals, limit)


# ═══ 21. kpl_concept_cons — 开盘啦题材成分 ═══
def get_kpl_concept_cons(trade_date: Optional[str] = None, ts_code: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    return _generic("kpl_concept_cons", "trade_date", conds, vals, limit)


# ═══ 22. dc_concept — 东方财富题材库 ═══
def get_dc_concept(trade_date: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    return _generic("dc_concept", "trade_date", conds, vals, limit)


# ═══ 23. dc_concept_cons — 东方财富题材成分 ═══
def get_dc_concept_cons(trade_date: Optional[str] = None, ts_code: Optional[str] = None, theme_code: Optional[str] = None, limit: int = 100) -> list[dict]:
    conds, vals = [], []
    if trade_date: conds.append("trade_date = %s"); vals.append(trade_date)
    if ts_code: conds.append("ts_code = %s"); vals.append(ts_code)
    if theme_code: conds.append("theme_code = %s"); vals.append(theme_code)
    return _generic("dc_concept_cons", "trade_date", conds, vals, limit)


__all__ = [
    "get_top_list", "get_top_list_by_stock",
    "get_top_inst",
    "get_limit_list",
    "get_limit_step",
    "get_limit_cpt_list",
    "get_ths_index",
    "get_ths_daily",
    "get_ths_member",
    "get_dc_index",
    "get_dc_member",
    "get_dc_daily",
    "get_stk_auction",
    "get_hm_list",
    "get_ths_hot",
    "get_dc_hot",
    "get_tdx_index",
    "get_tdx_member",
    "get_tdx_daily",
    "get_kpl_list",
    "get_kpl_concept_cons",
    "get_dc_concept",
    "get_dc_concept_cons",
]
