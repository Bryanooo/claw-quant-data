"""
income 采集器：上市公司利润表
Tushare 接口: income_vip（按季度取全市场）
每次取一个报告期的全市场数据，约6000~6600行
"""

import logging
from datetime import date, datetime, timedelta

import pandas as pd

from collectors.base import BaseCollector, get_db_conn

logger = logging.getLogger("collector.income")

# 核心字段（排除银行/保险专用字段）
_INCOME_FIELDS = [
    "ts_code", "ann_date", "f_ann_date", "end_date",
    "report_type", "comp_type",
    "basic_eps", "diluted_eps",
    "revenue", "total_revenue",
    "oper_cost", "sell_exp", "admin_exp", "fin_exp", "rd_exp",
    "biz_tax_surchg", "assets_impair_loss",
    "invest_income", "fv_value_chg_gain",
    "operate_profit", "non_oper_income", "non_oper_exp",
    "total_profit", "income_tax",
    "n_income", "n_income_attr_p", "minority_gain",
    "ebit", "ebitda",
    "oth_compr_income", "t_compr_income", "compr_inc_attr_p",
    "update_flag",
]


class IncomeCollector(BaseCollector):
    INTERFACE_NAME = "income_vip"
    TABLE_NAME = "income"
    PK_COLUMNS = ["ts_code", "end_date", "report_type"]

    def __init__(self):
        super().__init__()
        self.db = get_db_conn()

    def fetch(self, **params):
        """兼容 BaseCollector 抽象方法"""
        return pd.DataFrame()

    def fetch_period(self, period: str):
        """取某个报告期全市场利润表"""
        fields = ",".join(_INCOME_FIELDS)
        df = self.pro.income_vip(period=period, fields=fields)
        if df is not None and len(df) > 0:
            logger.info(f"[income_vip] {period}: {len(df)} 行")
        return df

    def save(self, df):
        """批量 upsert"""
        if df is None or len(df) == 0:
            return
        with self.db.cursor() as cur:
            for _, r in df.iterrows():
                cur.execute("""
                    INSERT INTO income ({cols})
                    VALUES ({vals})
                    ON CONFLICT (ts_code, end_date, report_type) DO UPDATE SET
                        {updates}
                """.format(
                    cols=",".join(_INCOME_FIELDS),
                    vals=",".join([f"%s" for _ in _INCOME_FIELDS]),
                    updates=",".join([f"{c}=EXCLUDED.{c}" for c in _INCOME_FIELDS if c not in ("ts_code", "end_date", "report_type")]),
                ), tuple(None if _is_nan(r.get(c)) else r.get(c) for c in _INCOME_FIELDS))
        self.db.commit()
        logger.info(f"[income] {_get_periods(df)}: upsert {len(df)} 行")


def _get_periods(df):
    periods = sorted(df["end_date"].unique())
    return f"{periods[0]}~{periods[-1]}" if len(periods) > 1 else periods[0]


def _is_nan(v):
    if v is None:
        return True
    if isinstance(v, float):
        import math
        return math.isnan(v)
    return False
