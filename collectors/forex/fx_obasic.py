"""
外汇基础信息采集器（fx_obasic）
采集策略：全量按分类拉
"""

from collectors.base import BaseCollector

_FIELDS = [
    "ts_code","name","classify","exchange","min_unit","max_unit",
    "pip","pip_cost","target_spread","min_stop_distance","trading_hours","break_time",
]

class FxObasicCollector(BaseCollector):
    INTERFACE_NAME = "fx_obasic"
    TABLE_NAME = "fx_obasic"
    CORE_FIELDS = _FIELDS
    pk_columns = ["ts_code"]

    def collect_full(self):
        """全量采集：获取所有分类的外汇基础信息"""
        total = 0
        for classify in ["FX","INDEX","COMMODITY","METAL","BUND","CRYPTO","FX_BASKET"]:
            df = self.fetch(exchange="FXCM", classify=classify)
            if df is not None and len(df) > 0:
                self.store(df)
                total += len(df)
        self.logger.info(f"✅ fx_obasic: 全量采集 {total} 行")
        return total
