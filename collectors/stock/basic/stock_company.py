"""
上市公司基本信息采集器
接口：stock_company（tushare pro）
"""

from collectors.base import BaseCollector


class StockCompanyCollector(BaseCollector):
    API_NAME = "stock_company"
    table_name = "stock_company"
    pk_columns = ["ts_code"]



