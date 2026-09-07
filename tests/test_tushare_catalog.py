import json
import re
import pandas as pd
from contextlib import nullcontext
import pytest

from collectors.base import BaseCollector
from collectors.tushare_raw import (
    CatalogRawCollector,
    IncompleteCollectionError,
    PaginationStalledError,
)
from service.tushare_normalization import NormalizationResult
from service.config import PROJECT_ROOT
from service.tushare_catalog import (
    InterfaceNotCollectableError,
    TushareInterfaceCatalog,
)
from service.tushare_policy import TusharePolicyRegistry
from scripts.report_tushare_data_presence import _implementation_tables


def test_catalog_docs_are_complete_and_do_not_contain_token():
    contracts_path = PROJECT_ROOT / "docs" / "tushare" / "contracts.json"
    payload = json.loads(contracts_path.read_text(encoding="utf-8"))
    contracts = payload["interfaces"]
    names = {item["api_name"] for item in contracts}
    markdown_files = {
        path.stem for path in (PROJECT_ROOT / "docs" / "tushare" / "interfaces").glob("*.md")
    }

    assert len(names) >= 231
    assert markdown_files == names
    assert "daily" in names
    assert "limit_cpt_list" in names
    assert "limit_list_cpt" not in names
    assert "${TUSHARE_TOKEN}" in (
        PROJECT_ROOT / "docs" / "tushare" / "interfaces" / "daily.md"
    ).read_text(encoding="utf-8")
    serialized_contracts = contracts_path.read_text(encoding="utf-8")
    assert not re.search(
        r"(?:tushare[_ -]?token|token)\s*[:=]\s*[0-9a-f]{32,}",
        serialized_contracts,
        flags=re.IGNORECASE,
    )


def test_every_authorized_read_interface_has_an_implementation():
    contracts = TushareInterfaceCatalog().list()
    missing = [
        item.api_name
        for item in contracts
        if item.collectable and item.implementation["mode"] == "unavailable"
    ]

    assert missing == []
    assert sum(item.collectable for item in contracts) >= 180


def test_presence_report_never_attributes_shared_raw_total_to_one_api():
    assert all(
        "tushare_raw_record" not in tables
        for tables in _implementation_tables().values()
    )


def test_every_interface_has_an_operational_collection_policy():
    contracts = TushareInterfaceCatalog().list()
    policies = TusharePolicyRegistry().list()

    assert {item.api_name for item in policies} == {item.api_name for item in contracts}
    collectable = [item for item in contracts if item.collectable]
    assert len(collectable) == 200
    assert all(TusharePolicyRegistry().get(item.api_name).page_size > 0 for item in collectable)
    assert TusharePolicyRegistry().get("fund_adj").pagination_mode == "offset"
    assert TusharePolicyRegistry().get("etf_sh_cons").pagination_mode == "offset"
    assert TusharePolicyRegistry().get("etf_sz_cons").pagination_mode == "offset"
    assert TusharePolicyRegistry().get("fund_share").pagination_mode == "offset"
    assert TusharePolicyRegistry().get("share_float").pagination_mode == "offset"
    assert TusharePolicyRegistry().get("stk_limit").pagination_mode == "offset"
    assert TusharePolicyRegistry().get("fund_basic").pagination_mode == "offset"
    assert TusharePolicyRegistry().get("index_weekly").pagination_mode == "offset"
    assert TusharePolicyRegistry().get("index_monthly").pagination_mode == "offset"
    assert TusharePolicyRegistry().get("stk_mins").automatic_safe is False
    assert TusharePolicyRegistry().get("factor_value").automatic_safe is False
    assert TusharePolicyRegistry().get("fund_basic").automatic_safe is False
    assert TusharePolicyRegistry().get("fut_weekly_detail").parameter_strategy == "manual"


def test_daily_policy_preserves_official_limit_and_live_verified_pagination():
    policy = TusharePolicyRegistry().get("daily")

    assert policy.parameter_strategy == "trade_date"
    assert policy.pagination_mode == "offset"
    assert policy.documented_row_limit == 6000
    assert policy.page_size == 5000


def test_catalog_blocks_denied_and_mutating_interfaces():
    catalog = TushareInterfaceCatalog()

    with pytest.raises(InterfaceNotCollectableError):
        catalog.require_collectable("anns_d")
    with pytest.raises(InterfaceNotCollectableError, match="write interface"):
        catalog.require_collectable("p_delete")


def test_raw_collector_uses_dynamic_tushare_query(monkeypatch):
    monkeypatch.setattr(BaseCollector, "__init__", lambda self: None)
    monkeypatch.setattr(CatalogRawCollector, "_wait_for_rate_slot", lambda self: None)
    collector = CatalogRawCollector("cn_cpi")

    class FakePro:
        def query(self, api_name, **parameters):
            assert api_name == "cn_cpi"
            assert parameters == {"start_m": "202601", "end_m": "202606"}
            return pd.DataFrame([{"month": "202601", "nt_val": 101.2}])

    collector.pro = FakePro()
    frame = collector.fetch(start_m="202601", end_m="202606")

    assert len(frame) == 1
    assert collector._request_parameters == {
        "start_m": "202601",
        "end_m": "202606",
    }


def test_raw_collector_reserves_distributed_rate_slot(monkeypatch):
    monkeypatch.setattr(BaseCollector, "__init__", lambda self: None)
    collector = CatalogRawCollector("cn_cpi")
    reservations = []
    monkeypatch.setattr(
        "collectors.tushare_raw.reserve_tushare_request",
        lambda api_name, **options: reservations.append((api_name, options)),
    )

    collector._wait_for_rate_slot()

    assert reservations == [
        ("cn_cpi", {"interface_interval": collector.policy.min_interval_seconds})
    ]


def test_raw_fetch_uses_logical_scope_for_storage_identity(monkeypatch):
    monkeypatch.setattr(BaseCollector, "__init__", lambda self: None)
    monkeypatch.setattr(CatalogRawCollector, "_wait_for_rate_slot", lambda self: None)
    collector = CatalogRawCollector("fund_adj")

    class FakePro:
        def query(self, _api_name, **_parameters):
            return pd.DataFrame([{"ts_code": "510300.SH", "trade_date": "20260828"}])

    collector.pro = FakePro()
    collector.fetch(ts_code="510300.SH", limit=100, offset=200)

    assert collector._request_parameters == {"ts_code": "510300.SH"}


def test_raw_store_deduplicates_equal_payloads(monkeypatch):
    monkeypatch.setattr(BaseCollector, "__init__", lambda self: None)
    collector = CatalogRawCollector("cn_cpi")
    collector._request_parameters = {"start_m": "202601"}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class FakeConnection:
        def __init__(self):
            self.committed = False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            self.committed = True

        def rollback(self):
            raise AssertionError("rollback should not be called")

        def close(self):
            pass

    connection = FakeConnection()
    captured = {}

    def fake_execute_values(_cursor, _statement, values, page_size):
        captured["values"] = values
        captured["page_size"] = page_size

    monkeypatch.setattr("collectors.tushare_raw.get_db_conn", lambda: connection)
    monkeypatch.setattr(
        "collectors.tushare_raw.psycopg2.extras.execute_values", fake_execute_values
    )
    monkeypatch.setattr(collector, "_normalize_stored_rows", lambda *_args: None)

    rows = collector.store(
        pd.DataFrame(
            [
                {"month": "202601", "value": 101.2},
                {"month": "202601", "value": 101.2},
            ]
        )
    )

    assert rows == 1
    assert len(captured["values"]) == 1
    assert connection.committed is True


def test_generic_collector_records_typed_normalization_evidence(monkeypatch):
    monkeypatch.setattr(BaseCollector, "__init__", lambda self: None)
    collector = CatalogRawCollector("adj_factor")

    class FakeNormalizer:
        def normalize(self, api_name, request_hash, records, **kwargs):
            assert api_name == "adj_factor"
            assert request_hash == "r" * 64
            assert records == [("h" * 64, {"ts_code": "000001.SZ"})]
            return NormalizationResult(
                api_name=api_name,
                raw_rows=1,
                normalized_rows=1,
                quarantined_rows=0,
                unknown_fields=(),
                missing_fields=(),
            )

        def resolve_superseded_scope(self, api_name, request_parameters):
            return 0

    collector.normalizer = FakeNormalizer()
    collector._normalize_stored_rows(
        "r" * 64,
        [("h" * 64, {"ts_code": "000001.SZ"})],
    )

    assert collector.normalization_evidence["normalized_rows"] == 1
    assert collector.normalization_evidence["complete"] is True


def test_complete_collection_rejects_unbounded_partition(monkeypatch):
    monkeypatch.setattr(BaseCollector, "__init__", lambda self: None)
    collector = CatalogRawCollector("cn_cpi")

    with pytest.raises(IncompleteCollectionError, match="month partition"):
        collector.collect_complete()


def test_complete_collection_rejects_undocumented_round_cap(monkeypatch):
    monkeypatch.setattr(BaseCollector, "__init__", lambda self: None)
    collector = CatalogRawCollector("ci_index_member")

    def fake_collect(**_params):
        collector._last_fetch_count = 5000
        return 5000

    monkeypatch.setattr(collector, "collect", fake_collect)

    with pytest.raises(IncompleteCollectionError, match="suspicious round cap"):
        collector.collect_complete(l3_code="CI005835.CI")


def test_offset_pagination_checkpoints_every_page(monkeypatch):
    monkeypatch.setattr(BaseCollector, "__init__", lambda self: None)
    collector = CatalogRawCollector("fund_adj")
    pages = {
        0: (2, "page-1"),
        2: (1, "page-2"),
    }
    calls = []
    saved = []
    finished = []

    def fake_collect(**params):
        calls.append(params)
        collector._last_fetch_count, collector._last_page_hash = pages[params["offset"]]
        return collector._last_fetch_count

    monkeypatch.setattr(collector, "collect", fake_collect)
    monkeypatch.setattr(collector, "_scope_lock", lambda *_args: nullcontext())
    monkeypatch.setattr(
        collector,
        "_begin_checkpoint",
        lambda *_args, **_kwargs: {
            "next_offset": 0,
            "pages_completed": 0,
            "rows_fetched": 0,
            "rows_stored": 0,
            "last_page_hash": None,
        },
    )
    monkeypatch.setattr(
        collector,
        "_save_checkpoint",
        lambda *args, **kwargs: saved.append((args, kwargs)),
    )
    monkeypatch.setattr(collector, "_finish_checkpoint", lambda *args: finished.append(args))

    rows = collector.collect_paginated(page_size=2, max_pages=5, ts_code="510300.SH")

    assert rows == 3
    assert [item["offset"] for item in calls] == [0, 2]
    assert len(saved) == 2
    assert finished and finished[-1][1] == "success"
    assert collector.completion_evidence["verified"] is True
    assert collector.completion_evidence["rows_fetched"] == 3


def test_offset_pagination_detects_repeated_pages(monkeypatch):
    monkeypatch.setattr(BaseCollector, "__init__", lambda self: None)
    collector = CatalogRawCollector("fund_adj")

    def fake_collect(**_params):
        collector._last_fetch_count = 2
        collector._last_page_hash = "same-page"
        return 2

    monkeypatch.setattr(collector, "collect", fake_collect)
    monkeypatch.setattr(collector, "_scope_lock", lambda *_args: nullcontext())
    monkeypatch.setattr(
        collector,
        "_begin_checkpoint",
        lambda *_args, **_kwargs: {
            "next_offset": 0,
            "pages_completed": 0,
            "rows_fetched": 0,
            "rows_stored": 0,
            "last_page_hash": None,
        },
    )
    monkeypatch.setattr(collector, "_save_checkpoint", lambda *_args, **_kwargs: None)

    with pytest.raises(PaginationStalledError):
        collector.collect_paginated(page_size=2, max_pages=5)

    assert collector.completion_evidence["rows_stored"] == 2


def test_offset_pagination_detects_non_adjacent_page_cycle(monkeypatch):
    monkeypatch.setattr(BaseCollector, "__init__", lambda self: None)
    collector = CatalogRawCollector("fund_adj")
    signatures = iter(["page-a", "page-b", "page-a"])

    def fake_collect(**_params):
        collector._last_fetch_count = 2
        collector._last_page_hash = next(signatures)
        return 2

    monkeypatch.setattr(collector, "collect", fake_collect)
    monkeypatch.setattr(collector, "_scope_lock", lambda *_args: nullcontext())
    monkeypatch.setattr(
        collector,
        "_begin_checkpoint",
        lambda *_args, **_kwargs: {
            "next_offset": 0,
            "pages_completed": 0,
            "rows_fetched": 0,
            "rows_stored": 0,
            "last_page_hash": None,
        },
    )
    monkeypatch.setattr(collector, "_save_checkpoint", lambda *_args, **_kwargs: None)

    with pytest.raises(PaginationStalledError) as caught:
        collector.collect_paginated(page_size=2, max_pages=5)

    assert caught.value.rows_inserted == 4
    assert caught.value.rows_fetched == 4
