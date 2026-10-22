"""Machine-readable V2 task baseline compiled from governed source metadata."""

from __future__ import annotations

from dataclasses import dataclass

from service.source_connectors.registry import SOURCE_REGISTRY


@dataclass(frozen=True, slots=True)
class EndpointRef:
    source_id: str
    endpoint_key: str


@dataclass(frozen=True, slots=True)
class AcquisitionTaskBlueprint:
    task_key: str
    endpoints: tuple[EndpointRef, ...]
    output_datasets: tuple[str, ...]
    cadence: str
    resource_class: str


@dataclass(frozen=True, slots=True)
class TransformationTaskBlueprint:
    task_key: str
    input_datasets: tuple[str, ...]
    output_datasets: tuple[str, ...]
    dependency_task_keys: tuple[str, ...]
    priority: int
    implementation_version: str = "planned-v1"


# Equivalent upstream endpoints are alternatives or frequency variants of one
# logical product. Pagination, symbols and date windows remain inside the
# acquire node; they never become task definitions.
_EQUIVALENT_ENDPOINT_GROUPS: dict[str, tuple[str, ...]] = {
    "balancesheet": ("balancesheet", "balancesheet_vip"),
    "cashflow": ("cashflow", "cashflow_vip"),
    "express": ("express", "express_vip"),
    "financial_indicator": ("fina_indicator", "fina_indicator_vip"),
    "fina_mainbz": ("fina_mainbz", "fina_mainbz_vip"),
    "forecast": ("forecast", "forecast_vip"),
    "income": ("income", "income_vip"),
    "stock_st": ("st", "stock_st"),
    "stk_weekly_monthly": ("weekly", "monthly", "stk_weekly_monthly"),
}


_OUTPUT_DATASET_OVERRIDES = {
    "shibor_lpr": "cn_lpr",
    "daily": "stock_daily",
    "fx_daily": "forex_daily",
    "stk_limit": "stock_limit",
    "suspend_d": "stock_suspend",
    "ths_daily": "industry_daily",
    "trade_cal": "trade_calendar",
}

_TASK_KEY_OVERRIDES = {
    "shibor_lpr": "cn_lpr",
}


# 官方公开源 scheduled-pull tasks: endpoints registered in the source
# registry with SCHEDULED_PULL mode and a dedicated connector that persists
# canonical rows (chinabond.py mirrors chinamoney.py).
_OFFICIAL_SOURCE_TASKS: tuple[dict[str, str], ...] = (
    {
        "task_key": "chinabond_yield_curve",
        "source_id": "chinabond",
        "endpoint_key": "yield_curve_history",
        "output_dataset": "chinabond_yield_curve",
    },
)

# 蚂蚁数据源 scheduled-pull tasks (2026-10 product decision): routes without a
# Tushare equivalent whose research value needs accumulated time series.
# Endpoint keys map to the SOURCE_REGISTRY scheduled-pull allow-list; the
# acquire node resolves route parameters inside ant_scheduled.py.
_FINANCIAL_DATA_TASKS: tuple[dict[str, str], ...] = (
    {
        "task_key": "ant_hot_stock_rank",
        "endpoint_key": "altdata.hot-stock-rank",
        "output_dataset": "ant_hot_stock_rank",
    },
    {
        "task_key": "ant_hot_plate_rank",
        "endpoint_key": "altdata.hot-plate-rank",
        "output_dataset": "ant_hot_plate_rank",
    },
    {
        "task_key": "ant_equity_structure",
        "endpoint_key": "stock_fnd.equity-structure",
        "output_dataset": "ant_equity_structure",
    },
    {
        "task_key": "ant_free_float",
        "endpoint_key": "stock_fnd.free-float",
        "output_dataset": "ant_free_float",
    },
    {
        "task_key": "ant_actual_controller",
        "endpoint_key": "stock_fnd.actual-controller",
        "output_dataset": "ant_actual_controller",
    },
    {
        "task_key": "ant_controlling_shareholder",
        "endpoint_key": "stock_fnd.controlling-shareholder",
        "output_dataset": "ant_controlling_shareholder",
    },
    {
        "task_key": "ant_style_classification",
        "endpoint_key": "stock_fnd.style-classification",
        "output_dataset": "ant_style_classification",
    },
)


_DERIVED_TASKS = (
    TransformationTaskBlueprint(
        "ggt_monthly", ("ggt_daily",), ("ggt_monthly",), ("ggt_daily",), 80
    ),
    TransformationTaskBlueprint(
        "adjusted_price_return",
        ("stock_daily", "adj_factor"),
        ("adjusted_price_return",),
        ("daily", "adj_factor"),
        90,
    ),
    TransformationTaskBlueprint(
        "canonical_period_bars",
        ("adjusted_price_return",),
        ("canonical_period_bars",),
        ("adjusted_price_return",),
        85,
    ),
    TransformationTaskBlueprint(
        "technical_factor_snapshot",
        ("stock_daily", "adj_factor", "stock_basic"),
        ("technical_factor_snapshot",),
        ("daily", "adj_factor", "stock_basic"),
        90,
        # v4 freezes the same-day security master alongside bars and factors,
        # so newly listed and final-day delisted securities cannot be omitted
        # because the derived task raced a weekly reference refresh.
        "technical-factor-snapshot-v4",
    ),
    TransformationTaskBlueprint(
        "valuation_percentile_snapshot",
        ("stock_daily_basic", "index_member_all"),
        ("valuation_percentile_snapshot",),
        ("daily_basic", "index_member_all"),
        80,
    ),
    TransformationTaskBlueprint(
        "fama_french_daily",
        (
            "stock_daily",
            # The orchestration data-plane name follows the acquisition
            # endpoint output.  ``stock_daily_basic`` is the public data
            # service alias, not the dataset_state identity.
            "daily_basic",
            "stock_st",
        ),
        ("fama_french_daily",),
        ("daily", "daily_basic", "stock_st"),
        80,
        "ff3-sh-sz-v2",
    ),
    TransformationTaskBlueprint(
        "market_breadth",
        ("stock_daily", "stock_limit"),
        ("market_breadth",),
        ("daily", "stk_limit"),
        85,
    ),
    TransformationTaskBlueprint(
        "sector_breadth",
        ("stock_daily", "index_member_all"),
        ("sector_breadth",),
        ("daily", "index_member_all"),
        80,
    ),
    TransformationTaskBlueprint(
        "etf_flow",
        ("etf_share_size", "fund_nav", "fund_daily"),
        ("etf_flow",),
        ("etf_share_size", "fund_nav", "fund_daily"),
        80,
    ),
    TransformationTaskBlueprint(
        "sector_rotation",
        ("sector_breadth", "industry_daily"),
        ("sector_rotation",),
        ("sector_breadth", "ths_daily"),
        70,
    ),
    TransformationTaskBlueprint(
        "industry_fundamental_snapshot",
        ("index_member_all", "financial_indicator", "stock_daily_basic"),
        ("industry_fundamental_snapshot",),
        ("index_member_all", "financial_indicator", "daily_basic"),
        70,
    ),
    TransformationTaskBlueprint(
        "repurchase_progress_snapshot",
        ("repurchase", "major_news", "stock_daily"),
        ("repurchase_progress_snapshot",),
        ("repurchase", "major_news", "daily"),
        70,
    ),
    TransformationTaskBlueprint(
        "investment_event_calendar",
        ("eco_cal", "cn_schedule", "idx_anns"),
        ("investment_event_calendar",),
        ("eco_cal", "cn_schedule", "idx_anns"),
        70,
    ),
    TransformationTaskBlueprint(
        "macro_regime",
        ("cn_gdp", "cn_cpi", "cn_pmi", "cn_ppi", "cn_m", "sf_month", "cn_lpr"),
        ("macro_regime",),
        ("cn_gdp", "cn_cpi", "cn_pmi", "cn_ppi", "cn_m", "sf_month", "cn_lpr"),
        60,
    ),
    TransformationTaskBlueprint(
        "etf_state_team_signal",
        ("etf_flow", "fund_portfolio", "major_news"),
        ("etf_state_team_signal",),
        ("etf_flow", "fund_portfolio", "major_news"),
        50,
    ),
)


def acquisition_task_blueprints() -> tuple[AcquisitionTaskBlueprint, ...]:
    endpoints = {
        item.endpoint_key: item
        for item in SOURCE_REGISTRY.list_endpoints("tushare")
    }
    consumed: set[str] = set()
    tasks: list[AcquisitionTaskBlueprint] = []

    for task_key, endpoint_keys in _EQUIVALENT_ENDPOINT_GROUPS.items():
        members = tuple(endpoints[key] for key in endpoint_keys)
        consumed.update(endpoint_keys)
        canonical = members[-1] if task_key == "stk_weekly_monthly" else members[0]
        tasks.append(AcquisitionTaskBlueprint(
            task_key=task_key,
            endpoints=tuple(EndpointRef(item.source_id, item.endpoint_key) for item in members),
            output_datasets=(task_key,),
            cadence=canonical.cadence,
            resource_class=canonical.resource_class,
        ))

    for endpoint_key, endpoint in endpoints.items():
        if endpoint_key in consumed:
            continue
        endpoint_refs = (EndpointRef(endpoint.source_id, endpoint.endpoint_key),)
        if endpoint_key == "shibor_lpr":
            # The official source has priority and Tushare is the audited fallback.
            endpoint_refs = (
                EndpointRef("chinamoney", "lpr_history"),
                *endpoint_refs,
            )
        task_key = _TASK_KEY_OVERRIDES.get(endpoint_key, endpoint_key)
        tasks.append(AcquisitionTaskBlueprint(
            task_key=task_key,
            endpoints=endpoint_refs,
            output_datasets=(
                _OUTPUT_DATASET_OVERRIDES.get(endpoint_key, endpoint_key),
            ),
            cadence=endpoint.cadence,
            resource_class=endpoint.resource_class,
        ))

    for spec in _FINANCIAL_DATA_TASKS:
        endpoint = SOURCE_REGISTRY.get_endpoint("financial_data", spec["endpoint_key"])
        if endpoint.acquisition_mode.value != "scheduled_pull":
            raise RuntimeError(
                f"financial_data endpoint {spec['endpoint_key']} is not "
                "registered for scheduled pulls"
            )
        tasks.append(AcquisitionTaskBlueprint(
            task_key=spec["task_key"],
            endpoints=(EndpointRef("financial_data", spec["endpoint_key"]),),
            output_datasets=(spec["output_dataset"],),
            cadence=endpoint.cadence,
            resource_class=endpoint.resource_class,
        ))

    for spec in _OFFICIAL_SOURCE_TASKS:
        endpoint = SOURCE_REGISTRY.get_endpoint(spec["source_id"], spec["endpoint_key"])
        if endpoint.acquisition_mode.value != "scheduled_pull":
            raise RuntimeError(
                f"{spec['source_id']} endpoint {spec['endpoint_key']} is not "
                "registered for scheduled pulls"
            )
        tasks.append(AcquisitionTaskBlueprint(
            task_key=spec["task_key"],
            endpoints=(EndpointRef(spec["source_id"], spec["endpoint_key"]),),
            output_datasets=(spec["output_dataset"],),
            cadence=endpoint.cadence,
            resource_class=endpoint.resource_class,
        ))

    result = tuple(sorted(tasks, key=lambda item: item.task_key))
    if len(result) != 200:
        raise RuntimeError(f"V2 acquisition task baseline drifted: {len(result)} != 200")
    return result


def transformation_task_blueprints() -> tuple[TransformationTaskBlueprint, ...]:
    return _DERIVED_TASKS


def task_baseline_summary() -> dict[str, int]:
    acquisition = acquisition_task_blueprints()
    transformation = transformation_task_blueprints()
    return {
        "acquisition": len(acquisition),
        "transformation": len(transformation),
        "total": len(acquisition) + len(transformation),
    }
