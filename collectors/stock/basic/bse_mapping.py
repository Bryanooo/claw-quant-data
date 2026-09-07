"""
=============================================================================
北交所新旧代码对照采集器
=============================================================================

接口：bse_mapping（tushare pro）
文档：https://tushare.pro/document/2?doc_id=375

描述：北交所股票代码变更后新旧代码映射表，总量约 300 条。
权限：120积分，单次最大1000条

运行模式：全量拉取，staging + 原子快照合并
"""

import pandas as pd
from collectors.base import BaseCollector
from collectors.contracts import ResourceClass, WriteMode


class BseMappingCollector(BaseCollector):
    write_mode = WriteMode.SNAPSHOT
    resource_class = ResourceClass.REFERENCE
    API_NAME = "bse_mapping"
    table_name = "bse_mapping"
    pk_columns = ["o_code"]

    def store(self, df: pd.DataFrame) -> int:
        """Merge a complete snapshot atomically without an ACCESS EXCLUSIVE lock."""
        return self.store_snapshot(df)
