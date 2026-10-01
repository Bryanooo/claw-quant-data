"""Publication gates and state transitions for orchestration V2."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from service.orchestration_v2.contracts import (
    AcquisitionEndpointContract,
    DatasetStateUpdate,
    ExecutionRequest,
    ExecutionStatus,
    TaskDefinitionDocument,
    assert_execution_transition,
    canonical_digest,
)


class DefinitionPublishError(ValueError):
    """A draft failed a deterministic publication gate."""


class OrchestrationV2Service:
    """Safe facade around V2 persistence.

    Runtime handler and dataset names are supplied from code-owned registries.
    Database rows can select an allow-listed handler, but cannot load code.
    """

    def __init__(
        self,
        repository,
        *,
        allowed_handler_keys: Iterable[str],
        known_datasets: Iterable[str],
    ):
        self._repository = repository
        self._allowed_handler_keys = frozenset(allowed_handler_keys)
        self._known_datasets = frozenset(known_datasets)

    def create_endpoint_draft(
        self,
        contract: AcquisitionEndpointContract | dict[str, Any],
        *,
        actor: str,
    ) -> dict:
        parsed = (
            contract
            if isinstance(contract, AcquisitionEndpointContract)
            else AcquisitionEndpointContract.model_validate(contract)
        )
        self._assert_handler_allowed(parsed.handler_key)
        return self._repository.create_endpoint_draft(parsed, actor=actor)

    def publish_endpoint(self, endpoint_id: int, *, actor: str) -> dict:
        row = self._repository.get_endpoint(endpoint_id)
        if not row:
            raise DefinitionPublishError(f"endpoint draft not found: {endpoint_id}")
        if row["lifecycle_status"] != "draft":
            raise DefinitionPublishError("only endpoint drafts can be published")
        contract = AcquisitionEndpointContract.model_validate({
            "source_id": row["source_id"],
            "endpoint_key": row["endpoint_key"],
            "acquisition_mode": row["acquisition_mode"],
            "handler_key": row["handler_key"],
            "credential_ref": row["credential_ref"],
            "request_contract": row["request_contract"],
            "response_contract": row["response_contract"],
            "pagination_policy": row["pagination_policy"],
            "rate_limit_policy": row["rate_limit_policy"],
            "completeness_policy": row["completeness_policy"],
        })
        if canonical_digest(contract) != row["contract_digest"].strip():
            raise DefinitionPublishError("endpoint digest does not match stored contract")
        self._assert_handler_allowed(contract.handler_key)
        return self._repository.publish_endpoint(endpoint_id, actor=actor)

    def create_definition_draft(
        self,
        document: TaskDefinitionDocument | dict[str, Any],
        *,
        actor: str,
    ) -> dict:
        parsed = (
            document
            if isinstance(document, TaskDefinitionDocument)
            else TaskDefinitionDocument.model_validate(document)
        )
        return self._repository.create_definition_draft(parsed, actor=actor)

    def publish_definition(
        self,
        definition_id: int,
        *,
        actor: str,
        app_revision: str,
        image_digest: str,
    ) -> dict:
        row = self._repository.get_definition(definition_id)
        if not row:
            raise DefinitionPublishError(f"task definition draft not found: {definition_id}")
        if row["lifecycle_status"] != "draft":
            raise DefinitionPublishError("only task definition drafts can be published")
        document = TaskDefinitionDocument.model_validate(row["definition"])
        if document.task_key != row["task_key"]:
            raise DefinitionPublishError("task key differs between row and definition")
        if document.workflow_kind.value != row["workflow_kind"]:
            raise DefinitionPublishError("workflow kind differs between row and definition")
        if canonical_digest(document) != row["definition_digest"].strip():
            raise DefinitionPublishError("definition digest does not match stored JSON")
        if not app_revision.strip() or not image_digest.strip():
            raise DefinitionPublishError(
                "publishing requires an application revision and image digest"
            )

        for node in document.nodes:
            self._assert_handler_allowed(node.handler_key)
        dependency_datasets = {
            dataset
            for dependency in document.dependencies
            for dataset in dependency.datasets
        }
        unknown_datasets = (
            set(document.input_datasets)
            | set(document.output_datasets)
            | dependency_datasets
        ) - self._known_datasets
        if unknown_datasets:
            raise DefinitionPublishError(
                "unknown datasets: " + ", ".join(sorted(unknown_datasets))
            )
        undeclared_inputs = dependency_datasets - set(document.input_datasets)
        if undeclared_inputs:
            raise DefinitionPublishError(
                "dependency datasets are not declared as task inputs: "
                + ", ".join(sorted(undeclared_inputs))
            )

        for endpoint_id in document.acquisition_endpoint_ids:
            endpoint = self._repository.get_endpoint(endpoint_id)
            if not endpoint or endpoint["lifecycle_status"] != "active":
                raise DefinitionPublishError(
                    f"acquisition endpoint is not active: {endpoint_id}"
                )
            self._assert_handler_allowed(endpoint["handler_key"])

        dependency_keys = {item.task_key for item in document.dependencies}
        missing_dependencies = dependency_keys - self._repository.active_task_keys()
        if missing_dependencies:
            raise DefinitionPublishError(
                "dependencies are not active: "
                + ", ".join(sorted(missing_dependencies))
            )
        graph = self._repository.active_dependency_graph()
        graph[document.task_key] = tuple(sorted(dependency_keys))
        cycle = _find_dependency_cycle(graph)
        if cycle:
            raise DefinitionPublishError(
                "task dependency cycle: " + " -> ".join(cycle)
            )
        return self._repository.publish_definition(
            definition_id,
            actor=actor,
            app_revision=app_revision,
            image_digest=image_digest,
        )

    def create_execution(
        self,
        request: ExecutionRequest | dict[str, Any],
    ) -> tuple[dict, bool]:
        parsed = (
            request
            if isinstance(request, ExecutionRequest)
            else ExecutionRequest.model_validate(request)
        )
        definition = self._repository.get_active_definition(parsed.task_key)
        if not definition:
            raise LookupError(
                f"active task definition not found: {parsed.task_key}"
            )
        document = TaskDefinitionDocument.model_validate(definition["definition"])
        if parsed.purpose.value in {"initialization", "backfill", "repair"}:
            from service.orchestration_v2.repair_planning import (
                validate_single_period_scope,
            )

            for contract in document.validation_contract.dataset_audits:
                validate_single_period_scope(
                    contract=contract,
                    observation_start=parsed.observation_start,
                    observation_end=parsed.observation_end,
                    observation_key=parsed.observation_key,
                )
        return self._repository.create_execution(parsed)

    def transition_execution(
        self,
        execution_id: int,
        target_status: ExecutionStatus | str,
        **changes,
    ) -> dict:
        execution = self._repository.get_execution(execution_id)
        if not execution:
            raise LookupError(f"task execution not found: {execution_id}")
        target = ExecutionStatus(target_status)
        current = ExecutionStatus(execution["status"])
        assert_execution_transition(current, target)
        return self._repository.transition_execution(
            execution_id,
            expected_status=current,
            target_status=target,
            **changes,
        )

    def publish_dataset_state(
        self,
        execution_id: int,
        update: DatasetStateUpdate | dict[str, Any],
        *,
        validation_payload: dict[str, Any],
        evidence_references: list[dict[str, Any]] | None = None,
    ) -> dict:
        parsed = (
            update
            if isinstance(update, DatasetStateUpdate)
            else DatasetStateUpdate.model_validate(update)
        )
        execution = self._repository.get_execution(execution_id)
        if not execution:
            raise LookupError(f"task execution not found: {execution_id}")
        definition = self._repository.get_definition(execution["task_definition_id"])
        if not definition:
            raise RuntimeError("execution references a missing task definition")
        document = TaskDefinitionDocument.model_validate(definition["definition"])
        if parsed.dataset_name not in document.output_datasets:
            raise DefinitionPublishError(
                f"task {document.task_key} does not publish {parsed.dataset_name}"
            )
        if validation_payload.get("verified") is not True:
            raise DefinitionPublishError(
                "dataset publication requires explicit verified validation payload"
            )
        if canonical_digest(parsed.validation_summary) != canonical_digest(
            validation_payload
        ):
            raise DefinitionPublishError(
                "dataset validation summary differs from the published evidence"
            )
        return self._repository.publish_dataset_state(
            execution_id,
            parsed,
            validation_payload=validation_payload,
            evidence_references=evidence_references,
        )

    def _assert_handler_allowed(self, handler_key: str) -> None:
        if handler_key not in self._allowed_handler_keys:
            raise DefinitionPublishError(
                f"handler is not present in the code allow-list: {handler_key}"
            )


def _find_dependency_cycle(
    graph: dict[str, tuple[str, ...]],
) -> tuple[str, ...] | None:
    """Return one deterministic dependency cycle, including its closing key."""
    visiting: set[str] = set()
    visited: set[str] = set()
    path: list[str] = []

    def visit(task_key: str) -> tuple[str, ...] | None:
        if task_key in visiting:
            start = path.index(task_key)
            return tuple(path[start:] + [task_key])
        if task_key in visited:
            return None
        visiting.add(task_key)
        path.append(task_key)
        for dependency in sorted(graph.get(task_key, ())):
            cycle = visit(dependency)
            if cycle:
                return cycle
        path.pop()
        visiting.remove(task_key)
        visited.add(task_key)
        return None

    for key in sorted(graph):
        cycle = visit(key)
        if cycle:
            return cycle
    return None
