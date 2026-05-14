"""
中央结算系统持股明细采集器（ccass_hold_detail）
采集策略：按 trade_date 逐天拉
注意：此接口不支持 start_date+end_date 范围查询，必须逐日采集
"""

from collectors.base import BaseCollector


class CcassHoldDetailCollector(BaseCollector):
    API_NAME = "ccass_hold_detail"
    table_name = "ccass_hold_detail"
    pk_columns = ["trade_date", "ts_code", "member_id"]
    supports_range_query = False  # 不支持范围查询，需逐日拉取
