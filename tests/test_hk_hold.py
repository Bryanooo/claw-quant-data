from collectors.base import BaseCollector
from collectors.contracts import CollectorResult
from collectors.stock.extra.hk_hold import HkHoldCollector


def _result(collector: HkHoldCollector, rows: int) -> CollectorResult:
    spec = collector.spec()
    return CollectorResult(
        collector_name=spec.qualified_name,
        collector_version=spec.version,
        api_name=spec.api_name,
        table_name=spec.table_name,
        fetched_rows=rows,
        stored_rows=rows,
        request_count=2,
        evidence={"verified": True, "verification_type": "offset_exhaustion"},
    )


def test_monthly_scope_is_split_into_bounded_offset_exhaustion_windows(monkeypatch):
    collector = HkHoldCollector.__new__(HkHoldCollector)
    calls = []

    def run_chunk(self, **kwargs):
        calls.append(kwargs)
        return _result(collector, 10)

    monkeypatch.setattr(BaseCollector, "run_offset_paginated", run_chunk)

    result = collector.run_offset_paginated(
        start_date="20240501",
        end_date="20240531",
        page_size=3800,
        max_pages=200,
    )

    assert [(item["start_date"], item["end_date"]) for item in calls] == [
        ("20240501", "20240507"),
        ("20240508", "20240514"),
        ("20240515", "20240521"),
        ("20240522", "20240528"),
        ("20240529", "20240531"),
    ]
    assert all(item["page_size"] == 3800 for item in calls)
    assert result.fetched_rows == result.stored_rows == 50
    assert result.request_count == 10
    assert result.evidence["verified"] is True
    assert result.evidence["verification_type"] == (
        "bounded_date_windows_with_offset_exhaustion"
    )


def test_seven_day_scope_uses_normal_offset_path(monkeypatch):
    collector = HkHoldCollector.__new__(HkHoldCollector)
    calls = []

    def run_chunk(self, **kwargs):
        calls.append(kwargs)
        return _result(collector, 3)

    monkeypatch.setattr(BaseCollector, "run_offset_paginated", run_chunk)

    result = collector.run_offset_paginated(
        start_date="2024-05-01",
        end_date="2024-05-07",
        page_size=3800,
        max_pages=200,
    )

    assert len(calls) == 1
    assert calls[0]["start_date"] == "2024-05-01"
    assert calls[0]["end_date"] == "2024-05-07"
    assert result.fetched_rows == 3
