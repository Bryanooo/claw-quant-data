"""Targeted post-collection coverage verification planning."""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

from service.clock import business_now
from service.history_baselines import (
    INITIALIZATION_STRICT_COVERAGE_LOOKBACK_DAYS,
    INITIALIZATION_TRANSPORT_VERIFIED_DATASETS,
)


@dataclass(frozen=True, slots=True)
class VerificationRequest:
    dataset_name: str
    start_date: date
    end_date: date
    idempotency_key: str

    def as_dict(self) -> dict:
        return asdict(self)


_DIRECT_DATASETS = {
    "stock_daily": ("stock_daily", "trade_date"),
    "stock_daily_basic": ("stock_daily_basic", "trade_date"),
    "moneyflow": ("moneyflow", "trade_date"),
    "stock_limit": ("stock_limit", "trade_date"),
    "income_period": ("income", "period"),
    "balancesheet_period": ("balancesheet", "period"),
    "cashflow_period": ("cashflow", "period"),
    "financial_indicator_period": ("financial_indicator", "period"),
}

_SCHEDULED_DAILY_DATASETS = {
    "daily_daily": "stock_daily",
    "bak_basic_daily": "stock_daily_basic",
    "stk_limit_daily": "stock_limit",
    "index_daily_daily": "index_daily",
    "ths_daily_daily": "industry_daily",
}

_SCHEDULED_FINANCE_DATASETS = {
    "income_quarterly": "income",
    "income_annual_update": "income",
    "balancesheet_quarterly": "balancesheet",
    "balancesheet_annual": "balancesheet",
    "cashflow_quarterly": "cashflow",
    "cashflow_annual": "cashflow",
    "fina_indicator_quarterly": "financial_indicator",
    "fina_indicator_annual": "financial_indicator",
}

_INTERFACE_DATASET_ALIASES = {
    "daily_basic": "stock_daily_basic",
}


def _compact_date(value: str) -> date:
    return datetime.strptime(value.replace("-", ""), "%Y%m%d").date()


def _financial_period(at: date) -> date:
    if at.month >= 11:
        return date(at.year, 9, 30)
    if at.month >= 9:
        return date(at.year, 6, 30)
    if at.month >= 5:
        return date(at.year, 3, 31)
    return date(at.year - 1, 12, 31)


class CollectionVerificationPlanner:
    """Resolve only audits that can prove the exact normalized write scope."""

    def plan(self, job: dict) -> VerificationRequest | None:
        task_name = job["task_name"]
        parameters = job["parameters"]
        target: date | None = None
        dataset_name: str | None = None

        direct = _DIRECT_DATASETS.get(task_name)
        if direct:
            # A single-security repair cannot be judged against the full-market
            # entity threshold. Its later dataset audit remains authoritative.
            if parameters.get("ts_code"):
                return None
            dataset_name, parameter_name = direct
            target = _compact_date(parameters[parameter_name])
        elif task_name == "scheduled_collector":
            schedule_id = parameters["schedule_id"]
            scheduled_value = parameters.get("scheduled_for")
            if not scheduled_value:
                return None
            scheduled_for = datetime.fromisoformat(scheduled_value)
            if schedule_id in _SCHEDULED_DAILY_DATASETS:
                dataset_name = _SCHEDULED_DAILY_DATASETS[schedule_id]
                target = scheduled_for.date()
            elif schedule_id in _SCHEDULED_FINANCE_DATASETS:
                dataset_name = _SCHEDULED_FINANCE_DATASETS[schedule_id]
                target = _financial_period(scheduled_for.date())
        elif task_name == "tushare_interface":
            # A transport-level exhaustion proof is necessary but not always
            # sufficient: exchanges may publish one market before the others.
            # Exact-date interfaces with a scheduled coverage rule therefore
            # enter ``verifying`` even when their collector returned complete.
            api_name = parameters.get("api_name")
            request = parameters.get("parameters") or {}
            raw_target = request.get("trade_date")
            if api_name and raw_target:
                candidate = _INTERFACE_DATASET_ALIASES.get(api_name, api_name)
                from service.data_coverage.models import CoverageRuleNotFoundError
                from service.data_coverage.registry import COVERAGE_RULES

                try:
                    rule = COVERAGE_RULES.get(candidate)
                except CoverageRuleNotFoundError:
                    rule = None
                if rule and rule.scheduled and rule.detects_missing_partitions:
                    dataset_name = candidate
                    target = _compact_date(str(raw_target))

        if dataset_name is None or target is None:
            return None
        if (
            job.get("cadence") == "initialization"
            and dataset_name in INITIALIZATION_TRANSPORT_VERIFIED_DATASETS
            and target < business_now().date() - timedelta(
                days=INITIALIZATION_STRICT_COVERAGE_LOOKBACK_DAYS - 1
            )
        ):
            return None
        return VerificationRequest(
            dataset_name=dataset_name,
            start_date=target,
            end_date=target,
            idempotency_key=f"verify-collection-job-{job['job_id']}",
        )
