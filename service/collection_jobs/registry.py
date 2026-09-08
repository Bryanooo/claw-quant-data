"""Whitelisted collection tasks and their parameter contracts."""

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from service.collection_jobs.models import (
    HandlerMetadata,
    JobHandlerUnavailableError,
    JobHandlerMismatchError,
    InvalidTaskParametersError,
    TaskExecutionResult,
    TaskNotFoundError,
    TaskSpec,
)
from service.config import APP_REVISION


def _compact_date(value: str) -> str:
    try:
        parsed = (
            date(int(value[:4]), int(value[4:6]), int(value[6:8]))
            if len(value) == 8 and value.isdigit()
            else date.fromisoformat(value)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("use YYYY-MM-DD or YYYYMMDD") from exc
    return parsed.strftime("%Y%m%d")


CompactDate = Annotated[str, Field(description="Date in YYYY-MM-DD or YYYYMMDD format")]


class TaskParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DateOnlyParameters(TaskParameters):
    trade_date: CompactDate

    @field_validator("trade_date")
    @classmethod
    def validate_trade_date(cls, value: str) -> str:
        return _compact_date(value)


class ReportPeriodParameters(TaskParameters):
    period: CompactDate

    @field_validator("period")
    @classmethod
    def validate_period(cls, value: str) -> str:
        normalized = _compact_date(value)
        if normalized[4:] not in {"0331", "0630", "0930", "1231"}:
            raise ValueError("period must be a calendar quarter end")
        return normalized


class TradeDateParameters(DateOnlyParameters):
    ts_code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9.]+$")

    @field_validator("ts_code")
    @classmethod
    def normalize_ts_code(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class TradeCalendarParameters(TaskParameters):
    start_date: CompactDate
    end_date: CompactDate
    exchanges: list[Literal["SSE", "SZSE"]] = Field(
        default_factory=lambda: ["SSE", "SZSE"],
        min_length=1,
        max_length=2,
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        return _compact_date(value)

    @model_validator(mode="after")
    def validate_range(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be later than end_date")
        return self


class EmptyParameters(TaskParameters):
    pass


class ScheduledCollectorParameters(TaskParameters):
    schedule_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    scheduled_for: str | None = None

    @field_validator("schedule_id")
    @classmethod
    def validate_schedule_id(cls, value: str) -> str:
        from collectors.scheduler import scheduled_collection_ids

        if value not in scheduled_collection_ids():
            raise ValueError(f"unknown scheduled collector: {value}")
        return value

    @field_validator("scheduled_for")
    @classmethod
    def validate_scheduled_for(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("scheduled_for must be an ISO-8601 timestamp") from exc
        if parsed.tzinfo is None:
            raise ValueError("scheduled_for must include a timezone")
        return parsed.isoformat()


class TushareInterfaceParameters(TaskParameters):
    api_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    parameters: dict[str, Any] = Field(default_factory=dict)
    fields: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_,]*$")
    complete: bool = True
    page_size: int | None = Field(default=None, ge=1, le=10_000)
    max_pages: int | None = Field(default=None, ge=1, le=1_000)
    resume: bool = True

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 50:
            raise ValueError("at most 50 Tushare parameters are allowed")
        if "skip_store" in value:
            raise ValueError("skip_store is reserved and cannot be submitted as a job parameter")
        if any(not key or not key.replace("_", "").isalnum() for key in value):
            raise ValueError("Tushare parameter names must be alphanumeric or underscore")
        return value

    @model_validator(mode="after")
    def validate_interface_access(self):
        from service.tushare_catalog import TushareInterfaceCatalog

        contract = TushareInterfaceCatalog().require_collectable(self.api_name)
        available_fields = [
            item["name"]
            for item in contract.output_parameters
            if item.get("name")
        ]
        if self.fields:
            requested_fields = [item for item in self.fields.split(",") if item]
            unknown_fields = sorted(set(requested_fields) - set(available_fields))
            if available_fields and unknown_fields:
                raise ValueError(
                    f"fields are not present in the {self.api_name} contract: "
                    f"{', '.join(unknown_fields)}"
                )
            self.fields = ",".join(dict.fromkeys(requested_fields))
        elif available_fields:
            # Tushare frequently returns only fields marked as default when the
            # argument is omitted. Persist the complete contract field set in
            # the job so field completeness is explicit and reproducible.
            self.fields = ",".join(dict.fromkeys(available_fields))
        return self


def _run_trade_calendar(parameters: BaseModel) -> TaskExecutionResult:
    from collectors.stock.basic.trade_cal import TradeCalCollector

    values = TradeCalendarParameters.model_validate(parameters)
    start = datetime.strptime(values.start_date, "%Y%m%d").date()
    end = datetime.strptime(values.end_date, "%Y%m%d").date()
    collector = TradeCalCollector()
    total = 0
    chunks = []
    cursor = start
    # trade_cal returns every calendar date. A multi-decade request can hit an
    # upstream row cap without any pagination signal, so exhaust the requested
    # domain in independently bounded calendar-year slices.
    while cursor <= end:
        chunk_end = min(date(cursor.year, 12, 31), end)
        for exchange in values.exchanges:
            rows = collector.collect(
                exchange=exchange,
                start_date=cursor.strftime("%Y%m%d"),
                end_date=chunk_end.strftime("%Y%m%d"),
            )
            total += rows
            chunks.append(
                {
                    "exchange": exchange,
                    "start_date": cursor.isoformat(),
                    "end_date": chunk_end.isoformat(),
                    "rows": rows,
                }
            )
        cursor = chunk_end + timedelta(days=1)
    return TaskExecutionResult(
        rows_inserted=total,
        rows_fetched=total,
        completion_status="complete" if total else "empty",
        completion_evidence={
            "verified": True,
            "verification_type": "bounded_calendar_year_partitions",
            "requested_start": start.isoformat(),
            "requested_end": end.isoformat(),
            "exchanges": list(values.exchanges),
            "chunks": chunks,
        },
    )


def _run_scheduled_collector(parameters: BaseModel) -> TaskExecutionResult:
    from collectors.scheduler import execute_scheduled_collection

    values = ScheduledCollectorParameters.model_validate(parameters)
    return execute_scheduled_collection(values.schedule_id, values.scheduled_for)


def _run_stock_daily(parameters: BaseModel) -> TaskExecutionResult:
    from collectors.stock.market.daily import DailyCollector
    from service.tushare_policy import TusharePolicyRegistry

    values = TradeDateParameters.model_validate(parameters)
    collector = DailyCollector()
    policy = TusharePolicyRegistry().get("daily")
    request = {"trade_date": values.trade_date}
    if values.ts_code:
        request["ts_code"] = values.ts_code
    result = collector.run_offset_paginated(
        page_size=policy.page_size,
        max_pages=policy.max_pages,
        **request,
    )
    return TaskExecutionResult(
        rows_inserted=result.stored_rows,
        rows_fetched=result.fetched_rows,
        completion_status="complete" if result.fetched_rows else "empty",
        completion_evidence=dict(result.evidence),
    )


def _run_stock_basic(parameters: BaseModel) -> int:
    from collectors.stock.basic.stock_basic import StockBasicCollector

    EmptyParameters.model_validate(parameters)
    return StockBasicCollector().collect()


def _run_daily_basic(parameters: BaseModel) -> TaskExecutionResult:
    values = DateOnlyParameters.model_validate(parameters)
    # ``daily_basic`` and ``bak_basic`` are different upstream contracts.  The
    # old repair task accidentally wrote the latter, making coverage repairs
    # appear successful while leaving the audited normalized table untouched.
    return _run_tushare_interface(
        TushareInterfaceParameters(
            api_name="daily_basic",
            parameters={"trade_date": values.trade_date},
            complete=True,
            resume=True,
        )
    )


def _run_moneyflow(parameters: BaseModel) -> TaskExecutionResult:
    from collectors.stock.moneyflow.moneyflow import MoneyflowCollector
    from service.tushare_policy import TusharePolicyRegistry

    values = TradeDateParameters.model_validate(parameters)
    request = {"trade_date": values.trade_date}
    if values.ts_code:
        request["ts_code"] = values.ts_code
    policy = TusharePolicyRegistry().get("moneyflow")
    result = MoneyflowCollector().run_offset_paginated(
        page_size=policy.page_size,
        max_pages=policy.max_pages,
        **request,
    )
    return TaskExecutionResult(
        rows_inserted=result.stored_rows,
        rows_fetched=result.fetched_rows,
        completion_status="complete" if result.fetched_rows else "empty",
        completion_evidence=dict(result.evidence),
    )


def _run_stock_limit(parameters: BaseModel) -> TaskExecutionResult:
    from collectors.stock.market.stk_limit import STKLimitCollector
    from service.tushare_policy import TusharePolicyRegistry

    values = DateOnlyParameters.model_validate(parameters)
    request = {"trade_date": values.trade_date}
    policy = TusharePolicyRegistry().get("stk_limit")
    result = STKLimitCollector().run_offset_paginated(
        page_size=policy.page_size,
        max_pages=policy.max_pages,
        **request,
    )
    return TaskExecutionResult(
        rows_inserted=result.stored_rows,
        rows_fetched=result.fetched_rows,
        completion_status="complete" if result.fetched_rows else "empty",
        completion_evidence=dict(result.evidence),
    )


def _run_stock_suspend(parameters: BaseModel) -> int:
    from collectors.stock.market.suspend_d import SuspendDCollector

    values = TradeDateParameters.model_validate(parameters)
    request = {"trade_date": values.trade_date}
    if values.ts_code:
        request["ts_code"] = values.ts_code
    return SuspendDCollector().collect(**request)


def _run_financial_period(parameters: BaseModel, collector_class) -> int:
    values = ReportPeriodParameters.model_validate(parameters)
    collector = collector_class()
    result = collector.run(period=values.period)
    proof = collector.partition_completion_evidence()
    return TaskExecutionResult(
        rows_inserted=result.stored_rows,
        rows_fetched=result.fetched_rows,
        completion_status="complete" if result.fetched_rows else "empty",
        completion_evidence={
            **dict(result.evidence),
            **proof,
            "collector_name": result.collector_name,
            "collector_version": result.collector_version,
            "request_count": result.request_count,
            "empty_reason": result.empty_reason,
        },
    )


def _run_income_period(parameters: BaseModel) -> int:
    from collectors.stock.finance.income import IncomeCollector

    return _run_financial_period(parameters, IncomeCollector)


def _run_balancesheet_period(parameters: BaseModel) -> int:
    from collectors.stock.finance.balancesheet import BalancesheetCollector

    return _run_financial_period(parameters, BalancesheetCollector)


def _run_cashflow_period(parameters: BaseModel) -> int:
    from collectors.stock.finance.cashflow import CashflowCollector

    return _run_financial_period(parameters, CashflowCollector)


def _run_financial_indicator_period(parameters: BaseModel) -> int:
    from collectors.stock.finance.fina_indicator import FinaIndicatorCollector

    return _run_financial_period(parameters, FinaIndicatorCollector)


def _run_tushare_interface(parameters: BaseModel) -> TaskExecutionResult:
    from collectors.tushare_raw import CatalogRawCollector, verify_complete_response
    from service.collector_catalog import resolve_collector_classes
    from service.tushare_catalog import TushareInterfaceCatalog
    from service.tushare_policy import TusharePolicyRegistry

    values = TushareInterfaceParameters.model_validate(parameters)
    contract = TushareInterfaceCatalog().get(values.api_name)
    if contract.implementation.get("mode") != "generic_raw":
        classes = resolve_collector_classes(values.api_name)
        if len(classes) != 1:
            names = ", ".join(cls.spec().qualified_name for cls in classes) or "none"
            raise RuntimeError(
                f"{values.api_name} resolves to {len(classes)} specialized collectors "
                f"({names}); submit its dedicated scheduled task"
            )
        collector = classes[0]()
        policy = TusharePolicyRegistry().get(values.api_name)
        if policy.pagination_mode == "offset":
            result = collector.run_offset_paginated(
                page_size=values.page_size or policy.page_size,
                max_pages=values.max_pages or policy.max_pages,
                **values.parameters,
            )
            scope_evidence = dict(result.evidence)
        else:
            result = collector.run(**values.parameters)
            partition_proof = getattr(
                collector, "partition_completion_evidence", None
            )
            scope_evidence = (
                partition_proof()
                if callable(partition_proof)
                else verify_complete_response(
                    values.api_name,
                    policy,
                    values.parameters,
                    result.fetched_rows,
                )
            )
            if not scope_evidence.get("verified"):
                raise RuntimeError(
                    f"{values.api_name} did not prove partition completion"
                )
        return TaskExecutionResult(
            rows_inserted=result.stored_rows,
            rows_fetched=result.fetched_rows,
            completion_status="complete" if result.fetched_rows else "empty",
            completion_evidence={
                **dict(result.evidence),
                "storage_mode": "specialized_normalized",
                "collector_name": result.collector_name,
                "collector_version": result.collector_version,
                "table_name": result.table_name,
                "request_count": result.request_count,
                **scope_evidence,
            },
        )
    request = dict(values.parameters)
    if values.fields:
        request["fields"] = values.fields
    collector = CatalogRawCollector(values.api_name)
    if not values.complete:
        stored = collector.collect(**request)
        return TaskExecutionResult(
            rows_inserted=stored,
            rows_fetched=collector._last_fetch_count,
            completion_status="unverified",
            completion_evidence={
                "verified": False,
                "reason": "complete collection protection was disabled",
                "normalization": dict(collector.normalization_evidence),
            },
        )
    if collector.policy.pagination_mode == "offset":
        stored = collector.collect_paginated(
            page_size=values.page_size,
            max_pages=values.max_pages,
            resume=values.resume,
            **request,
        )
    else:
        stored = collector.collect_complete(**request)
    fetched = int(collector.completion_evidence.get("rows_fetched", 0))
    return TaskExecutionResult(
        rows_inserted=stored,
        rows_fetched=fetched,
        completion_status="complete" if fetched > 0 else "empty",
        completion_evidence=collector.completion_evidence,
    )


class TaskRegistry:
    def __init__(self, tasks: Iterable[TaskSpec]):
        self._tasks: dict[str, TaskSpec] = {}
        for task in tasks:
            if task.name in self._tasks:
                raise ValueError(f"duplicate collection task: {task.name}")
            self._tasks[task.name] = task

    def get(self, name: str) -> TaskSpec:
        try:
            return self._tasks[name]
        except KeyError as exc:
            raise TaskNotFoundError(f"unknown collection task: {name}") from exc

    def list(self) -> tuple[TaskSpec, ...]:
        return tuple(sorted(self._tasks.values(), key=lambda item: item.name))

    def validate(self, name: str, parameters: dict) -> BaseModel:
        task = self.get(name)
        try:
            return task.parameters_model.model_validate(parameters)
        except ValidationError as exc:
            raise InvalidTaskParametersError(str(exc)) from exc

    def run(self, name: str, parameters: dict) -> int | TaskExecutionResult:
        task = self.get(name)
        validated = self.validate(name, parameters)
        return task.runner(validated)

    def handler_metadata(self, name: str, parameters: dict) -> HandlerMetadata:
        """Resolve and snapshot the exact logical handler selected for a job."""
        task = self.get(name)
        validated = self.validate(name, parameters)
        normalized = validated.model_dump(mode="json")
        if name == "tushare_interface":
            from service.collector_catalog import resolve_collector_classes
            from service.tushare_catalog import TushareInterfaceCatalog

            interface = TushareInterfaceCatalog().get(normalized["api_name"])
            if interface.implementation.get("mode") == "generic_raw":
                handler_key = f"catalog_typed:{normalized['api_name']}"
                handler_type = "generic"
            else:
                classes = resolve_collector_classes(normalized["api_name"])
                names = "+".join(cls.spec().qualified_name for cls in classes)
                handler_key = f"specialized:{names or normalized['api_name']}"
                handler_type = "specialized"
        elif name == "scheduled_collector":
            handler_key = f"schedule:{normalized['schedule_id']}"
            handler_type = task.handler_type
        else:
            handler_key = f"{task.runner.__module__}:{task.runner.__name__}"
            handler_type = task.handler_type
        return HandlerMetadata(
            handler_type=handler_type,
            handler_key=handler_key,
            handler_version=task.handler_version,
            code_revision=APP_REVISION,
        )

    def assert_handler_compatible(self, job: dict) -> None:
        """Fail closed if a queued job would be routed to a different handler."""
        persisted_key = job.get("handler_key")
        persisted_version = job.get("handler_version")
        if not persisted_key and not persisted_version:  # legacy row
            return
        current = self.handler_metadata(job["task_name"], job["parameters"])
        same_handler = (
            persisted_key == current.handler_key
            and job.get("handler_type") == current.handler_type
        )
        if same_handler:
            if _is_newer_handler_version(persisted_version, current.handler_version):
                raise JobHandlerUnavailableError(
                    "worker handler is older than the persisted job: "
                    f"{persisted_key}@{persisted_version} > "
                    f"{current.handler_key}@{current.handler_version}"
                )
            if persisted_version == current.handler_version or _is_newer_handler_version(
                current.handler_version, persisted_version
            ):
                # Numeric handler versions are backward compatible. This lets
                # an atomic deployment finish already-queued work while older
                # workers still fail closed on jobs created by newer code.
                return
        if (
            persisted_key != current.handler_key
            or persisted_version != current.handler_version
            or job.get("handler_type") != current.handler_type
        ):
            raise JobHandlerMismatchError(
                "persisted handler does not match current registry: "
                f"{persisted_key}@{persisted_version} != "
                f"{current.handler_key}@{current.handler_version}"
            )


def _is_newer_handler_version(required: str | None, available: str | None) -> bool:
    """Compare numeric handler versions without guessing for opaque versions."""
    try:
        required_parts = tuple(int(item) for item in str(required).split("."))
        available_parts = tuple(int(item) for item in str(available).split("."))
    except (TypeError, ValueError):
        return False
    return required_parts > available_parts


TASKS = TaskRegistry(
    [
        TaskSpec(
            "scheduled_collector",
            "执行由 Scheduler 持久化提交的白名单专项采集任务",
            "scheduled",
            ScheduledCollectorParameters,
            _run_scheduled_collector,
            handler_version="2",
        ),
        TaskSpec(
            "trade_calendar",
            "按年度边界分片更新沪深交易日历",
            "reference",
            TradeCalendarParameters,
            _run_trade_calendar,
            handler_version="2",
        ),
        TaskSpec(
            "stock_basic",
            "全量刷新 A 股股票基础信息",
            "reference",
            EmptyParameters,
            _run_stock_basic,
        ),
        TaskSpec(
            "stock_daily",
            "按交易日更新全市场或单只股票日线",
            "market",
            TradeDateParameters,
            _run_stock_daily,
            handler_version="2",
        ),
        TaskSpec(
            "stock_daily_basic",
            "按交易日更新全市场每日基本面",
            "market",
            DateOnlyParameters,
            _run_daily_basic,
        ),
        TaskSpec(
            "moneyflow",
            "按交易日更新全市场或单只股票资金流",
            "moneyflow",
            TradeDateParameters,
            _run_moneyflow,
            handler_version="2",
        ),
        TaskSpec(
            "stock_limit",
            "按交易日更新涨跌停价格",
            "market",
            DateOnlyParameters,
            _run_stock_limit,
            handler_version="2",
        ),
        TaskSpec(
            "stock_suspend",
            "按交易日更新停复牌信息",
            "market",
            TradeDateParameters,
            _run_stock_suspend,
        ),
        TaskSpec(
            "income_period",
            "按报告期完整更新利润表",
            "finance",
            ReportPeriodParameters,
            _run_income_period,
        ),
        TaskSpec(
            "balancesheet_period",
            "按报告期完整更新资产负债表",
            "finance",
            ReportPeriodParameters,
            _run_balancesheet_period,
        ),
        TaskSpec(
            "cashflow_period",
            "按报告期完整更新现金流量表",
            "finance",
            ReportPeriodParameters,
            _run_cashflow_period,
        ),
        TaskSpec(
            "financial_indicator_period",
            "按报告期完整更新财务指标",
            "finance",
            ReportPeriodParameters,
            _run_financial_indicator_period,
        ),
        TaskSpec(
            "tushare_interface",
            "按接口契约路由专项采集器或原始+强类型标准化采集器",
            "catalog",
            TushareInterfaceParameters,
            _run_tushare_interface,
            handler_type="generic",
            handler_version="4",
        ),
    ]
)
