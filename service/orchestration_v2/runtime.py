"""Executable V2 acquisition workflow.

One task execution owns one logical observation period.  Provider pagination,
symbols and market partitions are exhausted inside the acquire node and never
become scheduler-visible child executions.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from threading import Event, Thread
from typing import Any

from service.acquisition_runtime.models import TaskExecutionResult
from service.acquisition_runtime.models import BatchChildSpec
from service.acquisition_runtime.context import durable_job_execution
from service.acquisition_runtime.fanout import (
    FANOUT_DEFINITIONS,
    list_fanout_values,
)
from service.clock import business_now
from service.acquisition_runtime.registry import TASKS
from service.acquisition_runtime.reliability import classify_failure
from service.db import query
from service.history_recovery import (
    MARKET_WIDE_FANOUT_OVERRIDES,
    build_reverse_recovery_plan,
)
from service.tushare_catalog import TushareInterfaceCatalog
from service.tushare_policy import TusharePolicyRegistry
from service.tushare_scheduling import parameters_for_policy
from service.orchestration_v2.audit_runtime import TaskAuditRuntime
from service.orchestration_v2.contracts import (
    ExecutionStatus,
    TaskDefinitionDocument,
    WorkflowKind,
)


def merge_frozen_scope(
    existing: dict[str, Any] | None,
    planned: dict[str, Any],
) -> dict[str, Any]:
    """Refresh node-owned scope fields without losing campaign lineage."""

    return {**(existing or {}), **planned}


class V2RuntimeError(RuntimeError):
    """A V2 execution cannot safely complete its declared workflow."""


class V2UnsupportedScopeError(V2RuntimeError):
    """The current code cannot construct an exact bounded acquisition scope."""

    retryable = False


_WHOLE_MARKET_FINANCE_APIS = frozenset({
    "balancesheet",
    "cashflow",
    "disclosure_date",
    "express",
    "fina_audit",
    "fina_indicator",
    "fina_mainbz",
    "forecast",
    "income",
})


def bounded_history_target_date(
    parameter_strategy: str,
    period_end,
    trade_dates,
):
    """Map a logical period to the provider's materialized partition date."""
    if parameter_strategy == "trade_date" and trade_dates:
        return trade_dates[-1]
    return period_end


@contextmanager
def execution_lease_heartbeat(
    repository,
    execution_id: int,
    worker_id: str,
    lease_token: str,
    lease_seconds: int,
):
    stopping = Event()
    interval = max(min(lease_seconds / 3, 30), 1)
    lost: list[Exception] = []

    def renew() -> None:
        while not stopping.wait(interval):
            try:
                repository.renew_lease(
                    execution_id,
                    worker_id=worker_id,
                    lease_token=lease_token,
                    lease_seconds=lease_seconds,
                )
            except Exception as exc:  # pragma: no cover - timing dependent
                lost.append(exc)
                return

    thread = Thread(
        target=renew,
        name=f"v2-execution-lease-{execution_id}",
        daemon=True,
    )
    thread.start()
    try:
        yield
        if lost:
            raise RuntimeError("V2 execution lease was lost") from lost[0]
    finally:
        stopping.set()
        thread.join(timeout=min(interval, 1))


class OrchestrationV2Runtime:
    """Run the fixed acquisition graph for one already-claimed execution."""

    def __init__(self, repository, *, audit_runtime: TaskAuditRuntime | None = None):
        self._repository = repository
        self._audits = audit_runtime or TaskAuditRuntime()

    def run_claimed(
        self,
        execution: dict,
        *,
        worker_id: str,
        lease_seconds: int = 120,
    ) -> dict:
        execution_id = int(execution["task_execution_id"])
        lease_token = str(execution["lease_token"])
        definition = self._repository.get_definition(
            int(execution["task_definition_id"])
        )
        if not definition:
            raise V2RuntimeError("execution references a missing task definition")
        document = TaskDefinitionDocument.model_validate(definition["definition"])
        if document.workflow_kind != WorkflowKind.ACQUISITION:
            raise V2UnsupportedScopeError(
                "the first production V2 runtime only executes acquisition tasks"
            )

        node_status = dict(execution.get("node_status") or {})
        try:
            with execution_lease_heartbeat(
                self._repository,
                execution_id,
                worker_id,
                lease_token,
                lease_seconds,
            ):
                self._complete_node(
                    execution,
                    node_status,
                    "condition",
                    worker_id,
                    lease_token,
                    {"purpose": execution["purpose"], "eligible": True},
                )

                # Routine runs are the source of today's transport evidence.
                # A calendar grace window can legitimately make a preflight
                # audit say "empty", but it must never turn that absence of an
                # expectation into permission to skip the upstream request.
                # Historical repair may still short-circuit data already
                # proven ready; daily runs always execute the acquire node.
                # Daily executions are transport probes for the declared
                # observation date.  Some datasets (for example LPR and
                # repurchase events) have a monthly completeness contract, so
                # that one-day scope quite correctly has no mature aggregate
                # partition before the upstream request is made.  Running the
                # aggregate audit here used to fail the condition node and
                # prevented the request that would provide the evidence.
                # Historical work may still short-circuit when its full
                # logical period is already certified.
                if execution["purpose"] == "daily":
                    ready_before_acquire = False
                else:
                    preflight = self._audit_outputs(document, execution)
                    ready_before_acquire = all(
                        update.ready for _, update, _ in preflight
                    )
                acquisition_evidence = self._verified_acquisition_evidence(
                    execution_id
                )
                existing_scope = dict(execution.get("frozen_scope") or {})
                specs = ()
                if ready_before_acquire:
                    frozen_scope = merge_frozen_scope(existing_scope, {
                        "observation_key": execution["observation_key"],
                        "already_ready": True,
                        "requests": [],
                    })
                else:
                    planned_specs = self._plan_acquisition(document, execution)
                    specs = self._remaining_specs(
                        planned_specs,
                        acquisition_evidence,
                    )
                    completed_keys = {
                        item.get("request_key")
                        for item in acquisition_evidence
                        if item.get("request_key")
                    }
                    frozen_scope = merge_frozen_scope(existing_scope, {
                        "observation_key": execution["observation_key"],
                        "requests": [
                            {
                                "task_name": spec.task_name,
                                "api_name": spec.api_name,
                                "parameters": spec.parameters,
                                "request_key": spec.idempotency_key,
                                "completed": spec.idempotency_key in completed_keys,
                                "expected_for": (
                                    spec.expected_for.isoformat()
                                    if spec.expected_for else None
                                ),
                            }
                            for spec in planned_specs
                        ],
                        "resumed_verified_requests": len(acquisition_evidence),
                    })
                self._complete_node(
                    execution,
                    node_status,
                    "scope_plan",
                    worker_id,
                    lease_token,
                    frozen_scope,
                    frozen_scope=frozen_scope,
                )

                if specs:
                    node_status["acquire"] = "running"
                    self._repository.checkpoint_execution(
                        execution_id,
                        worker_id=worker_id,
                        lease_token=lease_token,
                        current_node_key="acquire",
                        node_status=node_status,
                    )
                    self._repository.append_event(
                        execution_id,
                        event_type="node.acquire.started",
                        node_key="acquire",
                        attempt_number=int(execution["attempt_count"]),
                        payload={
                            "request_count": len(specs),
                            "completed_requests": len(acquisition_evidence),
                        },
                    )

                for spec in specs:
                    # V2 owns the durable retryable execution. Mark the
                    # collector call accordingly so long
                    # interface windows release the worker instead of sleeping
                    # in-process and dragging the token-wide reservation into
                    # the future.
                    with durable_job_execution():
                        result = TASKS.run(spec.task_name, spec.parameters)
                    outcome = self._normalize_outcome(result)
                    if outcome.completion_status not in {"complete", "empty"}:
                        raise V2RuntimeError(
                            f"{spec.api_name or spec.task_name} returned "
                            f"non-terminal completion status "
                            f"{outcome.completion_status}"
                        )
                    evidence = {
                        "api_name": spec.api_name,
                        "task_name": spec.task_name,
                        "request_key": spec.idempotency_key,
                        "expected_for": (
                            spec.expected_for.isoformat()
                            if spec.expected_for else None
                        ),
                        "rows_fetched": outcome.rows_fetched,
                        "rows_inserted": outcome.rows_inserted,
                        "completion_status": outcome.completion_status,
                        "completion_evidence": outcome.completion_evidence,
                    }
                    acquisition_evidence.append(evidence)
                    self._repository.append_event(
                        execution_id,
                        event_type="node.acquire.request_completed",
                        node_key="acquire",
                        attempt_number=int(execution["attempt_count"]),
                        payload=evidence,
                    )
                self._complete_node(
                    execution,
                    node_status,
                    "acquire",
                    worker_id,
                    lease_token,
                    {
                        "skipped": ready_before_acquire,
                        "request_count": len(specs),
                        "rows_fetched": sum(
                            int(item.get("rows_fetched") or 0)
                            for item in acquisition_evidence
                        ),
                        "rows_inserted": sum(
                            int(item.get("rows_inserted") or 0)
                            for item in acquisition_evidence
                        ),
                    },
                    collected=bool(specs),
                )

                execution = self._repository.transition_execution(
                    execution_id,
                    expected_status=ExecutionStatus.RUNNING,
                    target_status=ExecutionStatus.VALIDATING,
                    worker_id=worker_id,
                    lease_token=lease_token,
                    current_node_key="validate",
                    node_status=node_status,
                )
                audit_results = self._audit_outputs(
                    document,
                    execution,
                    transport_evidence=acquisition_evidence,
                )
                node_status["validate"] = "success"
                self._repository.append_event(
                    execution_id,
                    event_type="node.validate.completed",
                    node_key="validate",
                    attempt_number=int(execution["attempt_count"]),
                    payload={
                        "outputs": {
                            update.dataset_name: result.status
                            for result, update, _ in audit_results
                        }
                    },
                )
                execution = self._repository.transition_execution(
                    execution_id,
                    expected_status=ExecutionStatus.VALIDATING,
                    target_status=ExecutionStatus.PUBLISHING,
                    worker_id=worker_id,
                    lease_token=lease_token,
                    current_node_key="publish",
                    node_status=node_status,
                )
                all_ready = True
                for _result, update, validation in audit_results:
                    self._repository.publish_dataset_state(
                        execution_id,
                        update,
                        validation_payload=validation,
                        evidence_references=[
                            {
                                "event": "node.acquire.request_completed",
                                "task_execution_id": execution_id,
                            }
                        ],
                    )
                    all_ready = all_ready and update.ready
                node_status["publish"] = "success"
                target = (
                    ExecutionStatus.SUCCESS
                    if all_ready else ExecutionStatus.ATTENTION
                )
                return self._repository.transition_execution(
                    execution_id,
                    expected_status=ExecutionStatus.PUBLISHING,
                    target_status=target,
                    worker_id=worker_id,
                    lease_token=lease_token,
                    current_node_key="publish",
                    node_status=node_status,
                    error_category=None if all_ready else "data_incomplete",
                    error_message=(
                        None
                        if all_ready
                        else "independent validation did not certify every output"
                    ),
                    error_detail={
                        "outputs": {
                            update.dataset_name: update.data_status.value
                            for _result, update, _validation in audit_results
                        }
                    },
                )
        except Exception as exc:
            if getattr(exc, "defer_without_failure", False):
                retry_after_seconds = max(
                    int(getattr(exc, "retry_after_seconds", 1)), 1
                )
                return self._repository.defer_execution(
                    execution_id,
                    delay=timedelta(seconds=retry_after_seconds),
                    worker_id=worker_id,
                    lease_token=lease_token,
                    node_status=node_status,
                    reason=f"{type(exc).__name__}: {exc}",
                )
            return self._fail_or_retry(
                execution_id,
                worker_id=worker_id,
                lease_token=lease_token,
                node_status=node_status,
                exc=exc,
            )

    def _verified_acquisition_evidence(self, execution_id: int) -> list[dict[str, Any]]:
        """Reuse verified request partitions when any later attempt resumes.

        Static fan-outs contain several provider partitions inside one acquire
        node. Persisting a stable request key on each completed partition
        prevents a network failure in the final exchange/type from replaying
        every earlier request. Legacy one-request evidence has no key; it is
        still reusable when the reconstructed plan contains exactly one item.
        """

        durable_reader = getattr(
            self._repository,
            "list_verified_acquisition_evidence",
            None,
        )
        if callable(durable_reader):
            return [dict(item) for item in durable_reader(execution_id)]
        # Test doubles and older adapters retain the bounded event-reader
        # fallback. Production repositories always use the unbounded,
        # request-key-deduplicated query above.
        evidence = [
            dict(event.get("payload") or {})
            for event in self._repository.list_execution_events(
                execution_id,
                limit=1000,
            )
            if event.get("event_type") == "node.acquire.request_completed"
        ]
        return [
            item
            for item in evidence
            if item.get("completion_status") in {"complete", "empty"}
            and (item.get("completion_evidence") or {}).get("verified") is True
        ]

    @staticmethod
    def _remaining_specs(
        planned_specs: tuple[BatchChildSpec, ...],
        acquisition_evidence: list[dict[str, Any]],
    ) -> tuple[BatchChildSpec, ...]:
        completed_keys = {
            str(item["request_key"])
            for item in acquisition_evidence
            if item.get("request_key")
        }
        if completed_keys:
            return tuple(
                spec
                for spec in planned_specs
                if spec.idempotency_key not in completed_keys
            )
        if len(planned_specs) == 1 and acquisition_evidence:
            return ()
        return planned_specs

    def _complete_node(
        self,
        execution: dict,
        node_status: dict[str, str],
        node_key: str,
        worker_id: str,
        lease_token: str,
        payload: dict[str, Any],
        *,
        frozen_scope: dict[str, Any] | None = None,
        collected: bool = False,
    ) -> None:
        node_status[node_key] = "success"
        self._repository.checkpoint_execution(
            int(execution["task_execution_id"]),
            worker_id=worker_id,
            lease_token=lease_token,
            current_node_key=node_key,
            node_status=node_status,
            frozen_scope=frozen_scope,
            collected=collected,
        )
        self._repository.append_event(
            int(execution["task_execution_id"]),
            event_type=f"node.{node_key}.completed",
            node_key=node_key,
            attempt_number=int(execution["attempt_count"]),
            payload=payload,
        )

    def _audit_outputs(
        self,
        document: TaskDefinitionDocument,
        execution: dict,
        *,
        transport_evidence: list[dict[str, Any]] | None = None,
    ) -> list[tuple[Any, Any, dict[str, Any]]]:
        start = execution.get("observation_start")
        end = execution.get("observation_end")
        if start is None or end is None:
            raise V2UnsupportedScopeError(
                "temporal acquisition requires observation_start and observation_end"
            )
        values = []
        for dataset_name in document.output_datasets:
            result, update = self._audits.audit_output(
                document,
                dataset_name=dataset_name,
                observation_key=execution["observation_key"],
                start_date=start,
                end_date=end,
                as_of=business_now(),
                persist=True,
                transport_evidence=transport_evidence,
            )
            validation = dict(update.validation_summary)
            values.append((result, update, validation))
        return values

    def _plan_acquisition(
        self,
        document: TaskDefinitionDocument,
        execution: dict,
    ):
        endpoints = [
            self._repository.get_endpoint(endpoint_id)
            for endpoint_id in document.acquisition_endpoint_ids
        ]
        active = [item for item in endpoints if item and item["lifecycle_status"] == "active"]
        if not active:
            raise V2UnsupportedScopeError("task has no active acquisition endpoint")
        # Prefer the endpoint whose name is the task identity. For equivalent
        # normal/VIP endpoints, prefer the non-VIP route and retain provider
        # fallback work for the later multi-source runtime phase.
        selected = sorted(
            active,
            key=lambda item: (
                item["endpoint_key"] != document.task_key,
                item["endpoint_key"].endswith("_vip"),
                item["source_id"] != "tushare",
                item["acquisition_endpoint_id"],
            ),
        )[0]
        if selected["source_id"] != "tushare":
            raise V2UnsupportedScopeError(
                f"V2 bounded history runtime is not implemented for "
                f"{selected['source_id']}/{selected['endpoint_key']}"
            )
        start = execution["observation_start"]
        end = execution["observation_end"]
        api_name = selected["endpoint_key"]
        if api_name in _WHOLE_MARKET_FINANCE_APIS:
            return (
                self._period_finance_spec(
                    api_name=api_name,
                    period=end,
                    purpose=execution["purpose"],
                ),
            )
        fanout = FANOUT_DEFINITIONS.get(api_name)
        if (
            api_name in MARKET_WIDE_FANOUT_OVERRIDES
            or (api_name == "dividend" and execution["purpose"] == "daily")
        ):
            # Live pagination probes prove these endpoints can exhaust one
            # market-wide logical period.  Keeping their legacy symbol fanout
            # here turned one V2 node into tens of thousands of calls (most
            # visibly fund_nav) even though the recovery planner already used
            # the safer bounded market-wide request. Dividend keeps its
            # all-history stock fanout for backfills, while a daily ann_date
            # is itself a small, exact and collector-guarded partition.
            fanout = None
        if fanout is not None and fanout.source == "static":
            # Exchange/type/frequency partitions are provider transport
            # details inside the acquire node. They must not become separate
            # workflow executions: one logical observation day still has one
            # execution, one validation decision and one dataset state.
            policy = TusharePolicyRegistry().get(api_name)
            return tuple(
                self._static_fanout_spec(
                    api_name=api_name,
                    parameter_name=fanout.parameter_name,
                    parameter_value=value,
                    scope_kind=fanout.scope,
                    observation_date=end,
                    purpose=execution["purpose"],
                    policy=policy,
                )
                for value in fanout.static_values
            )
        if fanout is not None:
            return self._dynamic_fanout_specs(
                api_name=api_name,
                fanout=fanout,
                observation_start=start,
                observation_end=end,
                purpose=execution["purpose"],
            )
        # Routine collection uses the endpoint's current operational policy.
        # History recipes deliberately favor start/end windows and fan-outs;
        # several live APIs instead require trade_date for today's partition.
        # The distinction belongs inside this node, not in separate tasks.
        if execution["purpose"] == "daily":
            contract = TushareInterfaceCatalog().require_collectable(api_name)
            policy = TusharePolicyRegistry().get(api_name)
            anchor_value = (execution.get("frozen_scope") or {}).get(
                "policy_anchor_date"
            )
            policy_anchor = (
                datetime.fromisoformat(anchor_value).date()
                if anchor_value else end
            )
            parameters = parameters_for_policy(
                policy,
                {item["name"] for item in contract.input_parameters},
                today=policy_anchor,
                trade_date=end.strftime("%Y%m%d"),
            )
            payload = {
                "api_name": api_name,
                "parameters": parameters,
                "complete": True,
                "page_size": policy.page_size,
                "max_pages": policy.max_pages,
                "resume": True,
            }
            return (BatchChildSpec(
                task_name="tushare_interface",
                parameters=payload,
                idempotency_key=f"v2:daily:{api_name}:{end.isoformat()}",
                api_name=api_name,
                cadence="daily",
                period_key=end.isoformat(),
                expected_for=end,
                handler=TASKS.handler_metadata("tushare_interface", payload),
                priority=80,
                resource_class="generic",
            ),)
        trade_dates = [
            row["cal_date"]
            for row in query(
                "SELECT cal_date FROM trade_cal WHERE exchange='SSE' "
                "AND is_open=1 AND cal_date BETWEEN %s AND %s ORDER BY cal_date",
                (start, end),
            )
        ]
        if not trade_dates:
            trade_dates = [start]
        plan = build_reverse_recovery_plan(
            dataset_apis={
                dataset_name: selected["endpoint_key"]
                for dataset_name in document.output_datasets
            },
            targets_by_dataset={
                dataset_name: [
                    bounded_history_target_date(
                        TusharePolicyRegistry().get(
                            selected["endpoint_key"]
                        ).parameter_strategy,
                        end,
                        trade_dates,
                    )
                ]
                for dataset_name in document.output_datasets
            },
            history_start=start,
            history_end=end,
            trade_dates=trade_dates,
        )
        if plan.unsupported:
            raise V2UnsupportedScopeError(str(plan.unsupported))
        if not plan.specs:
            raise V2UnsupportedScopeError(
                f"no bounded request for {document.task_key}/"
                f"{execution['observation_key']}"
            )
        return plan.specs

    @staticmethod
    def _period_finance_spec(
        *, api_name: str, period, purpose: str
    ) -> BatchChildSpec:
        compact_period = period.strftime("%Y%m%d")
        payload = {
            "api_name": api_name,
            # Specialized financial collectors expose one stable internal
            # ``period`` contract and translate it to upstream aliases such as
            # disclosure_date.end_date themselves.
            "parameters": {"period": compact_period},
            "complete": True,
            "resume": True,
        }
        return BatchChildSpec(
            task_name="tushare_interface",
            parameters=payload,
            idempotency_key=f"v2:{purpose}:{api_name}:{compact_period}",
            api_name=api_name,
            cadence="quarterly",
            period_key=compact_period,
            expected_for=period,
            handler=TASKS.handler_metadata("tushare_interface", payload),
            priority=80 if purpose == "daily" else 30,
            resource_class="finance" if purpose == "daily" else "backfill",
        )

    @staticmethod
    def _dynamic_fanout_specs(
        *,
        api_name: str,
        fanout,
        observation_start,
        observation_end,
        purpose: str,
    ) -> tuple[BatchChildSpec, ...]:
        values = list_fanout_values(fanout.source, as_of=observation_end)
        if not values:
            raise V2UnsupportedScopeError(
                f"fan-out dependency {fanout.source} has no available values"
            )
        compact_start = observation_start.strftime("%Y%m%d")
        compact_end = observation_end.strftime("%Y%m%d")
        if fanout.scope == "none":
            scope = {}
        elif fanout.scope == "trade_date":
            scope = {"trade_date": compact_end}
        elif fanout.scope == "ann_date":
            scope = {"ann_date": compact_end}
        elif fanout.scope == "period":
            scope = {"period": compact_end}
        else:
            scope = {"start_date": compact_start, "end_date": compact_end}
        policy = TusharePolicyRegistry().get(api_name)
        specs: list[BatchChildSpec] = []
        for offset in range(0, len(values), fanout.batch_size):
            chunk = values[offset : offset + fanout.batch_size]
            joined = ",".join(chunk)
            parameters = {**scope, fanout.parameter_name: joined}
            payload = {
                "api_name": api_name,
                "parameters": parameters,
                "complete": True,
                "page_size": policy.page_size,
                "max_pages": max(policy.max_pages, 1000),
                "resume": True,
            }
            specs.append(BatchChildSpec(
                task_name="tushare_interface",
                parameters=payload,
                idempotency_key=(
                    f"v2:{purpose}:{api_name}:{observation_start.isoformat()}:"
                    f"{observation_end.isoformat()}:{fanout.parameter_name}:{joined}"
                ),
                api_name=api_name,
                cadence="daily" if purpose == "daily" else "backfill",
                period_key=observation_end.isoformat(),
                expected_for=observation_end,
                handler=TASKS.handler_metadata("tushare_interface", payload),
                priority=80 if purpose == "daily" else 30,
                resource_class="generic" if purpose == "daily" else "backfill",
            ))
        return tuple(specs)

    @staticmethod
    def _static_fanout_spec(
        *,
        api_name: str,
        parameter_name: str,
        parameter_value: str,
        scope_kind: str,
        observation_date,
        purpose: str,
        policy,
    ) -> BatchChildSpec:
        compact_date = observation_date.strftime("%Y%m%d")
        scope_parameters = {
            "none": {},
            "trade_date": {"trade_date": compact_date},
            "ann_date": {"ann_date": compact_date},
            "period": {"period": compact_date},
            "date_window": {
                "start_date": compact_date,
                "end_date": compact_date,
            },
        }
        parameters = {
            **scope_parameters[scope_kind],
            parameter_name: parameter_value,
        }
        payload = {
            "api_name": api_name,
            "parameters": parameters,
            "complete": True,
            "page_size": policy.page_size,
            "max_pages": max(policy.max_pages, 1000),
            "resume": True,
        }
        return BatchChildSpec(
            task_name="tushare_interface",
            parameters=payload,
            idempotency_key=(
                f"v2:{purpose}:{api_name}:{observation_date.isoformat()}:"
                f"{parameter_name}:{parameter_value}"
            ),
            api_name=api_name,
            cadence="daily" if purpose == "daily" else "backfill",
            period_key=observation_date.isoformat(),
            expected_for=observation_date,
            handler=TASKS.handler_metadata("tushare_interface", payload),
            priority=80 if purpose == "daily" else 30,
            resource_class="generic" if purpose == "daily" else "backfill",
        )

    @staticmethod
    def _normalize_outcome(result: int | TaskExecutionResult) -> TaskExecutionResult:
        if isinstance(result, TaskExecutionResult):
            return result
        return TaskExecutionResult(
            rows_inserted=int(result),
            rows_fetched=int(result),
            completion_status="complete" if int(result) else "empty",
            completion_evidence={
                "verified": False,
                "reason": "legacy integer collector result",
            },
        )

    def _fail_or_retry(
        self,
        execution_id: int,
        *,
        worker_id: str,
        lease_token: str,
        node_status: dict[str, str],
        exc: Exception,
    ) -> dict:
        current = self._repository.get_execution(execution_id)
        if not current:
            raise exc
        status = ExecutionStatus(current["status"])
        if status not in {
            ExecutionStatus.RUNNING,
            ExecutionStatus.VALIDATING,
            ExecutionStatus.PUBLISHING,
        }:
            raise exc
        node_key = current.get("current_node_key") or "condition"
        node_status[node_key] = "failed"
        retryable = bool(getattr(exc, "retryable", True))
        exhausted = int(current["attempt_count"]) >= int(current["max_attempts"])
        target = (
            ExecutionStatus.ATTENTION
            if exhausted or not retryable
            else ExecutionStatus.RETRYING
        )
        delay = min(60 * (2 ** max(int(current["attempt_count"]) - 1, 0)), 900)
        updated = self._repository.transition_execution(
            execution_id,
            expected_status=status,
            target_status=target,
            worker_id=worker_id,
            lease_token=lease_token,
            current_node_key=node_key,
            node_status=node_status,
            eligible_at=(
                datetime.now().astimezone() + timedelta(seconds=delay)
                if target == ExecutionStatus.RETRYING else None
            ),
            error_category=classify_failure(exc),
            error_message=f"{type(exc).__name__}: {exc}"[:4000],
            error_detail={
                "retryable": retryable,
                "attempt": current["attempt_count"],
                "max_attempts": current["max_attempts"],
            },
        )
        self._repository.append_event(
            execution_id,
            event_type=(
                "execution.retry_scheduled"
                if target == ExecutionStatus.RETRYING
                else "execution.attention_required"
            ),
            node_key=node_key,
            attempt_number=int(current["attempt_count"]),
            payload={
                "category": classify_failure(exc),
                "message": str(exc)[:4000],
                "retryable": retryable,
                "delay_seconds": delay if target == ExecutionStatus.RETRYING else None,
            },
        )
        return updated
