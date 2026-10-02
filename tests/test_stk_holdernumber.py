from datetime import date

import pandas as pd

from collectors.stock.reference.stk_holdernumber import StkHoldernumberCollector
from service.data_service.registry import build_dataset_registry


def _collector() -> StkHoldernumberCollector:
    return StkHoldernumberCollector.__new__(StkHoldernumberCollector)


def test_transform_preserves_null_effective_date_with_stable_source_identity():
    source = pd.DataFrame(
        [
            {
                "ts_code": "300499.SZ",
                "ann_date": "20250225",
                "end_date": None,
                "holder_num": 12345,
            }
        ]
    )

    first = _collector().transform(source)
    second = _collector().transform(source.copy())

    assert first.iloc[0]["ann_date"] == date(2025, 2, 25)
    assert pd.isna(first.iloc[0]["end_date"])
    assert first.iloc[0]["source_key"] == second.iloc[0]["source_key"]
    assert len(first.iloc[0]["source_key"]) == 32


def test_transform_distinguishes_separate_announcements_for_same_period():
    source = pd.DataFrame(
        [
            {
                "ts_code": "300750.SZ",
                "ann_date": "20250101",
                "end_date": "20241231",
                "holder_num": 100,
            },
            {
                "ts_code": "300750.SZ",
                "ann_date": "20250102",
                "end_date": "20241231",
                "holder_num": 99,
            },
        ]
    )

    transformed = _collector().transform(source)

    assert transformed["source_key"].nunique() == 2


def test_public_dataset_keeps_business_filters_and_effective_date_contract():
    dataset = build_dataset_registry().get("stk_holdernumber")

    assert dataset.primary_keys == ("source_key",)
    assert set(dataset.exact_filters) == {
        "source_key",
        "ts_code",
        "ann_date",
        "end_date",
    }
    assert dataset.date_column == "end_date"
    assert dataset.default_order == ("end_date", "ann_date", "ts_code")


def test_lpr_dataset_uses_provider_neutral_canonical_view():
    dataset = build_dataset_registry().get("cn_lpr")

    assert dataset.table == "tushare_norm_shibor_lpr"
    assert dataset.read_table == "canonical_cn_lpr"
    assert dataset.description.startswith("LPR")
    assert dataset.source_ids == ("chinamoney", "tushare")
    assert dataset.merge_policy == (
        "official_source_precedence_by_publication_date"
    )
