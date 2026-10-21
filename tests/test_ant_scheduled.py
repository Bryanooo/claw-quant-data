"""Contracts for the 蚂蚁数据源 scheduled-pull allow-list."""

from service.data_service.dependencies import (
    _financial_data_scheduled_tasks,
    interface_inventory,
)
from service.orchestration_v2.catalog import acquisition_task_blueprints
from service.source_connectors.ant_scheduled import (
    SCHEDULED_ROUTES,
    _row_from_record,
    _row_hash,
    _TYPED_COLUMNS,
)
from service.source_connectors.registry import SOURCE_REGISTRY

from datetime import date


EXPECTED_TASKS = {
    "ant_hot_stock_rank": ("altdata.hot-stock-rank", "daily", "ant_hot_stock_rank"),
    "ant_hot_plate_rank": ("altdata.hot-plate-rank", "daily", "ant_hot_plate_rank"),
    "ant_equity_structure": ("stock_fnd.equity-structure", "weekly", "ant_equity_structure"),
    "ant_free_float": ("stock_fnd.free-float", "weekly", "ant_free_float"),
    "ant_actual_controller": ("stock_fnd.actual-controller", "monthly", "ant_actual_controller"),
    "ant_controlling_shareholder": (
        "stock_fnd.controlling-shareholder", "monthly", "ant_controlling_shareholder",
    ),
    "ant_style_classification": (
        "stock_fnd.style-classification", "monthly", "ant_style_classification",
    ),
}


def test_scheduled_routes_are_registered_as_scheduled_pull_endpoints():
    for task_key, (endpoint_key, cadence, _) in EXPECTED_TASKS.items():
        endpoint = SOURCE_REGISTRY.get_endpoint("financial_data", endpoint_key)
        assert endpoint.acquisition_mode.value == "scheduled_pull", task_key
        assert endpoint.cadence == cadence, task_key
        spec = SCHEDULED_ROUTES[endpoint_key]
        assert spec.cadence == cadence
        assert spec.table.startswith("ant_norm_")


def test_scheduled_blueprints_are_registered():
    tasks = {
        task.task_key: task for task in acquisition_task_blueprints()
        if task.task_key.startswith("ant_")
    }
    assert set(tasks) == set(EXPECTED_TASKS)
    for task_key, (endpoint_key, cadence, dataset) in EXPECTED_TASKS.items():
        task = tasks[task_key]
        assert task.cadence == cadence
        assert task.output_datasets == (dataset,)
        refs = [(ref.source_id, ref.endpoint_key) for ref in task.endpoints]
        assert refs == [("financial_data", endpoint_key)]


def test_inventory_marks_scheduled_ant_routes_active_with_tasks():
    items = {item["key"]: item for item in interface_inventory()}
    route = "/api/v1/altdata/hot-stock-rank"
    row = items[route]
    assert row["status"] == "active"
    assert row["acquisition_kind"] == "scheduled"
    assert row["cadence"] == "daily"
    assert row["tasks"] == [{
        "task_key": "ant_hot_stock_rank",
        "cadence": "daily",
        "output_datasets": ["ant_hot_stock_rank"],
        "table": "ant_norm_hot_stock_rank",
    }]
    assert row["tables"] == ["ant_norm_hot_stock_rank"]
    # Unrelated ant routes stay query-through / disabled.
    assert items["/api/v1/stock/tra-variant"]["status"] == "ant_primary"


def test_scheduled_task_route_index_matches_endpoints():
    tasks = _financial_data_scheduled_tasks()
    for endpoint_key, spec in SCHEDULED_ROUTES.items():
        assert spec.route in tasks


def test_row_normalization_and_hash_are_stable():
    spec = SCHEDULED_ROUTES["altdata.hot-stock-rank"]
    record = {
        "symbol": "300308", "begin_date": "2026-10-21", "sec_name": "中际旭创",
        "score": 91.2, "rank_raise": 3, "rank": 1,
    }
    row = _row_from_record(spec, record, date(2026, 10, 21))
    assert row["trade_date"] == date(2026, 10, 21)
    assert row["rank"] == 1
    assert row["score"] == 91.2
    assert row["payload"]["symbol"] == "300308"
    assert _row_hash(spec.table, row) == _row_hash(spec.table, dict(row))
    assert set(_TYPED_COLUMNS[spec.table]) <= set(row)
