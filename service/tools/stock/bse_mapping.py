"""
北交所新旧代码对照查询接口

从本地数据库查询 bse_mapping 表，不调 Tushare。
用于查询北交所股票代码变更映射。

函数：get_bse_mapping(o_code: str = None, n_code: str = None) → list[dict]
"""

from typing import Optional
from service.db import query


def get_bse_mapping(o_code: Optional[str] = None,
                    n_code: Optional[str] = None) -> list[dict]:
    """
    查询北交所新旧代码对照

    参数：
        o_code: 可选，原代码筛选
        n_code: 可选，新代码筛选

    返回：
        [
            {"name": "华岭股份", "o_code": "830139", "n_code": "430139", "list_date": "2022-10-28"},
            ...
        ]
    """
    sql = "SELECT name, o_code, n_code, list_date FROM bse_mapping WHERE 1=1"
    params = []
    if o_code:
        sql += " AND o_code = %s"
        params.append(o_code)
    if n_code:
        sql += " AND n_code = %s"
        params.append(n_code)
    sql += " ORDER BY o_code"

    return query(sql, tuple(params))
