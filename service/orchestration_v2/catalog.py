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
        ("canonical_period_bars",),
        ("technical_factor_snapshot",),
        ("canonical_period_bars",),
        80,
    ),
    TransformationTaskBlueprint(
        "valuation_percentile_snapshot",
        ("stock_daily_basic", "index_member_all"),
        ("valuation_percentile_snapshot",),
        ("daily_basic", "index_member_all"),
        80,
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

    result = tuple(sorted(tasks, key=lambda item: item.task_key))
    if len(result) != 191:
        raise RuntimeError(f"V2 acquisition task baseline drifted: {len(result)} != 191")
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
