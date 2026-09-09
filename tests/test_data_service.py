from datetime import date

import pytest

from service.data_service.models import (
    DatasetSpec,
    InvalidQueryError,
)
from service.collector_catalog import discover_collectors
from service.data_service.interfaces import InterfaceDataService
from service.data_service.registry import DATASETS, DatasetRegistry
from service.data_service.service import DataService
from service.tushare_normalization import NORMALIZATION_CONTRACTS


class FakeRepository:
    def __init__(self):
        self.last_dataset = None
        self.last_query = None

    def columns(self, dataset):
        return [
            {
                "column_name": "ts_code",
                "data_type": "character varying",
                "is_nullable": "NO",
            }
        ]

    def records(self, dataset, query):
        self.last_dataset = dataset
        self.last_query = query
        return [{"ts_code": query.exact_filters.get("ts_code", "000001.SZ")}]

    def count(self, dataset, query):
        return 1

    def latest_value(self, dataset):
        return None

    def estimated_rows(self, dataset):
        return 0

    def search_news(self, dataset, **kwargs):
        self.news_dataset = dataset
        self.news_query = kwargs
        return [
            {
                "_record_hash": "news-1",
                "title": "宁德时代发布经营进展",
                "content": "<p>宁德时代最新经营情况。</p>",
                "pub_time": "2026-09-07T12:00:00",
                "src": "测试新闻源",
            }
        ]


class FreshnessRepository(FakeRepository):
    def __init__(self, latest):
        super().__init__()
        self.latest = latest

    def latest_value(self, dataset):
        return self.latest

    def estimated_rows(self, dataset):
        return 12


def test_registry_rejects_duplicate_names():
    dataset = DatasetSpec(
        name="duplicate",
        table="example",
        description="example",
        category="test",
        primary_keys=("id",),
    )
    with pytest.raises(ValueError, match="duplicate dataset"):
        DatasetRegistry([dataset, dataset])


def test_registry_exposes_curated_datasets():
    names = {dataset.name for dataset in DATASETS.list()}

    assert "stock_daily" in names
    assert "financial_indicator" in names
    assert "index_daily" in names
    assert "forex_daily" in names
    assert "sge_daily" in names
    assert "tushare_raw" in names


def test_registry_exposes_every_collector_table():
    collector_tables = {contract.table_name for contract in discover_collectors()}
    registered_tables = {dataset.table for dataset in DATASETS.list()}
    normalized_tables = {
        contract.table_name for contract in NORMALIZATION_CONTRACTS.list()
    }

    assert collector_tables | normalized_tables | {
        "tushare_current_daily_basic"
    } == registered_tables
    assert len(DATASETS.list()) == 194


def test_normalized_dataset_exposes_versioned_storage_semantics():
    dataset = DATASETS.get("adj_factor")
    service = DataService(FakeRepository(), DATASETS)

    description = service.describe_dataset(dataset.name)

    assert description["primary_keys"] == ["_record_hash"]
    assert description["storage_semantics"] == "versioned_payload"
    assert description["business_identity_fields"] == ["trade_date", "ts_code"]
    assert description["identity_confidence"] == "heuristic"
    assert description["read_view"] is None


def test_reviewed_versioned_dataset_reads_from_current_view():
    dataset = DATASETS.get("fut_holding")

    assert dataset.table == "tushare_norm_fut_holding"
    assert dataset.read_table == "tushare_current_fut_holding"
    assert dataset.identity_confidence == "contract_reviewed"


def test_event_driven_freshness_without_sla_is_not_reported_as_stale():
    dataset = DatasetSpec(
        name="events",
        table="events",
        description="event data",
        category="test",
        primary_keys=("event_date",),
        date_column="event_date",
        freshness_sla_hours=None,
        freshness_policy="event_driven",
    )
    service = DataService(FreshnessRepository(date(2020, 1, 1)), DatasetRegistry([dataset]))

    assert service.freshness("events") == [
        {
            "dataset": "events",
            "latest_date": date(2020, 1, 1),
            "status": "event_driven",
            "freshness_sla_hours": None,
            "freshness_policy": "event_driven",
            "expected_latest_date": None,
            "estimated_rows": 12,
        }
    ]


def test_periodic_index_freshness_matches_its_real_cadence():
    assert DATASETS.get("index_daily").freshness_sla_hours == 72
    assert DATASETS.get("index_weekly").freshness_sla_hours == 24 * 10
    assert DATASETS.get("index_monthly").freshness_sla_hours == 24 * 45
    for dataset in ("slb_len", "slb_len_mm", "slb_sec", "slb_sec_detail"):
        assert DATASETS.get(dataset).freshness_sla_hours is None


def test_quarterly_freshness_respects_disclosure_deadlines():
    dataset = DatasetSpec(
        name="income",
        table="income",
        description="income",
        category="finance",
        primary_keys=("ts_code", "end_date"),
        date_column="end_date",
        freshness_sla_hours=24 * 120,
        freshness_policy="quarterly_disclosure",
    )

    assert DataService._latest_required_report_period(date(2026, 8, 30)) == date(
        2026, 3, 31
    )
    assert DataService._latest_required_report_period(date(2026, 8, 31)) == date(
        2026, 6, 30
    )


class FakeRawRepository:
    def __init__(self):
        self.dataset = None
        self.query = None

    def records(self, dataset, query):
        self.dataset = dataset
        self.query = query
        return [{"ts_code": "000001.SZ", "trade_date": "20260828"}]

    def count(self, dataset, query):
        return 1


def test_all_collectable_interfaces_have_a_public_data_path():
    service = InterfaceDataService(FakeRawRepository(), DATASETS)
    interfaces = service.list_interfaces()

    assert len(interfaces) == 201
    assert all(item["datasets"] for item in interfaces)
    assert all(
        item["records_url"]
        for item in interfaces
        if item["implementation_mode"] == "generic_raw"
    )


def test_raw_interface_query_uses_contract_filters_and_normalizes_dates():
    repository = FakeRawRepository()
    service = InterfaceDataService(repository, DATASETS)

    result = service.query_records(
        "adj_factor",
        filters={"ts_code": "000001.SZ"},
        date_field="trade_date",
        date_value=None,
        start_date="2026-08-01",
        end_date="20260828",
        limit=20,
        offset=0,
        include_total=True,
    )

    assert repository.dataset.table == "tushare_norm_adj_factor"
    assert repository.query.exact_filters == {"ts_code": "000001.SZ"}
    assert repository.query.start_date == date(2026, 8, 1)
    assert repository.query.end_date == date(2026, 8, 28)
    assert result["page"]["total"] == 1


def test_raw_interface_query_rejects_unknown_payload_filter():
    service = InterfaceDataService(FakeRawRepository(), DATASETS)

    with pytest.raises(InvalidQueryError, match="unsupported filters"):
        service.query_records(
            "adj_factor",
            filters={"raw_sql": "DROP TABLE daily"},
            date_field=None,
            date_value=None,
            start_date=None,
            end_date=None,
            limit=100,
            offset=0,
            include_total=False,
        )


def test_query_normalizes_index_dates():
    repository = FakeRepository()
    service = DataService(repository, DATASETS)

    result = service.query_dataset(
        "index_daily",
        exact_filters={"ts_code": "000300.SH"},
        date_value=None,
        start_date="2026-01-02",
        end_date="20260131",
        limit=20,
        offset=0,
        include_total=True,
    )

    assert repository.last_query.start_date == date(2026, 1, 2)
    assert repository.last_query.end_date == date(2026, 1, 31)
    assert result["page"]["total"] == 1


def test_query_uses_date_objects_for_date_columns():
    repository = FakeRepository()
    service = DataService(repository, DATASETS)

    service.query_dataset(
        "stock_daily",
        exact_filters={"ts_code": "000001.SZ"},
        date_value="20260726",
        start_date=None,
        end_date=None,
        limit=10,
        offset=0,
        include_total=False,
    )

    assert repository.last_query.date == date(2026, 7, 26)


def test_query_rejects_unknown_filters():
    service = DataService(FakeRepository(), DATASETS)

    with pytest.raises(InvalidQueryError, match="unsupported filters"):
        service.query_dataset(
            "stock_daily",
            exact_filters={"raw_sql": "DROP TABLE daily"},
            date_value=None,
            start_date=None,
            end_date=None,
            limit=100,
            offset=0,
            include_total=False,
        )


def test_stock_research_pack_aggregates_governed_datasets_without_advice():
    repository = FakeRepository()
    service = DataService(repository, DATASETS)

    result = service.stock_research_pack(
        "300750.SZ",
        lookback_days=90,
        benchmark="399006.SZ",
        financial_periods=4,
        as_of=date(2026, 9, 8),
    )

    assert result["meta"]["start_date"] == date(2026, 6, 11)
    assert result["meta"]["benchmark"] == "399006.SZ"
    assert result["data"]["profile"]["basic"]["ts_code"] == "300750.SZ"
    assert result["data"]["market"]["benchmark_daily"][0]["ts_code"] == "399006.SZ"
    assert result["data"]["market"]["adjustment_factors"]
    assert result["data"]["market"]["northbound_holding"]
    assert result["data"]["fundamentals"]["indicators"]
    assert result["data"]["ownership_and_events"]["top_holders"]
    assert result["data"]["ownership_and_events"]["related_news"][0]["content"] == "宁德时代最新经营情况。"
    assert repository.news_query["start_date"] == date(2026, 6, 11)
    assert repository.news_query["end_date"] == date(2026, 9, 8)
    provenance = {item["dataset"]: item for item in result["meta"]["provenance"]}
    assert "adj_factor" in provenance
    assert "hk_hold" in provenance
    assert "latest_value_in_pack" in provenance["stock_daily"]
    assert "earliest_value_in_pack" in provenance["stock_daily"]
    assert result["meta"]["external_data_needed"][0]["topic"] == "official_company_announcements"
    assert "advice" not in result


def test_stock_research_pack_enforces_announcement_cutoff_for_historical_view():
    class CapturingRepository(FakeRepository):
        def __init__(self):
            super().__init__()
            self.queries = []

        def records(self, dataset, query):
            self.queries.append((dataset.name, query))
            return super().records(dataset, query)

    repository = CapturingRepository()
    service = DataService(repository, DATASETS)

    result = service.stock_research_pack(
        "300750.SZ",
        lookback_days=90,
        financial_periods=4,
        as_of=date(2024, 4, 30),
    )

    by_dataset = {name: query for name, query in repository.queries}
    for dataset in (
        "income",
        "balancesheet",
        "cashflow",
        "financial_indicator",
        "forecast",
        "express",
        "stk_holdernumber",
        "top10_holders",
        "dividend",
    ):
        assert by_dataset[dataset].as_of == date(2024, 4, 30)
        assert by_dataset[dataset].end_date == date(2024, 4, 30)
    assert result["meta"]["quality"]["point_in_time_safe"] is False
    assert result["meta"]["quality"]["point_in_time_warnings"] == [
        "stock_basic",
        "stock_company",
    ]


def test_dataset_as_of_requires_and_uses_declared_availability_column():
    repository = FakeRepository()
    service = DataService(repository, DATASETS)

    service.query_dataset(
        "income",
        exact_filters={"ts_code": "300750.SZ"},
        date_value=None,
        start_date=None,
        end_date="2024-03-31",
        as_of="2024-04-30",
        limit=10,
        offset=0,
        include_total=False,
    )

    assert repository.last_query.as_of == date(2024, 4, 30)
    with pytest.raises(InvalidQueryError, match="does not support as_of"):
        service.query_dataset(
            "stock_basic",
            exact_filters={"ts_code": "300750.SZ"},
            date_value=None,
            start_date=None,
            end_date=None,
            as_of="2024-04-30",
            limit=10,
            offset=0,
            include_total=False,
        )


class SectorRepository(FakeRepository):
    def records(self, dataset, query):
        self.last_dataset = dataset
        self.last_query = query
        code = query.exact_filters.get("ts_code")
        constituent = query.exact_filters.get("con_code")
        rows = {
            "ths_index": [
                {
                    "ts_code": "885001.TI",
                    "name": "人工智能",
                    "type": "概念指数",
                    "count": 88,
                },
                {
                    "ts_code": "885002.TI",
                    "name": "银行",
                    "type": "行业指数",
                    "count": 42,
                },
            ],
            "industry_daily": [
                {
                    "ts_code": "885001.TI",
                    "trade_date": date(2026, 9, 8),
                    "close": 1234.5,
                    "pct_change": 1.2,
                },
                {
                    "ts_code": "885001.TI",
                    "trade_date": date(2026, 9, 7),
                    "close": 1220.0,
                    "pct_change": 0.5,
                },
            ],
            "ths_member": [
                {
                    "ts_code": "885001.TI",
                    "con_code": "300750.SZ",
                    "con_name": "宁德时代",
                    "weight": 8.5,
                    "in_date": "20200101",
                    "out_date": None,
                },
                {
                    "ts_code": "885001.TI",
                    "con_code": "000001.SZ",
                    "con_name": "平安银行",
                    "weight": 1.2,
                    "in_date": "20200101",
                    "out_date": None,
                },
            ],
            "moneyflow_cnt_ths": [
                {
                    "ts_code": "885001.TI",
                    "trade_date": date(2026, 9, 8),
                    "net_amount": 10.0,
                }
            ],
        }.get(dataset.name, [])
        if code:
            rows = [row for row in rows if row.get("ts_code") == code]
        if constituent:
            rows = [row for row in rows if row.get("con_code") == constituent]
        return rows[query.offset : query.offset + query.limit]


def test_sector_research_service_normalizes_vendor_data():
    service = DataService(SectorRepository(), DATASETS)

    listed = service.list_sectors(provider="ths", query="人工", limit=10)
    pack = service.sector_research_pack(
        "ths", "885001.TI", lookback_days=90,
        member_limit=100, as_of=date(2026, 9, 8),
    )

    assert listed["meta"]["matched"] == 1
    assert listed["data"][0]["name"] == "人工智能"
    assert listed["data"][0]["category"] == "概念指数"
    assert pack["data"]["profile"]["provider"] == "ths"
    assert pack["data"]["latest"]["trade_date"] == date(2026, 9, 8)
    assert pack["data"]["members"][0]["ts_code"] == "300750.SZ"
    assert pack["meta"]["quality"]["status"] == "ready"


def test_stock_sector_membership_and_peer_discovery_are_explainable():
    service = DataService(SectorRepository(), DATASETS)

    memberships = service.stock_sectors(
        "300750.SZ", provider="ths", as_of=date(2026, 9, 8)
    )
    peers = service.stock_peers(
        "300750.SZ", provider="ths", as_of=date(2026, 9, 8),
        max_sectors=5, limit=20,
    )

    assert memberships["data"][0]["sector_code"] == "885001.TI"
    assert peers["data"][0]["ts_code"] == "000001.SZ"
    assert peers["data"][0]["shared_sector_count"] == 1
    assert peers["data"][0]["shared_sectors"][0]["name"] == "人工智能"


@pytest.mark.parametrize(
    ("lookback_days", "financial_periods"),
    [(29, 4), (731, 4), (90, 0), (90, 13)],
)
def test_stock_research_pack_rejects_unbounded_requests(
    lookback_days,
    financial_periods,
):
    service = DataService(FakeRepository(), DATASETS)

    with pytest.raises(InvalidQueryError):
        service.stock_research_pack(
            "300750.SZ",
            lookback_days=lookback_days,
            financial_periods=financial_periods,
        )
