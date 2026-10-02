"""Compile and idempotently stage the V2 shadow-control baseline."""

from __future__ import annotations

from collections.abc import Mapping

from service.data_service.registry import DATASETS
from service.orchestration_v2.catalog import (
    EndpointRef,
    acquisition_task_blueprints,
    transformation_task_blueprints,
)
from service.orchestration_v2.audit_contracts import (
    observation_granularity,
    task_validation_contract,
)
from service.orchestration_v2.contracts import (
    AcquisitionEndpointContract,
    TaskDefinitionDocument,
    canonical_digest,
)
from service.orchestration_v2.service import OrchestrationV2Service
from service.source_connectors.registry import SOURCE_REGISTRY


V2_HANDLER_ALLOW_LIST = frozenset({
    "builtin.condition.v1",
    "builtin.dependency.v1",
    "builtin.scope.v1",
    "builtin.acquire.v1",
    "builtin.merge.v1",
    "builtin.transform.v1",
    "builtin.validate.v1",
    "builtin.publish.v1",
})


def endpoint_contracts() -> tuple[AcquisitionEndpointContract, ...]:
    references = {
        endpoint
        for task in acquisition_task_blueprints()
        for endpoint in task.endpoints
    }
    contracts: list[AcquisitionEndpointContract] = []
    for reference in sorted(references, key=lambda item: (item.source_id, item.endpoint_key)):
        endpoint = SOURCE_REGISTRY.get_endpoint(
            reference.source_id,
            reference.endpoint_key,
        )
        source = SOURCE_REGISTRY.get_source(reference.source_id)
        contracts.append(AcquisitionEndpointContract(
            source_id=reference.source_id,
            endpoint_key=reference.endpoint_key,
            acquisition_mode=endpoint.acquisition_mode.value,
            handler_key="builtin.acquire.v1",
            credential_ref=source.credential_ref,
            request_contract=dict(endpoint.request_contract),
            response_contract={
                "parser_name": endpoint.parser_name,
                "parser_version": endpoint.parser_version,
            },
            pagination_policy={
                "node_internal": True,
                "checkpointed": True,
            },
            rate_limit_policy={
                "source_quota_key": reference.source_id,
            },
            completeness_policy=dict(endpoint.completeness_policy),
        ))
    return tuple(contracts)


def task_documents(
    endpoint_ids: Mapping[EndpointRef, int],
) -> tuple[TaskDefinitionDocument, ...]:
    documents: list[TaskDefinitionDocument] = []
    producer_outputs: dict[str, tuple[str, ...]] = {}

    for task in acquisition_task_blueprints():
        ids = tuple(endpoint_ids[endpoint] for endpoint in task.endpoints)
        nodes = [
            _node("condition", "condition", "builtin.condition.v1"),
            _node("scope_plan", "scope_plan", "builtin.scope.v1"),
            _node(
                "acquire",
                "acquire",
                "builtin.acquire.v1",
                retry=(
                    {"max_attempts": 50}
                    if task.task_key == "share_float"
                    else None
                ),
            ),
        ]
        if len(task.endpoints) > 1 and task.task_key == "cn_lpr":
            nodes.append(_node("merge", "merge", "builtin.merge.v1"))
        nodes.extend((
            _node("validate", "validate", "builtin.validate.v1"),
            _node("publish", "publish", "builtin.publish.v1"),
        ))
        validation = task_validation_contract(task.output_datasets)
        document = TaskDefinitionDocument.model_validate({
            "task_key": task.task_key,
            "workflow_kind": "acquisition",
            "nodes": nodes,
            "output_datasets": task.output_datasets,
            "acquisition_endpoint_ids": ids,
            "schedule": _acquisition_schedule(task.cadence),
            "scope_contract": {
                "pagination_and_partitions": "within_acquire_node",
                "cadence": task.cadence,
                "execution_period_granularity": observation_granularity(validation),
                "one_execution_per_logical_period": True,
                "purposes": ["daily", "initialization", "backfill", "repair", "shadow"],
            },
            "validation_contract": validation,
            "resource": {
                "resource_class": task.resource_class or "default",
                "priority": 50,
                "source_quota_key": task.endpoints[0].source_id,
            },
        })
        documents.append(document)
        producer_outputs[task.task_key] = task.output_datasets

    for task in transformation_task_blueprints():
        dependencies = []
        for dependency_key in task.dependency_task_keys:
            dependency_outputs = producer_outputs.get(dependency_key, ())
            dependencies.append({
                "task_key": dependency_key,
                "datasets": [
                    name for name in dependency_outputs
                    if name in task.input_datasets
                ],
            })
        validation = task_validation_contract(task.output_datasets)
        document = TaskDefinitionDocument.model_validate({
            "task_key": task.task_key,
            "workflow_kind": "transformation",
            "nodes": [
                _node("condition", "condition", "builtin.condition.v1"),
                _node("dependencies", "dependency_check", "builtin.dependency.v1"),
                _node("scope_plan", "scope_plan", "builtin.scope.v1"),
                _node("transform", "transform", "builtin.transform.v1"),
                _node("validate", "validate", "builtin.validate.v1"),
                _node("publish", "publish", "builtin.publish.v1"),
            ],
            "input_datasets": task.input_datasets,
            "output_datasets": task.output_datasets,
            "dependencies": dependencies,
            "schedule": {"mode": "dependency"},
            "scope_contract": {
                "inherits_dependency_observation_scope": True,
                "cadence": "dependency",
                "execution_period_granularity": observation_granularity(validation),
                "one_execution_per_logical_period": True,
            },
            "validation_contract": validation,
            "resource": {
                "resource_class": "derived",
                "priority": task.priority,
            },
        })
        documents.append(document)
        producer_outputs[task.task_key] = task.output_datasets

    result = tuple(documents)
    if len(result) != 205:
        raise RuntimeError(f"compiled V2 task baseline drifted: {len(result)} != 205")
    return result


def stage_shadow_baseline(
    repository,
    *,
    actor: str,
    publish_ready: bool = False,
    app_revision: str = "shadow",
    image_digest: str = "shadow",
) -> dict:
    """Idempotently stage endpoint and task versions; never create executions."""
    if not repository.schema_exists():
        raise RuntimeError("orchestration_v2 schema is not installed")

    known_datasets = {item.name for item in DATASETS.list()}
    service = OrchestrationV2Service(
        repository,
        allowed_handler_keys=V2_HANDLER_ALLOW_LIST,
        known_datasets=known_datasets,
    )
    endpoint_rows: dict[EndpointRef, dict] = {}
    endpoint_created = 0
    endpoint_published = 0
    for contract in endpoint_contracts():
        digest = canonical_digest(contract)
        row = repository.find_endpoint_contract(
            contract.source_id,
            contract.endpoint_key,
            digest,
        )
        if row is None:
            row = service.create_endpoint_draft(contract, actor=actor)
            endpoint_created += 1
        if publish_ready and row["lifecycle_status"] == "draft":
            row = service.publish_endpoint(row["acquisition_endpoint_id"], actor=actor)
            endpoint_published += 1
        endpoint_rows[EndpointRef(contract.source_id, contract.endpoint_key)] = row

    endpoint_ids = {
        reference: row["acquisition_endpoint_id"]
        for reference, row in endpoint_rows.items()
    }
    documents = task_documents(endpoint_ids)
    definition_created = 0
    definition_published = 0
    planned_drafts = 0
    active_task_keys = repository.active_task_keys()
    for document in documents:
        digest = canonical_digest(document)
        row = repository.find_definition_contract(document.task_key, digest)
        if row is None:
            row = service.create_definition_draft(document, actor=actor)
            definition_created += 1

        outputs_available = set(document.output_datasets) <= known_datasets
        dependencies_active = all(
            dependency.task_key in active_task_keys
            for dependency in document.dependencies
        )
        can_publish = publish_ready and outputs_available and dependencies_active
        if can_publish and row["lifecycle_status"] == "draft":
            row = service.publish_definition(
                row["task_definition_id"],
                actor=actor,
                app_revision=app_revision,
                image_digest=image_digest,
            )
            definition_published += 1
            active_task_keys.add(document.task_key)
        elif row["lifecycle_status"] == "draft" and not outputs_available:
            planned_drafts += 1

    return {
        "mode": "published_ready" if publish_ready else "draft_only",
        "endpoint_contracts": len(endpoint_rows),
        "endpoint_versions_created": endpoint_created,
        "endpoint_versions_published": endpoint_published,
        "task_definitions": len(documents),
        "task_versions_created": definition_created,
        "task_versions_published": definition_published,
        "planned_output_drafts": planned_drafts,
        "executions_created": 0,
    }


def _node(
    key: str,
    kind: str,
    handler_key: str,
    *,
    retry: dict | None = None,
) -> dict:
    node = {"key": key, "kind": kind, "handler_key": handler_key}
    if retry is not None:
        node["retry"] = retry
    return node


def _acquisition_schedule(cadence: str) -> dict:
    expressions = {
        "daily": "15 19,23 * * *",
        "weekly": "30 20 * * 5",
        "monthly": "30 20 1 * *",
        "quarterly": "0 21 1 1,4,7,10 *",
    }
    expression = expressions.get(cadence)
    return (
        {"mode": "cron", "expression": expression}
        if expression
        else {"mode": "disabled"}
    )
