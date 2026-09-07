import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from collectors.base import (
    BaseCollector,
    CollectorRateLimitError,
    NonRetryableCollectorError,
    PartialCollectionError,
    sanitize_postgres_value,
)
from collectors.contracts import CollectorRequest, CollectorResult
from collectors.stock.market.daily import _fix_date


class ExampleCollector(BaseCollector):
    API_NAME = "example"
    table_name = "example"
    pk_columns = ["id"]


def _collector_without_init():
    collector = ExampleCollector.__new__(ExampleCollector)
    collector.logger = logging.getLogger("test-collector")
    collector.retry_max = 3
    collector.retry_interval = 0
    return collector


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("20260726", "2026-07-26"),
        ("2026-07-26", "2026-07-26"),
        ("", None),
        (None, None),
        (float("nan"), None),
        ("invalid", None),
    ],
)
def test_fix_date(value, expected):
    assert _fix_date(value) == expected


def test_collect_runs_fetch_transform_and_store(monkeypatch):
    collector = _collector_without_init()
    source = pd.DataFrame([{"id": 1, "value": 2}])
    monkeypatch.setattr(collector, "fetch", lambda **params: source)
    monkeypatch.setattr(
        collector, "transform", lambda frame: frame.assign(value=frame["value"] * 2)
    )
    stored = {}

    def fake_store(frame):
        stored["frame"] = frame
        return len(frame)

    monkeypatch.setattr(collector, "store", fake_store)

    assert collector.collect(trade_date="20260726") == 1
    assert stored["frame"].to_dict(orient="records") == [{"id": 1, "value": 4}]


def test_run_returns_structured_collection_evidence(monkeypatch):
    collector = _collector_without_init()
    monkeypatch.setattr(
        collector,
        "fetch",
        lambda **params: pd.DataFrame([{"id": 1}, {"id": 2}]),
    )
    monkeypatch.setattr(collector, "store", lambda frame: len(frame))

    result = collector.run(
        CollectorRequest({"trade_date": "20260829"}, partition_key="20260829")
    )

    assert isinstance(result, CollectorResult)
    assert result.api_name == "example"
    assert result.fetched_rows == 2
    assert result.stored_rows == 2
    assert result.partitions == ("20260829",)
    assert result.empty_reason is None


def test_run_records_empty_response_without_claiming_completeness(monkeypatch):
    collector = _collector_without_init()
    monkeypatch.setattr(collector, "fetch", lambda **params: pd.DataFrame())

    result = collector.run(trade_date="20260829")

    assert result.is_empty
    assert result.empty_reason == "upstream_returned_no_rows"
    assert result.evidence["empty_policy"] == "requires_verification"


def test_transport_retry_is_visible_and_counted_by_collector_runtime(monkeypatch):
    class FakePro:
        def query(self, api_name, **_parameters):
            assert api_name == "example"
            return pd.DataFrame([{"id": 1}])

        def example(self, **parameters):
            return self.query("example", **parameters)

    fake_pro = FakePro()
    monkeypatch.setattr("collectors.base.get_env_tushare_token", lambda: "test-token")
    monkeypatch.setattr(
        "collectors.base.get_config",
        lambda key, default=None: default,
    )
    monkeypatch.setattr("tushare.set_token", lambda _token: None)
    monkeypatch.setattr("tushare.pro_api", lambda: fake_pro)
    monkeypatch.setattr(
        "service.tushare_rate_limit.reserve_tushare_request",
        lambda *_args, **_kwargs: 0,
    )

    collector = ExampleCollector()
    result = collector.run(skip_store=True)

    assert result.request_count == 1
    assert collector.pro._DataApi__session.adapters["https://"].max_retries.total == 0


def test_collect_retries_then_succeeds(monkeypatch):
    collector = _collector_without_init()
    attempts = {"count": 0}

    def flaky_fetch(**params):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ConnectionError("temporary failure")
        return pd.DataFrame([{"id": 1}])

    monkeypatch.setattr(collector, "fetch", flaky_fetch)
    monkeypatch.setattr(collector, "store", lambda frame: len(frame))
    monkeypatch.setattr("collectors.base.time.sleep", lambda seconds: None)

    assert collector.collect() == 1
    assert attempts["count"] == 3


@pytest.mark.parametrize(
    ("message", "error_type"),
    [
        ("必填参数, trade_date", NonRetryableCollectorError),
        ("抱歉，您没有接口访问权限", NonRetryableCollectorError),
        ("访问接口频率超限(1次/小时)", CollectorRateLimitError),
    ],
)
def test_collect_does_not_blindly_retry_permanent_tushare_errors(
    monkeypatch, message, error_type
):
    collector = _collector_without_init()
    attempts = {"count": 0}

    def reject(**_params):
        attempts["count"] += 1
        raise Exception(message)

    monkeypatch.setattr(collector, "fetch", reject)

    with pytest.raises(error_type):
        collector.collect()
    assert attempts["count"] == 1


def test_rate_limit_error_exposes_retry_delay(monkeypatch):
    collector = _collector_without_init()
    monkeypatch.setattr(
        collector,
        "fetch",
        lambda **_params: (_ for _ in ()).throw(Exception("频率超限(2次/分钟)")),
    )

    with pytest.raises(CollectorRateLimitError) as captured:
        collector.collect()
    assert captured.value.retry_after_seconds == 30


def test_daily_quota_waits_until_next_shanghai_reset(monkeypatch):
    collector = _collector_without_init()
    monkeypatch.setattr(
        "collectors.base.business_now",
        lambda: datetime(2026, 8, 31, 20, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    monkeypatch.setattr(
        collector,
        "fetch",
        lambda **_params: (_ for _ in ()).throw(Exception("频率超限(1000次/天)")),
    )

    with pytest.raises(CollectorRateLimitError) as captured:
        collector.collect()
    assert captured.value.retry_after_seconds == 4 * 3600 + 5 * 60


def test_postgres_sanitizer_is_recursive_and_counted():
    value, count = sanitize_postgres_value(
        {"name": "概念\x00板块", "nested": ["a\x00", {"x\x00": "b\x00"}]}
    )

    assert value == {"name": "概念板块", "nested": ["a", {"x": "b"}]}
    assert count == 4


def test_collect_skip_store(monkeypatch):
    collector = _collector_without_init()
    monkeypatch.setattr(
        collector, "fetch", lambda **params: pd.DataFrame([{"id": 1}, {"id": 2}])
    )
    monkeypatch.setattr(
        collector,
        "store",
        lambda frame: pytest.fail("store must not run when skip_store=True"),
    )

    assert collector.collect(skip_store=True) == 2


def test_specialized_offset_pagination_exhausts_and_aggregates(monkeypatch):
    collector = _collector_without_init()
    page_sizes = {0: 2, 2: 2, 4: 1}
    calls = []

    def fetch(**params):
        calls.append(params)
        offset = params["offset"]
        return pd.DataFrame(
            [{"id": offset + index} for index in range(page_sizes[offset])]
        )

    monkeypatch.setattr(collector, "fetch", fetch)
    monkeypatch.setattr(collector, "store", lambda frame: len(frame))

    result = collector.run_offset_paginated(
        page_size=2,
        max_pages=5,
        trade_date="20260831",
    )

    assert [call["offset"] for call in calls] == [0, 2, 4]
    assert result.fetched_rows == 5
    assert result.stored_rows == 5
    assert result.request_count == 3
    assert result.partitions == ("20260831",)
    assert result.evidence["verified"] is True
    assert result.evidence["exhausted"] is True
    assert result.evidence["pages_completed"] == 3


def test_specialized_offset_pagination_fails_closed_at_max_pages(monkeypatch):
    collector = _collector_without_init()
    monkeypatch.setattr(
        collector,
        "fetch",
        lambda **params: pd.DataFrame(
            [{"id": params["offset"]}, {"id": params["offset"] + 1}]
        ),
    )
    monkeypatch.setattr(collector, "store", lambda frame: len(frame))

    with pytest.raises(PartialCollectionError) as captured:
        collector.run_offset_paginated(page_size=2, max_pages=2)

    assert captured.value.rows_inserted == 4
    assert captured.value.rows_fetched == 4
    assert captured.value.completion_evidence["exhausted"] is False


def test_specialized_offset_pagination_detects_ignored_offset(monkeypatch):
    collector = _collector_without_init()
    monkeypatch.setattr(
        collector,
        "fetch",
        lambda **_params: pd.DataFrame([{"id": 1}, {"id": 2}]),
    )
    monkeypatch.setattr(collector, "store", lambda frame: len(frame))

    with pytest.raises(PartialCollectionError, match="ignore offset"):
        collector.run_offset_paginated(page_size=2, max_pages=5)


def test_dividend_forwards_the_scheduler_partition_to_upstream():
    from collectors.stock.finance.dividend import DividendCollector

    calls = []

    class FakePro:
        def dividend(self, **parameters):
            calls.append(parameters)
            return pd.DataFrame()

    collector = DividendCollector.__new__(DividendCollector)
    collector.pro = FakePro()

    collector.fetch(ann_date="20260828")

    assert len(calls) == 2
    assert all(item["ann_date"] == "20260828" for item in calls)
    assert {item["div_proc"] for item in calls} == {"实施", "预案"}


def test_partitioned_history_fails_closed_when_any_partition_fails(monkeypatch):
    collector = _collector_without_init()
    monkeypatch.setattr(
        collector,
        "collect",
        lambda **_params: (_ for _ in ()).throw(ConnectionError("upstream down")),
    )
    monkeypatch.setattr("collectors.base.time.sleep", lambda _seconds: None)

    with pytest.raises(PartialCollectionError) as captured:
        collector.collect_all_history("20260101", "20260131")

    assert captured.value.rows_inserted == 0
    assert len(captured.value.failures) == 1


def test_ggt_monthly_is_derived_from_daily_data():
    from collectors.stock.market.ggt_monthly import GgtMonthlyCollector

    class FakePro:
        def ggt_daily(self, **_params):
            return pd.DataFrame(
                [
                    {"trade_date": "20260803", "buy_amount": 10, "buy_volume": 2, "sell_amount": 8, "sell_volume": 1},
                    {"trade_date": "20260804", "buy_amount": 20, "buy_volume": 4, "sell_amount": 12, "sell_volume": 3},
                ]
            )

    collector = object.__new__(GgtMonthlyCollector)
    collector.pro = FakePro()
    result = collector.fetch(start_month="202608", end_month="202608")

    assert result.to_dict(orient="records") == [
        {
            "month": "202608",
            "day_buy_amt": 15.0,
            "day_buy_vol": 3.0,
            "day_sell_amt": 10.0,
            "day_sell_vol": 2.0,
            "total_buy_amt": 30,
            "total_buy_vol": 6,
            "total_sell_amt": 20,
            "total_sell_vol": 4,
        }
    ]


def test_finance_pagination_detects_non_adjacent_cycles():
    from collectors.stock.finance.base import BaseFinanceCollector
    from collectors.tushare_raw import PaginationStalledError

    class FinanceCollector(BaseFinanceCollector):
        INTERFACE_NAME = "finance_vip"
        TABLE_NAME = "finance"
        CORE_FIELDS = ["ts_code", "end_date", "report_type"]
        PK_COLUMNS = ["ts_code", "end_date", "report_type"]

    pages = {
        0: [("000001.SZ", "20260630", 1), ("000002.SZ", "20260630", 1)],
        2: [("000003.SZ", "20260630", 1), ("000004.SZ", "20260630", 1)],
        4: [("000001.SZ", "20260630", 1), ("000002.SZ", "20260630", 1)],
    }

    class FakePro:
        def finance_vip(self, **params):
            return pd.DataFrame(
                pages[params["offset"]],
                columns=["ts_code", "end_date", "report_type"],
            )

    collector = object.__new__(FinanceCollector)
    collector.pro = FakePro()

    with pytest.raises(PaginationStalledError):
        collector._fetch_paginated("20260630", page_size=2, max_pages=4)


def test_disclosure_date_uses_end_date_partition_and_exhausts():
    from collectors.stock.finance.disclosure_date import DisclosureDateCollector

    calls = []

    class FakePro:
        def disclosure_date(self, **params):
            calls.append(params)
            if params["offset"]:
                return pd.DataFrame(columns=["ts_code", "end_date"])
            return pd.DataFrame([{"ts_code": "000001.SZ", "end_date": "20251231"}])

    collector = object.__new__(DisclosureDateCollector)
    collector.pro = FakePro()
    result = collector._fetch_paginated("20251231", page_size=1, max_pages=3)

    assert len(result) == 1
    assert [item["end_date"] for item in calls] == ["20251231", "20251231"]
    assert all("period" not in item for item in calls)
    proof = collector.partition_completion_evidence()
    assert proof["verified"] is True
    assert proof["pages_completed"] == 1
    assert proof["scopes"][0]["parameter"] == "end_date"


def test_finance_pagination_rejects_ignored_period_parameter():
    from collectors.stock.finance.base import BaseFinanceCollector
    from collectors.tushare_raw import IncompleteCollectionError

    class FinanceCollector(BaseFinanceCollector):
        INTERFACE_NAME = "finance_vip"
        TABLE_NAME = "finance"
        CORE_FIELDS = ["ts_code", "end_date"]
        PK_COLUMNS = ["ts_code", "end_date"]

    class FakePro:
        def finance_vip(self, **_params):
            return pd.DataFrame([{"ts_code": "000001.SZ", "end_date": "19901231"}])

    collector = object.__new__(FinanceCollector)
    collector.pro = FakePro()

    with pytest.raises(IncompleteCollectionError, match="ignored period"):
        collector._fetch_paginated("20251231", page_size=1000, max_pages=2)


def test_main_business_collector_paginates_each_classification(monkeypatch):
    from collectors.stock.finance.fina_mainbz import FinaMainbzCollector

    collector = object.__new__(FinaMainbzCollector)
    calls = []

    def fetch_scope(period, *, extra_params, **_options):
        calls.append((period, extra_params))
        return pd.DataFrame(
            [{
                "ts_code": "000001.SZ",
                "end_date": period,
                "bz_item": extra_params["type"],
                "bz_code": extra_params["type"],
            }]
        )

    monkeypatch.setattr(collector, "_fetch_paginated", fetch_scope)
    result = collector.fetch_period("20261231")

    assert calls == [
        ("20261231", {"type": "I"}),
        ("20261231", {"type": "P"}),
    ]
    assert len(result) == 2
