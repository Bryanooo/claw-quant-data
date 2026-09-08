import pandas as pd
import pytest

from collectors.base import NonRetryableCollectorError
from collectors.index.ths_member import ThsMemberCollector
from collectors.tushare_raw import IncompleteCollectionError


def _collector_without_init() -> ThsMemberCollector:
    return object.__new__(ThsMemberCollector)


def test_unbounded_member_request_is_rejected_before_network(monkeypatch):
    collector = _collector_without_init()
    monkeypatch.setattr(
        "collectors.base.BaseCollector.fetch",
        lambda *_args, **_kwargs: pytest.fail("unbounded request must not reach Tushare"),
    )

    with pytest.raises(NonRetryableCollectorError, match="requires ts_code or con_code"):
        collector.fetch()


def test_member_partition_must_be_echoed_and_below_cap():
    collector = _collector_without_init()
    frame = pd.DataFrame([{"ts_code": "885800.TI", "con_code": "000001.SZ"}])
    collector.validate_response(frame, {"ts_code": "885800.TI"})

    with pytest.raises(IncompleteCollectionError, match="ignored the ts_code"):
        collector.validate_response(frame, {"ts_code": "885801.TI"})

    capped = pd.DataFrame({
        "ts_code": ["885800.TI"] * 6000,
        "con_code": [f"{index:06d}.SZ" for index in range(6000)],
    })
    with pytest.raises(IncompleteCollectionError, match="6000-row cap"):
        collector.validate_response(capped, {"ts_code": "885800.TI"})


def test_member_storage_reconciles_only_the_requested_board(monkeypatch):
    collector = _collector_without_init()
    observed = {}
    monkeypatch.setattr(
        collector,
        "store_partition_snapshot",
        lambda frame, **options: observed.update(options) or len(frame),
    )

    rows = collector.store(pd.DataFrame([
        {"ts_code": "885800.TI", "con_code": "000001.SZ"},
    ]))

    assert rows == 1
    assert observed == {"partition_columns": ("ts_code",)}
