"""
黄金现货基础信息采集器（sge_basic）
采集策略：全量一次性
"""

from collectors.base import BaseCollector


class SgeBasicCollector(BaseCollector):
    API_NAME = "sge_basic"
    table_name = "sge_basic"
    pk_columns = ["ts_code"]

    def collect_full(self):
        """全量采集所有现货合约"""
        rows = self.collect()
        self.logger.info(f"✅ sge_basic: 全量采集 {rows} 行")
        return rows
