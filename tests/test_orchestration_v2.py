from pathlib import Path

import pytest
from pydantic import ValidationError

from service.config import PROJECT_ROOT
from service.orchestration_v2.contracts import (
    AcquisitionEndpointContract,
    DataStatus,
    DatasetStateUpdate,
    ExecutionStatus,
    TaskDefinitionDocument,
    assert_execution_transition,
    canonical_digest,
)
from service.orchestration_v2.service import (
    DefinitionPublishError,
    OrchestrationV2Service,
    _find_dependency_cycle,
)
from service.orchestration_v2.repository import OrchestrationV2Repository
from service.orchestration_v2.catalog import (
    EndpointRef,
    acquisition_task_blueprints,
    task_baseline_summary,
    transformation_task_blueprints,
)
from service.orchestration_v2.bootstrap import endpoint_contracts, task_documents
from service.orchestration_v2.runtime import merge_frozen_scope
from service.source_connectors.registry import SOURCE_REGISTRY
from service.data_service.registry import DATASETS


HANDLERS = {
    "builtin.condition.v1",
    "builtin.scope.v1",
    "tushare.pull.v1",
    "builtin.validate.v1",
    "builtin.publish.v1",
    "builtin.dependency.v1",
    "derived.compute.v1",
}


def acquisition_definition(**changes):
    value = {
        "schema_version": 1,
        "task_key": "daily_basic",
        "workflow_kind": "acquisition",
        "nodes": [
            {"key": "condition", "kind": "condition", "handler_key": "builtin.condition.v1"},
            {"key": "scope_plan", "kind": "scope_plan", "handler_key": "builtin.scope.v1"},
            {"key": "acquire", "kind": "acquire", "handler_key": "tushare.pull.v1"},
            {"key": "validate", "kind": "validate", "handler_key": "builtin.validate.v1"},
            {"key": "publish", "kind": "publish", "handler_key": "builtin.publish.v1"},
        ],
        "input_datasets": [],
        "output_datasets": ["stock_daily_basic"],
        "acquisition_endpoint_ids": [7],
        "dependencies": [],
        "schedule": {"mode": "cron", "expression": "0 18 * * 1-5"},
        "scope_contract": {"observation": "trade_date"},
        "validation_contract": {
            "verified_evidence_required": True,
            "outputs": ["stock_daily_basic"],
            "dataset_audits": [{
                "dataset_name": "stock_daily_basic",
                "audit_mode": "expected_partition",
                "period_granularity": "day",
                "date_column": "trade_date",
            }],
        },
        "resource": {"resource_class": "daily", "priority": 90},
    }
    value.update(changes)
    return value


def transformation_definition(**changes):
    value = {
        "schema_version": 1,
        "task_key": "adjusted_price_return",
        "workflow_kind": "transformation",
        "nodes": [
            {"key": "condition", "kind": "condition", "handler_key": "builtin.condition.v1"},
            {"key": "dependencies", "kind": "dependency_check", "handler_key": "builtin.dependency.v1"},
            {"key": "scope_plan", "kind": "scope_plan", "handler_key": "builtin.scope.v1"},
            {"key": "transform", "kind": "transform", "handler_key": "derived.compute.v1"},
            {"key": "validate", "kind": "validate", "handler_key": "builtin.validate.v1"},
            {"key": "publish", "kind": "publish", "handler_key": "builtin.publish.v1"},
        ],
        "input_datasets": ["stock_daily", "adj_factor"],
        "output_datasets": ["adjusted_price_return"],
        "acquisition_endpoint_ids": [],
        "dependencies": [
            {"task_key": "daily", "datasets": ["stock_daily"]},
            {"task_key": "adj_factor", "datasets": ["adj_factor"]},
        ],
        "schedule": {"mode": "dependency"},
        "scope_contract": {"observation": "trade_date"},
        "validation_contract": {
            "verified_evidence_required": True,
            "outputs": ["adjusted_price_return"],
            "dataset_audits": [{
                "dataset_name": "adjusted_price_return",
                "audit_mode": "expected_partition",
                "period_granularity": "day",
                "date_column": "trade_date",
                "require_transport_proof": True,
            }],
        },
        "resource": {"resource_class": "derived", "priority": 70},
    }
    value.update(changes)
    return value


def test_task_contract_accepts_only_the_fixed_acquisition_node_graph():
    document = TaskDefinitionDocument.model_validate(acquisition_definition())

    assert document.task_key == "daily_basic"
    assert [node.kind.value for node in document.nodes] == [
        "condition", "scope_plan", "acquire", "validate", "publish"
    ]

    invalid = acquisition_definition()
    invalid["nodes"][2], invalid["nodes"][3] = invalid["nodes"][3], invalid["nodes"][2]
    with pytest.raises(ValidationError, match="five-node"):
        TaskDefinitionDocument.model_validate(invalid)


def test_task_contract_requires_an_audit_for_every_output():
    invalid = acquisition_definition()
    invalid["validation_contract"]["dataset_audits"] = []
    with pytest.raises(ValidationError, match="must match exactly"):
        TaskDefinitionDocument.model_validate(invalid)

    invalid = acquisition_definition(output_datasets=["stock_daily_basic", "other"])
    with pytest.raises(ValidationError, match="every declared output exactly"):
        TaskDefinitionDocument.model_validate(invalid)


def test_transformation_contract_requires_dependencies_and_never_endpoints():
    document = TaskDefinitionDocument.model_validate(transformation_definition())
    assert len(document.dependencies) == 2

    with pytest.raises(ValidationError, match="cannot call acquisition endpoints"):
        TaskDefinitionDocument.model_validate(
            transformation_definition(acquisition_endpoint_ids=[7])
        )
    with pytest.raises(ValidationError, match="require input datasets and dependencies"):
        TaskDefinitionDocument.model_validate(
            transformation_definition(input_datasets=[], dependencies=[])
        )


def test_ready_dataset_state_requires_expected_verified_evidence():
    base = {
        "dataset_name": "stock_daily",
        "observation_key": "2026-09-24",
        "contract_version": "1",
        "expectation_status": "expected",
        "data_status": "complete",
        "validation_summary": {"verified": True, "actual": 5000},
    }
    state = DatasetStateUpdate.model_validate(base)
    assert state.ready is True

    with pytest.raises(ValidationError, match="verified validation evidence"):
        DatasetStateUpdate.model_validate({
            **base,
            "validation_summary": {"verified": False},
        })
    with pytest.raises(ValidationError, match="only expected data"):
        DatasetStateUpdate.model_validate({
            **base,
            "expectation_status": "unknown",
        })


def test_execution_state_machine_rejects_skipping_validation():
    assert_execution_transition(ExecutionStatus.RUNNING, ExecutionStatus.VALIDATING)
    assert_execution_transition(ExecutionStatus.PUBLISHING, ExecutionStatus.SUCCESS)

    with pytest.raises(ValueError, match="invalid execution transition"):
        assert_execution_transition(ExecutionStatus.RUNNING, ExecutionStatus.SUCCESS)
    with pytest.raises(ValueError, match="invalid execution transition"):
        assert_execution_transition(ExecutionStatus.SUCCESS, ExecutionStatus.QUEUED)


def test_expired_lease_recovery_rejects_unbounded_batches_before_connecting():
    repository = OrchestrationV2Repository(connection_factory=None)

    with pytest.raises(ValueError, match="between 1 and 10000"):
        repository.reclaim_expired_leases(limit=0)
    with pytest.raises(ValueError, match="between 1 and 10000"):
        repository.reclaim_expired_leases(limit=10_001)


def test_dependency_cycle_detection_reports_the_closed_path():
    assert _find_dependency_cycle({
        "a_task": ("b_task",),
        "b_task": ("c_task",),
        "c_task": ("a_task",),
    }) == ("a_task", "b_task", "c_task", "a_task")
    assert _find_dependency_cycle({"a_task": (), "b_task": ("a_task",)}) is None


class FakeRepository:
    def __init__(self, definition):
        self.endpoint = {
            "acquisition_endpoint_id": 7,
            "lifecycle_status": "active",
            "handler_key": "tushare.pull.v1",
        }
        self.definition = {
            "task_definition_id": 11,
            "task_key": definition.task_key,
            "workflow_kind": definition.workflow_kind.value,
            "lifecycle_status": "draft",
            "definition": definition.model_dump(mode="json"),
            "definition_digest": canonical_digest(definition),
        }
        self.published = None

    def get_definition(self, definition_id):
        return self.definition if definition_id == 11 else None

    def get_endpoint(self, endpoint_id):
        return self.endpoint if endpoint_id == 7 else None

    def active_task_keys(self):
        return set()

    def active_dependency_graph(self):
        return {}

    def publish_definition(self, definition_id, **metadata):
        self.published = (definition_id, metadata)
        return {**self.definition, "lifecycle_status": "active", **metadata}


def test_definition_publish_gate_requires_code_owned_handlers_and_datasets():
    document = TaskDefinitionDocument.model_validate(acquisition_definition())
    repository = FakeRepository(document)
    service = OrchestrationV2Service(
        repository,
        allowed_handler_keys=HANDLERS,
        known_datasets={"stock_daily_basic"},
    )

    result = service.publish_definition(
        11,
        actor="ci",
        app_revision="abc123",
        image_digest="sha256:image",
    )
    assert result["lifecycle_status"] == "active"
    assert repository.published[1]["app_revision"] == "abc123"

    blocked = OrchestrationV2Service(
        FakeRepository(document),
        allowed_handler_keys=HANDLERS - {"tushare.pull.v1"},
        known_datasets={"stock_daily_basic"},
    )
    with pytest.raises(DefinitionPublishError, match="allow-list"):
        blocked.publish_definition(
            11,
            actor="ci",
            app_revision="abc123",
            image_digest="sha256:image",
        )


def test_endpoint_contract_contains_no_executable_code_field():
    endpoint = AcquisitionEndpointContract.model_validate({
        "source_id": "tushare",
        "endpoint_key": "daily_basic",
        "acquisition_mode": "scheduled_pull",
        "handler_key": "tushare.pull.v1",
        "credential_ref": "env:TUSHARE_TOKEN",
        "completeness_policy": {"documented_row_limit": 6000},
    })
    assert endpoint.handler_key == "tushare.pull.v1"
    with pytest.raises(ValidationError, match="Extra inputs"):
        AcquisitionEndpointContract.model_validate({
            **endpoint.model_dump(mode="json"),
            "python_source": "exec('unsafe')",
        })


def test_v2_migration_builds_only_the_five_control_tables():
    migration = Path(
        PROJECT_ROOT / "sql/migrations/067_orchestration_v2_control_plane.sql"
    ).read_text(encoding="utf-8")
    expected = {
        "acquisition_endpoint",
        "task_definition",
        "task_execution",
        "task_execution_event",
        "dataset_state",
    }
    created = {
        line.split("orchestration_v2.", 1)[1].split(" ", 1)[0].strip()
        for line in migration.splitlines()
        if line.startswith("CREATE TABLE orchestration_v2.")
    }
    assert created == expected
    assert "FOR UPDATE SKIP LOCKED" not in migration
    assert "exec(" not in migration
    assert "task execution events are append-only" in migration


def test_canonical_digest_is_order_independent():
    assert canonical_digest({"scope": {"market": "SSE"}, "date": "2026-09-24"}) == canonical_digest({
        "date": "2026-09-24",
        "scope": {"market": "SSE"},
    })


def test_operator_retry_budget_is_bounded_before_database_access():
    repository = OrchestrationV2Repository()

    with pytest.raises(ValueError, match="between 1 and 100"):
        repository.retry_attention_executions(
            (), reason="invalid", minimum_max_attempts=101
        )


def test_operator_supersede_empty_selection_never_opens_database():
    repository = OrchestrationV2Repository()

    assert repository.supersede_attention_executions((), reason="nothing") == []


def test_resolved_attention_reconciler_rejects_unbounded_limit():
    repository = OrchestrationV2Repository()

    with pytest.raises(ValueError, match="between 1 and 5000"):
        repository.reconcile_resolved_attention_executions(limit=5001)


def test_operator_supersede_invalid_scope_empty_selection_never_opens_database():
    repository = OrchestrationV2Repository()

    assert repository.supersede_invalid_scope_executions((), reason="nothing") == []


def test_scope_refresh_preserves_initialization_lineage():
    refreshed = merge_frozen_scope(
        {
            "planner": "strict_audit_v2",
            "initialization_id": "42",
            "requests": [{"request_key": "stale"}],
        },
        {
            "observation_key": "2026-09-28",
            "requests": [{"request_key": "current"}],
        },
    )

    assert refreshed["initialization_id"] == "42"
    assert refreshed["planner"] == "strict_audit_v2"
    assert refreshed["requests"] == [{"request_key": "current"}]


def test_v2_machine_task_baseline_is_complete_and_non_overlapping():
    acquisitions = acquisition_task_blueprints()
    transformations = transformation_task_blueprints()

    assert task_baseline_summary() == {
        "acquisition": 191,
        "transformation": 14,
        "total": 205,
    }
    assert len({item.task_key for item in acquisitions}) == 191
    assert len({item.task_key for item in transformations}) == 14
    assert not (
        {item.task_key for item in acquisitions}
        & {item.task_key for item in transformations}
    )

    covered_tushare_endpoints = [
        endpoint.endpoint_key
        for task in acquisitions
        for endpoint in task.endpoints
        if endpoint.source_id == "tushare"
    ]
    expected_tushare_endpoints = {
        item.endpoint_key
        for item in SOURCE_REGISTRY.list_endpoints("tushare")
    }
    assert len(covered_tushare_endpoints) == len(expected_tushare_endpoints) == 201
    assert set(covered_tushare_endpoints) == expected_tushare_endpoints
    for task in acquisitions:
        for endpoint in task.endpoints:
            SOURCE_REGISTRY.get_endpoint(endpoint.source_id, endpoint.endpoint_key)
        for dataset_name in task.output_datasets:
            DATASETS.get(dataset_name)

    all_task_keys = {
        item.task_key for item in (*acquisitions, *transformations)
    }
    for task in transformations:
        assert set(task.dependency_task_keys) <= all_task_keys


def test_v2_baseline_compiles_to_strong_shadow_definitions_without_database():
    references = {
        endpoint
        for task in acquisition_task_blueprints()
        for endpoint in task.endpoints
    }
    endpoint_ids = {
        reference: index
        for index, reference in enumerate(
            sorted(references, key=lambda item: (item.source_id, item.endpoint_key)),
            start=1,
        )
    }
    documents = task_documents(endpoint_ids)

    assert len(endpoint_contracts()) == len(references) == 202
    assert len(documents) == 205
    by_key = {document.task_key: document for document in documents}
    assert [node.kind.value for node in by_key["daily"].nodes] == [
        "condition", "scope_plan", "acquire", "validate", "publish"
    ]
    assert [node.kind.value for node in by_key["shibor_lpr"].nodes] == [
        "condition", "scope_plan", "acquire", "merge", "validate", "publish"
    ]
    assert [node.kind.value for node in by_key["macro_regime"].nodes] == [
        "condition", "dependency_check", "scope_plan", "transform", "validate", "publish"
    ]
    share_float_acquire = next(
        node for node in by_key["share_float"].nodes if node.key == "acquire"
    )
    assert share_float_acquire.retry.max_attempts == 50
    assert EndpointRef("chinamoney", "lpr_history") in references

    known_datasets = {item.name for item in DATASETS.list()}
    planned_outputs = {
        output
        for document in documents
        for output in document.output_datasets
        if output not in known_datasets
    }
    assert len(planned_outputs) == 13
    assert "macro_regime" in planned_outputs
    assert "ggt_monthly" not in planned_outputs
    for document in documents:
        assert set(document.validation_contract.outputs) == set(
            document.output_datasets
        )
        assert {
            item.dataset_name
            for item in document.validation_contract.dataset_audits
        } == set(document.output_datasets)
        assert document.scope_contract["one_execution_per_logical_period"] is True
        assert document.scope_contract["execution_period_granularity"] in {
            "day", "week", "month", "quarter", "snapshot", "dependency"
        }

    assert by_key["daily"].scope_contract[
        "execution_period_granularity"
    ] == "day"
    assert by_key["daily"].scope_contract["cadence"] == "daily"
    assert by_key["index_monthly"].scope_contract[
        "execution_period_granularity"
    ] == "month"
    assert by_key["index_monthly"].scope_contract["cadence"] == "monthly"
    assert by_key["cn_gdp"].scope_contract[
        "execution_period_granularity"
    ] == "quarter"
    assert by_key["stock_basic"].scope_contract[
        "execution_period_granularity"
    ] == "snapshot"
