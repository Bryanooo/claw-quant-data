"""Whitelisted datasets exposed by the public data service.

The registry deliberately derives its complete table allow-list from collector
contracts declared in this repository.  This keeps SQL identifiers closed to
user input while preventing a new normalized collector table from silently
being omitted from the REST API.
"""

from collections.abc import Iterable

from service.collector_catalog import CollectorContract, discover_collectors
from service.data_service.models import DatasetNotFoundError, DatasetSpec, DateStorage
from service.tushare_catalog import TushareInterfaceCatalog
from service.tushare_normalization import NORMALIZATION_CONTRACTS
from service.tushare_policy import TusharePolicyRegistry


class DatasetRegistry:
    def __init__(self, datasets: Iterable[DatasetSpec]):
        by_name: dict[str, DatasetSpec] = {}
        for dataset in datasets:
            if dataset.name in by_name:
                raise ValueError(f"duplicate dataset name: {dataset.name}")
            by_name[dataset.name] = dataset
        self._datasets = by_name

    def get(self, name: str) -> DatasetSpec:
        try:
            return self._datasets[name]
        except KeyError as exc:
            raise DatasetNotFoundError(f"unknown dataset: {name}") from exc

    def list(self) -> tuple[DatasetSpec, ...]:
        return tuple(sorted(self._datasets.values(), key=lambda item: item.name))


def _market_dataset(
    name: str,
    description: str,
    *,
    table: str | None = None,
    date_storage: DateStorage = DateStorage.DATE,
    category: str = "market",
    source: str = "Tushare Pro",
    freshness_sla_hours: int = 72,
) -> DatasetSpec:
    return DatasetSpec(
        name=name,
        table=table or name,
        description=description,
        category=category,
        primary_keys=("ts_code", "trade_date"),
        exact_filters={"ts_code": "ts_code"},
        date_column="trade_date",
        date_storage=date_storage,
        default_order=("trade_date", "ts_code"),
        freshness_sla_hours=freshness_sla_hours,
        freshness_policy="max_age",
        source=source,
    )


_DATE_KEY_CANDIDATES = (
    "trade_date",
    "cal_date",
    "report_date",
    "surv_date",
    "float_date",
    "ann_date",
    "end_date",
    "start_date",
    "begin_date",
)

# These normalized tables intentionally retain upstream YYYYMMDD strings.
# Every other inferred date column is a PostgreSQL DATE column.
_COMPACT_DATE_TABLES = {
    "dc_concept",
    "dc_concept_cons",
    "dc_daily",
    "dc_hot",
    "dc_index",
    "dc_member",
    "kpl_concept_cons",
    "kpl_list",
    "limit_cpt_list",
    "limit_list_d",
    "limit_step",
    "margin",
    "margin_detail",
    "margin_secs",
    "slb_len",
    "stk_auction",
    "tdx_daily",
    "tdx_index",
    "tdx_member",
    "ths_hot",
    "top_inst",
    "top_list",
}


def _curated_datasets() -> list[DatasetSpec]:
    return [
        DatasetSpec(
            name="stock_basic",
            table="stock_basic",
            description="A股股票基础信息",
            category="reference",
            primary_keys=("ts_code",),
            exact_filters={
                "ts_code": "ts_code",
                "symbol": "symbol",
                "name": "name",
                "market": "market",
                "exchange": "exchange",
                "industry": "industry",
                "list_status": "list_status",
            },
            default_order=("ts_code",),
            default_descending=False,
            freshness_sla_hours=None,
        ),
        DatasetSpec(
            name="tushare_raw",
            table="tushare_raw_record",
            description="契约驱动采集器保存的 Tushare 原始 JSON 记录",
            category="catalog",
            primary_keys=("api_name", "request_hash", "record_hash"),
            exact_filters={
                "api_name": "api_name",
                "request_hash": "request_hash",
                "record_hash": "record_hash",
            },
            default_order=("collected_at", "api_name"),
            freshness_sla_hours=None,
        ),
        DatasetSpec(
            name="trade_calendar",
            table="trade_cal",
            description="交易所交易日历",
            category="reference",
            primary_keys=("exchange", "cal_date"),
            exact_filters={"exchange": "exchange", "is_open": "is_open"},
            date_column="cal_date",
            default_order=("cal_date", "exchange"),
            default_descending=False,
            freshness_sla_hours=48,
            freshness_policy="max_age",
        ),
        _market_dataset("stock_daily", "A股日线行情", table="daily"),
        _market_dataset(
            "stock_daily_basic",
            "A股每日基本面",
            table="tushare_current_daily_basic",
        ),
        _market_dataset("stock_limit", "A股每日涨跌停价格", table="stk_limit"),
        DatasetSpec(
            name="stock_suspend",
            table="suspend_d",
            description="A股停复牌信息",
            category="market",
            primary_keys=("ts_code", "trade_date", "suspend_type"),
            exact_filters={"ts_code": "ts_code", "suspend_type": "suspend_type"},
            date_column="trade_date",
            default_order=("trade_date", "ts_code"),
            freshness_sla_hours=72,
            freshness_policy="max_age",
        ),
        _market_dataset("moneyflow", "A股个股资金流向", category="moneyflow"),
        DatasetSpec(
            name="income",
            table="income",
            description="上市公司利润表",
            category="finance",
            primary_keys=("ts_code", "end_date", "report_type"),
            exact_filters={"ts_code": "ts_code", "report_type": "report_type"},
            date_column="end_date",
            default_order=("end_date", "ts_code"),
            freshness_sla_hours=24 * 120,
            freshness_policy="quarterly_disclosure",
        ),
        DatasetSpec(
            name="balancesheet",
            table="balancesheet",
            description="上市公司资产负债表",
            category="finance",
            primary_keys=("ts_code", "end_date", "report_type"),
            exact_filters={"ts_code": "ts_code", "report_type": "report_type"},
            date_column="end_date",
            default_order=("end_date", "ts_code"),
            freshness_sla_hours=24 * 120,
            freshness_policy="quarterly_disclosure",
        ),
        DatasetSpec(
            name="cashflow",
            table="cashflow",
            description="上市公司现金流量表",
            category="finance",
            primary_keys=("ts_code", "end_date", "report_type"),
            exact_filters={"ts_code": "ts_code", "report_type": "report_type"},
            date_column="end_date",
            default_order=("end_date", "ts_code"),
            freshness_sla_hours=24 * 120,
            freshness_policy="quarterly_disclosure",
        ),
        DatasetSpec(
            name="financial_indicator",
            table="fina_indicator",
            description="上市公司财务指标",
            category="finance",
            primary_keys=("ts_code", "end_date"),
            exact_filters={"ts_code": "ts_code"},
            date_column="end_date",
            default_order=("end_date", "ts_code"),
            freshness_sla_hours=24 * 120,
            freshness_policy="quarterly_disclosure",
        ),
        _market_dataset(
            "index_daily",
            "国内指数日线行情",
            category="index",
        ),
        _market_dataset(
            "index_weekly",
            "国内指数周线行情",
            category="index",
            freshness_sla_hours=24 * 10,
        ),
        _market_dataset(
            "index_monthly",
            "国内指数月线行情",
            category="index",
            freshness_sla_hours=24 * 45,
        ),
        _market_dataset(
            "industry_daily",
            "同花顺行业和概念指数行情",
            table="ths_daily",
            category="index",
        ),
        _market_dataset(
            "forex_daily",
            "外汇日线行情",
            table="fx_daily",
            category="forex",
            source="Tushare Pro / FXCM",
        ),
        _market_dataset(
            "sge_daily",
            "上海黄金交易所现货日线行情",
            category="commodity",
            source="Tushare Pro / SGE",
        ),
    ]


def _inferred_date_column(contract: CollectorContract) -> str | None:
    return next(
        (name for name in _DATE_KEY_CANDIDATES if name in contract.primary_keys),
        None,
    )


def _generated_dataset(
    contract: CollectorContract,
    *,
    title: str,
    description: str,
) -> DatasetSpec:
    date_column = _inferred_date_column(contract)
    details = description.strip() or f"Tushare {contract.api_name} 接口数据"
    if contract.table_name != contract.api_name:
        details = f"{details}（规范化表：{contract.table_name}）"
    freshness_hours, freshness_policy = _inferred_freshness(
        contract.api_name,
        date_column,
    )
    return DatasetSpec(
        name=contract.table_name,
        table=contract.table_name,
        description=title.strip() or details,
        category=contract.resource_class.value,
        primary_keys=contract.primary_keys,
        exact_filters={name: name for name in contract.primary_keys},
        date_column=date_column,
        date_storage=(
            DateStorage.COMPACT
            if contract.table_name in _COMPACT_DATE_TABLES
            else DateStorage.DATE
        ),
        default_order=contract.primary_keys,
        freshness_sla_hours=freshness_hours,
        freshness_policy=freshness_policy,
    )


def _inferred_freshness(
    api_name: str,
    date_column: str | None,
) -> tuple[int | None, str]:
    """Infer freshness only for a proven periodic partition.

    Event/disclosure dates are intentionally classified as event-driven: an
    old latest event is not evidence that collection is stale.  This is a
    deliberate policy, not missing configuration.  A ``trade_date`` policy
    writing a ``trade_date`` partition, however, has a defensible market-data
    freshness SLA.
    """
    # Securities-lending publication stopped for a long interval after the
    # regulator suspended new lending. An old latest row is not collector
    # staleness; recurring empty checks remain visible in job evidence.
    if api_name in {"slb_len", "slb_len_mm", "slb_sec", "slb_sec_detail"}:
        return None, "event_driven"
    if date_column != "trade_date":
        return None, "event_driven"
    policy = TusharePolicyRegistry().get(api_name)
    if policy.parameter_strategy != "trade_date":
        return None, "event_driven"
    hours = {
        "daily": 72,
        "weekly": 24 * 10,
        "monthly": 24 * 45,
        "quarterly": 24 * 120,
    }.get(policy.cadence)
    return (hours, "max_age") if hours is not None else (None, "event_driven")


def build_dataset_registry() -> DatasetRegistry:
    """Build the public allow-list and guarantee collector-table coverage."""
    datasets = _curated_datasets()
    registered_tables = {item.table for item in datasets}
    catalog = TushareInterfaceCatalog()

    for contract in discover_collectors():
        if contract.table_name in registered_tables:
            continue
        upstream = catalog.get(contract.api_name)
        datasets.append(
            _generated_dataset(
                contract,
                title=upstream.title,
                description=upstream.description,
            )
        )
        registered_tables.add(contract.table_name)

    for contract in NORMALIZATION_CONTRACTS.list():
        if contract.table_name in registered_tables:
            continue
        order = (
            (contract.date_column, "_record_hash")
            if contract.date_column
            else ("_source_collected_at", "_record_hash")
        )
        freshness_hours, freshness_policy = _inferred_freshness(
            contract.api_name,
            contract.date_column,
        )
        datasets.append(
            DatasetSpec(
                name=contract.api_name,
                table=contract.table_name,
                description=f"{contract.title}（契约驱动标准化数据）",
                category=contract.category,
                primary_keys=("_record_hash",),
                exact_filters={
                    "_record_hash": "_record_hash",
                    **{field.name: field.name for field in contract.fields},
                },
                date_column=contract.date_column,
                date_storage=DateStorage.DATE,
                default_order=order,
                freshness_sla_hours=freshness_hours,
                freshness_policy=freshness_policy,
                storage_semantics="versioned_payload",
                business_identity_fields=contract.business_identity_fields,
                identity_confidence=contract.identity_confidence,
                current_view=(
                    f"tushare_current_{contract.api_name}"
                    if contract.identity_confidence == "contract_reviewed"
                    else None
                ),
            )
        )
        registered_tables.add(contract.table_name)

    return DatasetRegistry(datasets)


DATASETS = build_dataset_registry()
