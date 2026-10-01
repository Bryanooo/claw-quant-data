from collectors.base import BaseCollector
from collectors.contracts import CollectorResult
from collectors.stock.reference.share_float import ShareFloatCollector


def _result(rows: int) -> CollectorResult:
    spec = ShareFloatCollector.spec()
    return CollectorResult(
        collector_name=spec.qualified_name,
        collector_version=spec.version,
        api_name=spec.api_name,
        table_name=spec.table_name,
        fetched_rows=rows,
        stored_rows=rows,
        request_count=1,
        evidence={
            "raw_archive": {
                "request_ids": [rows + 1],
                "logical_request_hashes": [f"hash-{rows}"],
            }
        },
    )


def test_large_exact_date_fans_out_inside_collector(monkeypatch):
    collector = object.__new__(ShareFloatCollector)
    monkeypatch.setattr(collector, "_stored_partition_rows", lambda _: 100_001)
    monkeypatch.setattr(
        collector, "_stock_universe", lambda _: ["000001.SZ", "600000.SH"]
    )
    monkeypatch.setattr(
        collector,
        "_completed_stock_codes",
        lambda _date, page_size: {"000001.SZ"},
    )
    requests = []

    def run_partition(_collector, **parameters):
        requests.append(parameters)
        return _result(2 if parameters["ts_code"] == "000001.SZ" else 0)

    monkeypatch.setattr(BaseCollector, "run_offset_paginated", run_partition)

    result = collector.run_offset_paginated(
        page_size=1000,
        max_pages=1000,
        start_date="20240219",
        end_date="20240219",
    )

    assert [item["ts_code"] for item in requests] == ["600000.SH"]
    assert all(item["start_date"] == "20240219" for item in requests)
    assert result.fetched_rows == 0
    assert result.request_count == 1
    assert result.evidence["verified"] is True
    assert result.evidence["entities_completed"] == 2
    assert result.evidence["entities_empty"] == 1
    assert result.evidence["entities_resumed"] == 1
    assert result.evidence["verification_type"] == "stock_fanout_offset_exhaustion"


def test_normal_partition_keeps_market_wide_offset_path(monkeypatch):
    collector = object.__new__(ShareFloatCollector)
    monkeypatch.setattr(collector, "_stored_partition_rows", lambda _: 42)
    calls = []

    def run_partition(_collector, **parameters):
        calls.append(parameters)
        return _result(42)

    monkeypatch.setattr(BaseCollector, "run_offset_paginated", run_partition)

    result = collector.run_offset_paginated(
        page_size=1000,
        max_pages=1000,
        start_date="20260928",
        end_date="20260928",
    )

    assert result.fetched_rows == 42
    assert len(calls) == 1
    assert "ts_code" not in calls[0]
