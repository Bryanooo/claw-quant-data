"""
股权质押统计采集器
接口：pledge_stat
采集策略：逐个股票拉
"""

import re
import pandas as pd
from collectors.base import BaseCollector


class PledgeStatCollector(BaseCollector):
    API_NAME = "pledge_stat"
    table_name = "pledge_stat"
    pk_columns = ["ts_code", "end_date"]

    def _fix_date(self, val):
        if val is None:
            return None
        s = str(val).strip()
        if not s or s.lower() in ("nan", "nat", "none"):
            return None
        m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return s
        return None

    def fetch(self, **params) -> pd.DataFrame:
        if set(params) == {'end_date'}:
            day = params['end_date']
            frame = self.pro.pledge_stat(**params, limit=6000)
            if (frame.empty or len(frame) >= 6000 or frame.ts_code.isna().any()
                    or frame.ts_code.duplicated().any() or set(frame.end_date.astype(str)) != {day}):
                raise ValueError(f'pledge_stat unverified date partition {day}')
            tail = self.pro.pledge_stat(**params, limit=1, offset=len(frame))
            if not tail.empty:
                raise ValueError(f'pledge_stat date partition not exhausted: {day}')
            self._date_proof = {'verified': True, 'end_date': day, 'distinct_codes': len(frame),
                                'terminal_offset': len(frame)}
            return frame
        self._date_proof = None
        frame = self.pro.pledge_stat(**params)
        self._last_scope, self._last_rows = params, len(frame)
        return frame

    def partition_completion_evidence(self):
        if getattr(self, '_date_proof', None):
            return self._date_proof
        from collectors.tushare_raw import verify_complete_response
        from service.tushare_policy import TusharePolicyRegistry
        return verify_complete_response(self.API_NAME, TusharePolicyRegistry().get(self.API_NAME),
                                        self._last_scope, self._last_rows)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        if "end_date" in df.columns:
            df["end_date"] = df["end_date"].apply(self._fix_date)
        # 过滤掉关键字段为空的记录
        before = len(df)
        df = df.dropna(subset=["end_date"], how="any")
        if len(df) < before:
            self.logger.warning(f"过滤掉 {before - len(df)} 行（end_date 为空）")
        return df

    def collect_by_stock(self, ts_code: str) -> int:
        return self.collect(ts_code=ts_code)
