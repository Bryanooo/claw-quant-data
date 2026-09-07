import pandas as pd

from collectors.base import BaseCollector
from collectors.stock.basic.stock_basic import StockBasicCollector
from collectors.stock.market.daily import DailyCollector
from collectors.stock.finance.base import BaseFinanceCollector


def test_stock_basic_fetches_all_statuses_and_requests_status_field(monkeypatch):
    monkeypatch.setattr(BaseCollector, "__init__", lambda self: None)
    collector = StockBasicCollector()
    calls = []

    class FakePro:
        def stock_basic(self, **parameters):
            calls.append(parameters)
            status = parameters["list_status"]
            if status == "P":
                return pd.DataFrame()
            return pd.DataFrame([{"ts_code": f"{status}.SZ", "list_status": status}])

    collector.pro = FakePro()
    result = collector.fetch()

    assert [item["list_status"] for item in calls] == ["L", "D", "P"]
    assert all("list_status" in item["fields"] for item in calls)
    assert result["list_status"].tolist() == ["L", "D"]


def test_daily_market_partition_does_not_build_comma_separated_codes(monkeypatch):
    monkeypatch.setattr(BaseCollector, "__init__", lambda self: None)
    collector = DailyCollector()
    calls = []
    monkeypatch.setattr(
        collector,
        "collect",
        lambda **parameters: calls.append(parameters) or 5551,
    )

    assert collector.collect_by_date("20260828") == 5551
    assert calls == [{"trade_date": "20260828"}]


def test_finance_period_exhausts_offset_pages(monkeypatch):
    class FinanceCollector(BaseFinanceCollector):
        INTERFACE_NAME = "income_vip"
        CORE_FIELDS = ["ts_code", "end_date", "report_type"]
        PK_COLUMNS = ["ts_code", "end_date", "report_type"]

    collector = object.__new__(FinanceCollector)
    calls = []

    class FakePro:
        def income_vip(self, **parameters):
            calls.append(parameters)
            offset = parameters["offset"]
            size = 3000 if offset == 0 else 1
            return pd.DataFrame(
                [
                    {
                        "ts_code": f"{offset + index:06d}.SZ",
                        "end_date": "20260630",
                        "report_type": "1",
                    }
                    for index in range(size)
                ]
            )

    collector.pro = FakePro()
    monkeypatch.setattr("collectors.stock.finance.base.time.sleep", lambda _seconds: None)

    result = collector.fetch_period("20260630")

    assert len(result) == 3001
    assert [item["offset"] for item in calls] == [0, 3000]
    assert all(item["limit"] == 3000 for item in calls)


def test_finance_fetch_uses_standard_period_parameter(monkeypatch):
    class FinanceCollector(BaseFinanceCollector):
        INTERFACE_NAME = "income_vip"
        TABLE_NAME = "income"
        CORE_FIELDS = ["ts_code", "end_date", "report_type"]
        PK_COLUMNS = ["ts_code", "end_date", "report_type"]

    collector = object.__new__(FinanceCollector)
    expected = pd.DataFrame(
        [{"ts_code": "000001.SZ", "end_date": "20260630", "report_type": "1"}]
    )
    monkeypatch.setattr(collector, "fetch_period", lambda period: expected)

    assert collector.fetch(period="20260630") is expected
