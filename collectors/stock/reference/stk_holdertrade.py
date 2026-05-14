"""
股东增减持采集器（stk_holdertrade）

⚠️ 已知问题修复：
  1. 主键改为 (ts_code, ann_date, holder_name)，已移除 begin_date
  2. 日期字段（begin_date, close_date）Tushare 可能返回浮点数如 20260101.0，需转字符串
  3. holder_name 可能超 varchar(128)，需截断
  4. 历史补齐从按天改为按月（减少 API 调用）
"""

from collectors.base import BaseCollector


class StkHoldertradeCollector(BaseCollector):
    API_NAME = "stk_holdertrade"
    table_name = "stk_holdertrade"
    pk_columns = ["ts_code", "ann_date", "holder_name"]

    @staticmethod
    def _clean_date(val):
        """处理日期浮点数如 20260101.0 → 2026-01-01"""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            if val != val:  # NaN
                return None
            s = f"{int(val):08d}"
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        s = str(val).strip()
        if len(s) == 8 and s.isdigit():
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
        return s[:10] if len(s) >= 10 else s

    def transform(self, df):
        df = df.copy()
        # 清理日期字段
        for col in ["ann_date", "begin_date", "close_date"]:
            if col in df.columns:
                df[col] = df[col].apply(self._clean_date)
        # 截断 holder_name
        if "holder_name" in df.columns:
            df["holder_name"] = df["holder_name"].apply(
                lambda v: v[:128] if isinstance(v, str) and len(v) > 128 else v
            )
        return df
