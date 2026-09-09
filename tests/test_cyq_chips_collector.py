from datetime import date, timedelta

import pandas as pd
import pytest

from collectors.stock.extra.cyq_chips import CyqChipsCollector
from collectors.tushare_raw import IncompleteCollectionError


def _rows(start: date, count: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ts_code": "600722.SH",
                "trade_date": (start + timedelta(days=index // 100)).strftime(
                    "%Y%m%d"
                ),
                "price": float(index),
                "percent": 0.1,
            }
            for index in range(count)
        ]
    )


def test_cyq_chips_bisects_ambiguous_round_cap():
    calls = []
    start = date(2026, 8, 6)

    class FakePro:
        def cyq_chips(self, **params):
            calls.append(dict(params))
            if (
                params["start_date"] == "20260806"
                and params["end_date"] == "20260905"
            ):
                return _rows(start, 2000)
            if params["end_date"] == "20260821":
                return _rows(start, 889)
            return _rows(date(2026, 8, 22), 1111)

    collector = object.__new__(CyqChipsCollector)
    collector.pro = FakePro()
    frame = collector.fetch(
        ts_code="600722.SH",
        start_date="20260806",
        end_date="20260905",
    )

    assert len(frame) == 2000
    assert len(calls) == 3
    assert calls[1]["end_date"] == "20260821"
    assert calls[2]["start_date"] == "20260822"
    proof = collector.partition_completion_evidence()
    assert proof["verified"] is True
    assert proof["leaf_scopes"] == 2
    assert proof["rows_fetched"] == 2000


def test_cyq_chips_keeps_single_verified_window():
    calls = []

    class FakePro:
        def cyq_chips(self, **params):
            calls.append(dict(params))
            return _rows(date(2026, 8, 6), 127)

    collector = object.__new__(CyqChipsCollector)
    collector.pro = FakePro()
    frame = collector.fetch(
        ts_code="600722.SH",
        start_date="2026-08-06",
        end_date="2026-08-07",
    )

    assert len(frame) == 127
    assert calls == [
        {
            "ts_code": "600722.SH",
            "start_date": "20260806",
            "end_date": "20260807",
        }
    ]
    assert collector.partition_completion_evidence()["leaf_scopes"] == 1


def test_cyq_chips_rejects_a_capped_single_day():
    class FakePro:
        def cyq_chips(self, **_params):
            return pd.DataFrame(
                {
                    "ts_code": ["600722.SH"] * 2000,
                    "trade_date": ["20260806"] * 2000,
                    "price": list(range(2000)),
                    "percent": [0.1] * 2000,
                }
            )

    collector = object.__new__(CyqChipsCollector)
    collector.pro = FakePro()
    with pytest.raises(IncompleteCollectionError, match="suspicious round cap"):
        collector.fetch(
            ts_code="600722.SH",
            start_date="20260806",
            end_date="20260806",
        )


def test_cyq_chips_rejects_an_ignored_date_window():
    class FakePro:
        def cyq_chips(self, **_params):
            return _rows(date(2026, 7, 1), 10)

    collector = object.__new__(CyqChipsCollector)
    collector.pro = FakePro()
    with pytest.raises(IncompleteCollectionError, match="ignored the requested"):
        collector.fetch(
            ts_code="600722.SH",
            start_date="20260806",
            end_date="20260807",
        )
