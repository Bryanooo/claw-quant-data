import pandas as pd
from types import SimpleNamespace
import pytest

from collectors.index.basic import IndexBasicCollector
from collectors.tushare_raw import IncompleteCollectionError


def _collector_without_init() -> IndexBasicCollector:
    return object.__new__(IndexBasicCollector)


def test_full_snapshot_partitions_csi_and_replaces_atomically(monkeypatch):
    collector = _collector_without_init()
    calls = []
    stored = []

    def fetch(**params):
        calls.append(params)
        market = params["market"]
        category = params.get("category")
        if market == "CSI" and category is None:
            return pd.DataFrame([{
                "ts_code": "000001.CSI",
                "market": "CSI",
                "category": "主题指数",
            }])
        if market == "CSI" and category == "主题指数":
            return pd.DataFrame([{
                "ts_code": "000001.CSI",
                "market": "CSI",
                "category": "主题指数",
            }])
        if market != "CSI":
            return pd.DataFrame([{
                "ts_code": f"{market}.IDX",
                "market": market,
                "category": "测试",
            }])
        return pd.DataFrame()

    monkeypatch.setattr(collector, "fetch", fetch)
    collector.pro = SimpleNamespace(index_basic=lambda **params: fetch(**params))
    monkeypatch.setattr(collector, "transform", lambda frame: frame)
    monkeypatch.setattr(
        collector,
        "store_snapshot",
        lambda frame: stored.append(frame.copy()) or len(frame),
    )

    rows = collector.collect_full_snapshot()

    assert rows == len(IndexBasicCollector.MARKETS)
    assert len(stored) == 1
    assert stored[0]["ts_code"].is_unique
    assert {"market": "CSI"} in calls
    assert {"market": "CSI", "category": "主题指数"} in calls


def test_partition_at_provider_limit_fails_before_storage(monkeypatch):
    collector = _collector_without_init()
    monkeypatch.setattr(
        collector,
        "fetch",
        lambda **_params: pd.DataFrame({
            "ts_code": [f"{index}.CSI" for index in range(8000)],
            "market": ["CSI"] * 8000,
        }),
    )

    with pytest.raises(IncompleteCollectionError, match="8000-row limit"):
        collector._checked_fetch(market="CSI", category="主题指数")


def test_complete_snapshot_protocol_returns_verified_evidence(monkeypatch):
    collector = _collector_without_init()
    collector._request_count = 7
    monkeypatch.setattr(collector, "collect_full_snapshot", lambda: 123)
    monkeypatch.setattr(collector, "_raw_archive_evidence", lambda: {"requests": 7})
    monkeypatch.setattr(
        collector,
        "_sanitization_evidence",
        lambda: {"nul_characters_removed": 0, "affected_fields": []},
    )

    result = collector.run_complete_snapshot()

    assert result.fetched_rows == result.stored_rows == 123
    assert result.evidence["verified"] is True
    assert result.evidence["verification_type"] == (
        "market_and_csi_category_partitions"
    )


def test_base_run_rejects_capped_specialized_response_before_storage(monkeypatch):
    collector = _collector_without_init()
    collector.retry_max = 1
    collector.retry_interval = 0
    collector.logger = type(
        "Logger",
        (),
        {"info": lambda *_args, **_kwargs: None, "error": lambda *_args, **_kwargs: None},
    )()
    monkeypatch.setattr(
        collector,
        "fetch",
        lambda **_params: pd.DataFrame({
            "ts_code": [f"{index}.CSI" for index in range(8000)],
            "market": ["CSI"] * 8000,
        }),
    )
    monkeypatch.setattr(
        collector,
        "store",
        lambda _frame: pytest.fail("capped response must not reach storage"),
    )

    with pytest.raises(Exception, match="8000-row limit"):
        collector.run(market="CSI")
