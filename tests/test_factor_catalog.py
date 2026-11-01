"""Canonical factor ownership and operator presentation contracts."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from service.data_service import factor_catalog as fc
from service.data_service.models import DatasetNotFoundError
from service.data_service.registry import DATASETS
from service.data_service.service import DataService
from service.data_service.interfaces import InterfaceDataService
from service.research.factor_inputs import factor_input_catalog
from service.research.local_factors.materializer import _load_exact_overlaps
from service.research.local_factors.ownership import (
    SHARED_TECHNICAL_FIELDS, TECHNICAL_ALIASES, technical_payload,
)
from service.research.local_factors.service import normalize_factor_names


def test_catalog_has_one_identity_per_value_and_all_aliases_resolve():
    definitions = fc.local_feature_definitions()
    names = {f["name"] for f in definitions}
    assert len(definitions) == len(names)
    assert len({f["id"] for f in definitions}) == len(names)
    assert sum(f["package"] == "Alpha101" for f in definitions) == 101
    assert sum(f["package"] == "Style171" for f in definitions) == 171
    assert {f["storage"] for f in definitions} == {"local_factor_snapshot"}
    for f in definitions:
        assert f["origin"] == "local"
        assert not f["fallback_allowed"]
        assert normalize_factor_names([f["name"], *f["aliases"]])
        assert not set(f["aliases"]) & names
    assert len(fc.CATEGORIES) == 11


def test_catalog_does_not_certify_values_or_infer_continuity(monkeypatch):
    def fake(sql, params=None):
        if "min(trade_date)" in sql:
            return [{"min_date": date(2026, 10, 9), "max_date": date(2026, 10, 22), "days": 10, "rows": 55752}]
        if "WITH latest" in sql:
            return [{"key": "232", "available": 5000, "total": 5570}]
        if "local_factor_validation" in sql:
            return [{"factor_position": 232, "validation_status": "review_required", "sample_size": 5000}]
        if "audit_status" in sql:
            return [{"audit_status": "partial", "securities": 5570}]
        raise AssertionError(sql)
    monkeypatch.setattr(fc, "query", fake)
    result = fc._build_catalog()
    assert result["audit"]["collection_retained"]
    assert not result["audit"]["external_values"]
    assert all(f["storage"] != "tushare_norm_factor_value" for f in result["factors"])
    rsi = next(f for f in result["factors"] if f["name"] == "rsi")
    assert rsi["available_securities"] == 5000
    assert rsi["availability"] == "has_values"
    assert rsi["validation"]["validation_status"] == "review_required"
    assert "min_date" not in rsi  # Table boundaries must not become factor coverage.


def test_technical_payload_cannot_duplicate_array_slots_or_aliases():
    original = {key: 3.0 for key in (*SHARED_TECHNICAL_FIELDS, *TECHNICAL_ALIASES)}
    original.update(ema_20=10.0, snapshot_date=date(2026, 10, 22), ts_code="300750.SZ")
    assert technical_payload(original) == {"ema_20": 10.0}


def test_missing_exact_results_never_enable_alternative_formula():
    row = {field: None for field in SHARED_TECHNICAL_FIELDS}
    row["ts_code"] = "300750.SZ"
    result = _load_exact_overlaps([row], pd.Index(["300750.SZ"]))
    assert set(result) == set(SHARED_TECHNICAL_FIELDS.values())
    assert all(np.isnan(series.iloc[0]) for series in result.values())


def test_provider_reference_is_collected_but_not_public():
    assert DATASETS.get("factor_value")  # Internal registry remains intact.
    service = DataService(None, DATASETS)
    assert "factor_value" not in {item["name"] for item in service.list_datasets()}
    with pytest.raises(DatasetNotFoundError):
        service.describe_dataset("factor_value")
    with pytest.raises(DatasetNotFoundError):
        InterfaceDataService(None, DATASETS).describe_interface("factor_value")
    assert '"factor_value"' not in __import__("json").dumps(factor_input_catalog())
