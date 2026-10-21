"""Tests for the 数据派生 (derived indicators) inventory API."""

from __future__ import annotations

import pytest

from service.data_service.derivations import (
    derivation_inventory,
    derivation_summary,
    on_demand_catalog,
)
from service.orchestration_v2.catalog import transformation_task_blueprints


def test_inventory_covers_every_transformation_blueprint():
    blueprints = {b.task_key for b in transformation_task_blueprints()}
    items = {item["key"] for item in derivation_inventory()}
    assert items == blueprints
    assert len(items) == 15


def test_status_partition_matches_implementation_registry():
    items = {item["key"]: item for item in derivation_inventory()}
    assert items["technical_factor_snapshot"]["status"] == "implemented"
    assert items["fama_french_daily"]["status"] == "implemented"
    # Materialized through the collector runtime rather than V2 dispatch.
    assert items["ggt_monthly"]["status"] == "implemented"
    assert items["market_breadth"]["status"] == "planned"
    assert items["macro_regime"]["status"] == "planned"


def test_inputs_are_resolved_to_governed_datasets_or_derived_chains():
    items = {item["key"]: item for item in derivation_inventory()}
    ff_inputs = {row["name"] for row in items["fama_french_daily"]["inputs"]}
    assert {"stock_daily", "stock_daily_basic", "stock_st"} <= ff_inputs
    # sector_rotation consumes the sector_breadth derived dataset.
    rotation_inputs = items["sector_rotation"]["inputs"]
    chained = [row for row in rotation_inputs if row["kind"] == "derived"]
    assert any(row["name"] == "sector_breadth" for row in chained)


def test_implemented_tasks_carry_algorithm_and_frequency_notes():
    items = {item["key"]: item for item in derivation_inventory()}
    for key in ("technical_factor_snapshot", "fama_french_daily", "ggt_monthly"):
        assert items[key]["algorithm"], key
        assert items[key]["frequency"], key
    planned = items["market_breadth"]
    assert "待固化" in planned["algorithm"]


def test_summary_counts_are_consistent():
    summary = derivation_summary()
    items = derivation_inventory()
    assert summary["tasks"] == len(items)
    implemented = sum(item["status"] == "implemented" for item in items)
    assert summary["by_status"]["implemented"] == implemented
    assert summary["by_status"]["planned"] == len(items) - implemented
    assert summary["on_demand_endpoints"] == len(on_demand_catalog())


def test_on_demand_catalog_exposes_research_endpoints():
    rows = on_demand_catalog()
    assert rows, "research on-demand catalog must not be empty"
    assert all(row["key"].startswith("/api/v1/research/") for row in rows)
    assert all(row["title"] for row in rows)


def test_date_coverage_degrades_without_database(monkeypatch):
    import service.data_service.derivations as module

    def _fail():
        raise RuntimeError("no database in unit tests")

    monkeypatch.setattr(module, "get_conn", _fail, raising=False)
    rows = derivation_inventory()
    coverage = module.date_coverage(rows)
    assert set(coverage) == {row["key"] for row in rows}
    assert all(value is None for value in coverage.values())
