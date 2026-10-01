from datetime import date

import pytest

from service.orchestration_v2.contracts import DatasetAuditContract
from service.orchestration_v2.service import OrchestrationV2Service
from service.orchestration_v2.runtime import (
    OrchestrationV2Runtime,
    bounded_history_target_date,
)
from service.tushare_policy import TusharePolicyRegistry
from service.acquisition_runtime.fanout import FANOUT_DEFINITIONS
from service.orchestration_v2.repair_planning import (
    observation_identity,
    observation_bounds,
    plan_period_repairs,
    validate_single_period_scope,
)


def test_standalone_gap_repair_module_imports_without_cycle():
    from service.orchestration_v2.gap_repair import plan_current_repairs

    assert callable(plan_current_repairs)


def _contract(dataset: str, granularity: str = "day"):
    return DatasetAuditContract(
        dataset_name=dataset,
        audit_mode="expected_partition",
        period_granularity=granularity,
        date_column="trade_date",
    )


def test_repair_planner_collapses_outputs_but_never_days():
    proposals = plan_period_repairs(
        task_key="daily_bundle",
        contracts=(_contract("prices"), _contract("valuation")),
        problem_partitions={
            "prices": {
                date(2026, 9, 23): "missing",
                date(2026, 9, 24): "missing",
            },
            "valuation": {date(2026, 9, 24): "partial"},
        },
    )

    assert [item.observation_key for item in proposals] == [
        "2026-09-24", "2026-09-23"
    ]
    assert proposals[0].datasets == ("prices", "valuation")
    assert proposals[0].reasons == ("missing", "partial")
    assert proposals[0].idempotency_key == "v2:repair:daily_bundle:2026-09-24"


@pytest.mark.parametrize(
    ("granularity", "value", "expected"),
    [
        ("day", date(2026, 9, 24), "2026-09-24"),
        ("week", date(2026, 9, 24), "2026-W39"),
        ("month", date(2026, 9, 30), "2026-09"),
        ("quarter", date(2026, 9, 30), "2026-Q3"),
    ],
)
def test_observation_identity(granularity, value, expected):
    assert observation_identity(value, granularity) == expected


@pytest.mark.parametrize(
    ("granularity", "value", "expected"),
    [
        ("day", date(2026, 9, 24), (date(2026, 9, 24), date(2026, 9, 24))),
        ("week", date(2026, 9, 24), (date(2026, 9, 21), date(2026, 9, 27))),
        ("month", date(2026, 2, 13), (date(2026, 2, 1), date(2026, 2, 28))),
        ("quarter", date(2026, 5, 13), (date(2026, 4, 1), date(2026, 6, 30))),
    ],
)
def test_observation_bounds_cover_the_full_logical_period(
    granularity, value, expected
):
    assert observation_bounds(value, granularity) == expected


def test_weekly_repair_uses_full_period_and_scope_aware_identity():
    proposals = plan_period_repairs(
        task_key="index_weekly",
        contracts=(_contract("index_weekly", "week"),),
        problem_partitions={"index_weekly": {date(2026, 9, 24): "missing"}},
    )

    assert len(proposals) == 1
    assert proposals[0].observation_start == date(2026, 9, 21)
    assert proposals[0].observation_end == date(2026, 9, 27)
    assert proposals[0].idempotency_key.endswith(
        ":2026-W39:2026-09-21:2026-09-27"
    )


def test_trade_date_history_uses_last_open_day_of_logical_period():
    trade_dates = [date(2026, 9, 21), date(2026, 9, 24)]

    assert bounded_history_target_date(
        "trade_date", date(2026, 9, 27), trade_dates
    ) == date(2026, 9, 24)
    assert bounded_history_target_date(
        "month", date(2026, 9, 30), trade_dates
    ) == date(2026, 9, 30)


def test_static_provider_partitions_stay_inside_one_v2_execution_node():
    policy = TusharePolicyRegistry().get("opt_daily")
    specs = tuple(
        OrchestrationV2Runtime._static_fanout_spec(
            api_name="opt_daily",
            parameter_name="exchange",
            parameter_value=exchange,
            scope_kind="trade_date",
            observation_date=date(2026, 9, 24),
            purpose="repair",
            policy=policy,
        )
        for exchange in ("SSE", "SZSE", "CFFEX")
    )

    assert len(specs) == 3
    assert {item.parameters["parameters"]["exchange"] for item in specs} == {
        "SSE", "SZSE", "CFFEX"
    }
    assert all(
        item.parameters["parameters"]["trade_date"] == "20260924"
        for item in specs
    )
    assert all(item.expected_for == date(2026, 9, 24) for item in specs)
    assert all(item.period_key == "2026-09-24" for item in specs)


def test_static_provider_retry_skips_only_verified_request_partitions():
    policy = TusharePolicyRegistry().get("opt_daily")
    specs = tuple(
        OrchestrationV2Runtime._static_fanout_spec(
            api_name="opt_daily",
            parameter_name="exchange",
            parameter_value=exchange,
            scope_kind="trade_date",
            observation_date=date(2026, 9, 24),
            purpose="backfill",
            policy=policy,
        )
        for exchange in ("SSE", "SZSE", "CFFEX")
    )

    remaining = OrchestrationV2Runtime._remaining_specs(
        specs,
        [{
            "request_key": specs[1].idempotency_key,
            "completion_status": "complete",
            "completion_evidence": {"verified": True},
        }],
    )

    assert [item.idempotency_key for item in remaining] == [
        specs[0].idempotency_key,
        specs[2].idempotency_key,
    ]


def test_runtime_reads_all_durable_request_evidence_without_ui_limit():
    class Repository:
        def list_verified_acquisition_evidence(self, execution_id):
            assert execution_id == 42
            return [
                {
                    "request_key": f"request-{index}",
                    "completion_status": "complete",
                    "completion_evidence": {"verified": True},
                }
                for index in range(1_501)
            ]

        def list_execution_events(self, *_args, **_kwargs):
            raise AssertionError("the UI-limited event reader must not be used")

    evidence = OrchestrationV2Runtime(
        Repository()
    )._verified_acquisition_evidence(42)

    assert len(evidence) == 1_501


def test_financial_period_is_one_whole_market_request():
    spec = OrchestrationV2Runtime._period_finance_spec(
        api_name="forecast",
        period=date(2026, 6, 30),
        purpose="daily",
    )

    assert spec.parameters["parameters"] == {"period": "20260630"}
    assert spec.resource_class == "finance"


@pytest.mark.parametrize(
    ("task_key", "date_column", "observation_date", "expected_parameters"),
    [
        ("fund_nav", "nav_date", date(2026, 9, 30), {"nav_date": "20260930"}),
        (
            "fund_portfolio",
            "end_date",
            date(2026, 6, 30),
            {"period": "20260630"},
        ),
    ],
)
def test_proven_market_wide_endpoints_do_not_use_legacy_symbol_fanout(
    monkeypatch,
    task_key,
    date_column,
    observation_date,
    expected_parameters,
):
    from tests.test_orchestration_v2 import acquisition_definition
    from service.orchestration_v2.contracts import TaskDefinitionDocument

    definition = acquisition_definition(
        task_key=task_key,
        output_datasets=[task_key],
        acquisition_endpoint_ids=[7],
    )
    definition["validation_contract"]["outputs"] = [task_key]
    definition["validation_contract"]["dataset_audits"][0].update({
        "dataset_name": task_key,
        "date_column": date_column,
    })
    document = TaskDefinitionDocument.model_validate(definition)

    class Repository:
        @staticmethod
        def get_endpoint(_endpoint_id):
            return {
                "acquisition_endpoint_id": 7,
                "endpoint_key": task_key,
                "source_id": "tushare",
                "lifecycle_status": "active",
            }

    monkeypatch.setattr(
        "service.orchestration_v2.runtime.list_fanout_values",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("legacy symbol fanout must not be evaluated")
        ),
    )
    runtime = OrchestrationV2Runtime(Repository())
    specs = runtime._plan_acquisition(document, {
        "purpose": "daily",
        "observation_start": observation_date,
        "observation_end": observation_date,
        "frozen_scope": (
            {"policy_anchor_date": "2026-09-28"}
            if task_key == "fund_portfolio" else {}
        ),
    })

    assert len(specs) == 1
    assert specs[0].api_name == task_key
    assert specs[0].parameters["parameters"] == expected_parameters


def test_daily_dividend_uses_exact_announcement_date_not_all_stock_fanout(
    monkeypatch,
):
    from tests.test_orchestration_v2 import acquisition_definition
    from service.orchestration_v2.contracts import TaskDefinitionDocument

    definition = acquisition_definition(
        task_key="dividend",
        output_datasets=["dividend"],
        acquisition_endpoint_ids=[7],
    )
    definition["validation_contract"]["outputs"] = ["dividend"]
    definition["validation_contract"]["dataset_audits"][0].update({
        "dataset_name": "dividend",
        "audit_mode": "observed_scope_transport",
        "date_column": "ex_date",
    })
    document = TaskDefinitionDocument.model_validate(definition)

    class Repository:
        @staticmethod
        def get_endpoint(_endpoint_id):
            return {
                "acquisition_endpoint_id": 7,
                "endpoint_key": "dividend",
                "source_id": "tushare",
                "lifecycle_status": "active",
            }

    monkeypatch.setattr(
        "service.orchestration_v2.runtime.list_fanout_values",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("daily dividend must not enumerate all stocks")
        ),
    )
    specs = OrchestrationV2Runtime(Repository())._plan_acquisition(document, {
        "purpose": "daily",
        "observation_start": date(2026, 9, 30),
        "observation_end": date(2026, 9, 30),
        "frozen_scope": {},
    })

    assert len(specs) == 1
    assert specs[0].parameters["parameters"] == {"ann_date": "20260930"}


def test_dynamic_dependency_fanout_stays_inside_one_execution(monkeypatch):
    monkeypatch.setattr(
        "service.orchestration_v2.runtime.list_fanout_values",
        lambda _source, as_of=None: ["885001.TI", "885002.TI"],
    )

    specs = OrchestrationV2Runtime._dynamic_fanout_specs(
        api_name="ths_member",
        fanout=FANOUT_DEFINITIONS["ths_member"],
        observation_start=date(2026, 9, 21),
        observation_end=date(2026, 9, 27),
        purpose="daily",
    )

    assert len(specs) == 2
    assert [item.parameters["parameters"]["ts_code"] for item in specs] == [
        "885001.TI",
        "885002.TI",
    ]


def test_v2_execution_scope_rejects_multi_period_backfill():
    contract = _contract("prices")
    validate_single_period_scope(
        contract=contract,
        observation_start=date(2026, 9, 24),
        observation_end=date(2026, 9, 24),
        observation_key="2026-09-24",
    )
    with pytest.raises(ValueError, match="exactly one logical"):
        validate_single_period_scope(
            contract=contract,
            observation_start=date(2026, 9, 23),
            observation_end=date(2026, 9, 24),
            observation_key="2026-09-23",
        )


class _ExecutionRepository:
    def __init__(self, definition):
        self.definition = definition
        self.created = None

    def get_active_definition(self, _task_key):
        return {"definition": self.definition.model_dump(mode="json")}

    def create_execution(self, request):
        self.created = request
        return {"task_key": request.task_key}, True


def test_service_enforces_single_period_before_persistence():
    from tests.test_orchestration_v2 import acquisition_definition
    from service.orchestration_v2.contracts import TaskDefinitionDocument

    definition = TaskDefinitionDocument.model_validate(acquisition_definition())
    repository = _ExecutionRepository(definition)
    service = OrchestrationV2Service(
        repository,
        allowed_handler_keys=(),
        known_datasets=(),
    )
    base = {
        "task_key": "daily_basic",
        "purpose": "backfill",
        "trigger_source": "recovery",
        "idempotency_key": "v2:repair:daily_basic:2026-09-24",
        "observation_key": "2026-09-24",
        "observation_start": date(2026, 9, 24),
        "observation_end": date(2026, 9, 24),
    }
    assert service.create_execution(base)[1] is True

    with pytest.raises(ValueError, match="exactly one logical"):
        service.create_execution({
            **base,
            "idempotency_key": "bad-range",
            "observation_end": date(2026, 9, 25),
        })
