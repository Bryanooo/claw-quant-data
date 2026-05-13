"""
股票曾用名查询接口

直接调 Tushare namechange 接口，不落数据库。
用于查询指定股票的全部曾用名历史。

函数：get_namechange(ts_code: str) → list[dict]
"""

import pandas as pd
from typing import Optional
from service.db import get_pro


def _safe_val(val):
    """NaN/NaT → None，其他原样"""
    if val is None:
        return None
    if isinstance(val, float) and (pd.isna(val) or val != val):
        return None
    s = str(val).strip()
    if s in ("nan", "NaT", "None", ""):
        return None
    return s


def get_namechange(ts_code: str,
                   start_date: Optional[str] = None,
                   end_date: Optional[str] = None) -> list[dict]:
    """
    查询股票曾用名历史

    参数：
        ts_code:  股票代码，如 "000001.SZ"
        start_date: 可选，起始日期 YYYYMMDD
        end_date:   可选，截止日期 YYYYMMDD

    返回：
        [
            {
                "ts_code": "000001.SZ",
                "name": "平安银行",
                "start_date": "2020-01-01",
                "end_date": "2022-06-30",
                "ann_date": "2020-01-01",
                "change_reason": "更名"
            },
            ...
        ]
    """
    pro = get_pro()
    params = {"ts_code": ts_code}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date

    df = pro.namechange(**params,
                        fields="ts_code,name,start_date,end_date,ann_date,change_reason")
    if df is None or df.empty:
        return []

    # 日期转字符串，NaN 转 None
    result = []
    for _, row in df.iterrows():
        item = {
            "ts_code": _safe_val(row.get("ts_code", "")),
            "name": _safe_val(row.get("name")),
            "start_date": _safe_val(row.get("start_date")),
            "end_date": _safe_val(row.get("end_date")),
            "ann_date": _safe_val(row.get("ann_date")),
            "change_reason": _safe_val(row.get("change_reason")),
        }
        result.append(item)

    # 去重（Tushare 接口返回可能有重复行）
    seen = set()
    unique = []
    for item in result:
        key = (item["name"], item["start_date"], item["end_date"])
        if key not in seen:
            seen.add(key)
            unique.append(item)

    return unique
