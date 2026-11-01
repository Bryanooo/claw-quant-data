"""Cross-checks between the control plane and the registry it came from."""

from __future__ import annotations

from fastapi.testclient import TestClient

from service.api.app import create_app
from service.api.dependencies import get_orchestration_v2_repository
from service.orchestration_v2.consistency import (
    cadence_drift,
    consistency_report,
    cron_frequency,
    derivation_rollout_drift,
    dispatch_drift,
    endpoint_registry_drift,
)

DAILY_CRON = "15 19,23 * * *"
WEEKLY_CRON = "30 20 * * 5"
MONTHLY_CRON = "30 20 1 * *"
QUARTERLY_CRON = "0 21 1 1,4,7,10 *"


def _definition(task_key: str, *, cadence: str, mode: str, expression: str | None):
    return {
        "task_key": task_key,
        "lifecycle_status": "active",
        "cadence": cadence,
        "schedule_mode": mode,
        "schedule_expression": expression,
    }


class FakeRepository:
    def __init__(self, *, installed=True, definitions=None, pairs=None):
        self._installed = installed
        self._definitions = definitions or []
        self._pairs = pairs or []

    def schema_exists(self) -> bool:
        return self._installed

    def list_definitions(self, *, limit=50, **kwargs):
        return list(self._definitions)

    def endpoint_registry_pairs(self):
        return list(self._pairs)


def test_cron_frequency_classifies_compiled_expressions():
    assert cron_frequency(DAILY_CRON) == "daily"
    assert cron_frequency(WEEKLY_CRON) == "weekly"
    assert cron_frequency(MONTHLY_CRON) == "monthly"
    assert cron_frequency(QUARTERLY_CRON) == "quarterly"


def test_cron_frequency_refuses_unresolvable_expressions():
    # A wildcard minute means "every minute"; reporting it as a cadence would
    # hide real scheduling behaviour behind a convenient label.
    assert cron_frequency("* * * * *") is None
    assert cron_frequency("") is None
    assert cron_frequency(None) is None
    assert cron_frequency("15 19 * *") is None


def test_cadence_drift_flags_labelled_but_disabled():
    # An unstated stop is the dangerous case: nobody recorded why, so the
    # console keeps advertising a cadence that nothing honours.
    repository = FakeRepository(definitions=[
        _definition("unstated_stop", cadence="daily", mode="disabled", expression=None),
    ])
    result = cadence_drift(repository)
    assert result["available"] is True
    assert [item["kind"] for item in result["items"]] == ["labelled_but_disabled"]
    assert result["items"][0]["severity"] == "high"
    assert result["items"][0]["declared"] is False


def test_cadence_drift_flags_cron_frequency_mismatch():
    repository = FakeRepository(definitions=[
        _definition("cn_gdp", cadence="quarterly", mode="cron", expression=MONTHLY_CRON),
    ])
    result = cadence_drift(repository)
    assert [item["kind"] for item in result["items"]] == ["cron_frequency_mismatch"]
    assert result["items"][0]["observed_frequency"] == "monthly"


def test_cadence_drift_stays_quiet_for_consistent_definitions():
    repository = FakeRepository(definitions=[
        _definition("daily", cadence="daily", mode="cron", expression=DAILY_CRON),
        _definition("cn_gdp", cadence="quarterly", mode="cron", expression=QUARTERLY_CRON),
        _definition("local_factor_snapshot", cadence="dependency",
                    mode="dependency", expression=None),
    ])
    assert cadence_drift(repository)["items"] == []


def test_cadence_drift_ignores_retired_versions():
    repository = FakeRepository(definitions=[
        {**_definition("us_daily", cadence="daily", mode="disabled", expression=None),
         "lifecycle_status": "retired"},
    ])
    assert cadence_drift(repository)["items"] == []


def test_endpoint_drift_flags_governed_contract_without_registry():
    repository = FakeRepository(pairs=[
        {"source_id": "tushare", "endpoint_key": "daily", "acquisition_mode": None,
         "registry_cadence": None, "registered": False, "governed": True,
         "contract_cadence": None},
    ])
    result = endpoint_registry_drift(repository)
    assert [item["kind"] for item in result["items"]] == ["governed_without_registry"]


def test_endpoint_drift_does_not_flag_query_through_routes():
    # Query-through routes are served live and never persist partitions, so
    # staying out of the contract layer is the design, not a drift.
    repository = FakeRepository(pairs=[
        {"source_id": "sina", "endpoint_key": "quote", "acquisition_mode": "query_through",
         "registry_cadence": None, "registered": True, "governed": False,
         "contract_cadence": None},
    ])
    assert endpoint_registry_drift(repository)["items"] == []


def test_endpoint_drift_flags_ungoverned_scheduled_pull():
    repository = FakeRepository(pairs=[
        {"source_id": "tushare", "endpoint_key": "new_api",
         "acquisition_mode": "scheduled_pull", "registry_cadence": "daily",
         "registered": True, "governed": False, "contract_cadence": None},
    ])
    result = endpoint_registry_drift(repository)
    assert [item["kind"] for item in result["items"]] == ["scheduled_pull_not_governed"]


def test_derivation_rollout_drift_reports_unpublished_blueprints():
    repository = FakeRepository(definitions=[])
    result = derivation_rollout_drift(repository)
    assert result["available"] is True
    assert result["blueprint_total"] > 0
    assert result["published_total"] == 0
    assert {item["kind"] for item in result["items"]} == {"blueprint_not_published"}


def test_report_degrades_when_control_plane_is_absent():
    repository = FakeRepository(installed=False)
    report = consistency_report(repository)
    assert report["total"] == 0
    assert all(check["available"] is False for check in report["checks"].values())


def _client(repository) -> TestClient:
    application = create_app(
        database_factory=lambda: type("DB", (), {"close": lambda self: None})()
    )
    application.dependency_overrides[get_orchestration_v2_repository] = (
        lambda: repository
    )
    return TestClient(application)


def test_consistency_endpoint_reports_drift():
    repository = FakeRepository(definitions=[
        _definition("unstated_stop", cadence="daily", mode="disabled", expression=None),
    ])
    response = _client(repository).get("/api/v1/ops/orchestration-v2/consistency")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert payload["by_severity"]["high"] >= 1
    assert payload["checks"]["cadence"]["available"] is True
    assert "dispatch" in payload["checks"]


def test_consistency_sub_endpoints_are_read_only():
    repository = FakeRepository(definitions=[])
    client = _client(repository)
    for path in ("cadence", "endpoints", "derivations"):
        response = client.get(f"/api/v1/ops/orchestration-v2/consistency/{path}")
        assert response.status_code == 200, path


class LineageRepository(FakeRepository):
    """Repository whose lineage table is either absent or populated."""

    def __init__(self, rows=None):
        super().__init__()
        self._rows = rows

    def field_lineage_rows(self):
        return self._rows


def test_field_lineage_prefers_persisted_rows():
    rows = [{
        "table": "stock_daily",
        "source": "tushare",
        "interfaces": ["daily"],
        "fields": [{"name": "close", "type": "float",
                    "description": "收盘价", "from_interfaces": ["daily"]}],
    }]
    response = _client(LineageRepository(rows)).get(
        "/api/v1/data/dependencies/field-lineage"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "database"
    assert payload["items"][0]["table"] == "stock_daily"


def test_field_lineage_falls_back_when_unsynced():
    # An unsynced table must not read as "no lineage exists", so the compiler
    # stays the fallback and the payload says where the answer came from.
    response = _client(LineageRepository(None)).get(
        "/api/v1/data/dependencies/field-lineage"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "compiled"
    assert payload["total"] > 0


class DispatchRepository(FakeRepository):
    """Definitions plus the execution evidence the audit judges them against."""

    def __init__(self, definitions=None, activity=None):
        super().__init__(definitions=definitions)
        self._activity = activity or {}

    def execution_activity_by_task(self, *, since):
        return self._activity


def _activity(succeeded: int, last_finished=None):
    return {"total": succeeded, "succeeded": succeeded, "last_finished": last_finished}


def test_dispatch_drift_flags_disabled_task_that_still_runs():
    repository = DispatchRepository(
        definitions=[_definition("factor_value", cadence="daily", mode="disabled",
                                 expression=None)],
        activity={"factor_value": _activity(8)},
    )
    items = dispatch_drift(repository)["items"]
    assert [item["kind"] for item in items] == ["disabled_but_running"]
    assert items[0]["severity"] == "high"
    assert items[0]["declared"] is False


def test_dispatch_drift_accepts_declared_supplementary_trigger():
    # income is driven by a code-owned rolling refresh; its definition stays
    # disabled so the routine dispatcher skips it. That is a design, not drift.
    repository = DispatchRepository(
        definitions=[_definition("income", cadence="daily", mode="disabled",
                                 expression=None)],
        activity={"income": _activity(2)},
    )
    items = dispatch_drift(repository)["items"]
    assert items[0]["severity"] == "low"
    assert items[0]["declared"] is True
    assert "滚动刷新" in items[0]["reason"]


def test_dispatch_drift_does_not_flag_a_monthly_task_as_idle():
    # A monthly job silent for three weeks is healthy; judging it against a
    # fixed short window would flag every slow cadence.
    from datetime import date, timedelta

    from service.clock import business_today

    recent = business_today() - timedelta(days=20)
    repository = DispatchRepository(
        definitions=[_definition("cn_gdp", cadence="monthly", mode="cron",
                                 expression="30 20 1 * *")],
        activity={"cn_gdp": _activity(1, recent)},
    )
    assert dispatch_drift(repository)["items"] == []


def test_dispatch_drift_flags_a_daily_task_gone_silent():
    from datetime import timedelta

    from service.clock import business_today

    stale = business_today() - timedelta(days=30)
    repository = DispatchRepository(
        definitions=[_definition("daily", cadence="daily", mode="cron",
                                 expression=DAILY_CRON)],
        activity={"daily": _activity(1, stale)},
    )
    items = dispatch_drift(repository)["items"]
    assert [item["kind"] for item in items] == ["scheduled_but_idle"]
    assert items[0]["idle_days"] == 30


def test_deferred_dataset_is_reported_as_declared_not_broken():
    repository = FakeRepository(definitions=[
        _definition("us_daily", cadence="daily", mode="disabled", expression=None),
    ])
    item = cadence_drift(repository)["items"][0]
    assert item["severity"] == "low"
    assert item["declared"] is True
    assert "停采" in item["reason"]
