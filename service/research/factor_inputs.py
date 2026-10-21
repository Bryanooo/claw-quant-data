"""Versioned data-delivery contracts intended for claw-factor-lab.

These contracts enumerate reproducible observations.  They do not define
labels, cross-sectional transforms, factor direction or backtest semantics.
"""

from __future__ import annotations

from typing import Any

from service.data_service.registry import DATASETS


FACTOR_INPUT_BUNDLES: tuple[dict[str, Any], ...] = (
    {
        "id": "core_daily@v1",
        "required": True,
        "description": "Daily bars, adjustment, tradability, calendar and benchmark evidence.",
        "datasets": (
            "stock_daily", "adj_factor", "stock_limit", "stock_suspend",
            "stock_basic", "stock_company", "bse_mapping", "namechange",
            "stock_st", "trade_calendar", "index_daily", "index_weight",
            "fama_french_daily", "stock_daily_basic",
        ),
        "point_in_time": False,
        "dataset_policies": {
            "index_weight": {
                "required": False,
                "absence_semantics": "historical_constituent_history_not_guaranteed",
            },
            "fama_french_daily": {
                "required": False,
                "absence_semantics": "forward_materialization_not_historical",
            },
            "stock_company": {
                "required": False,
                "absence_semantics": "reference_attribute_unavailable",
            },
            "bse_mapping": {
                "required": False,
                "absence_semantics": "not_a_bse_instrument",
            },
            "namechange": {
                "required": False,
                "absence_semantics": "no_observed_event_not_proven_absent",
            },
            "stock_st": {
                "required": False,
                "absence_semantics": "not_in_observed_st_membership",
            },
            "stock_daily_basic": {
                "required": False,
                "absence_semantics": "missing_input",
                "coverage_mode": "stock_daily_sessions",
            },
        },
    },
    {
        "id": "valuation_daily@v1",
        "required": False,
        "description": "Daily valuation, turnover, share-count and market-cap observations.",
        "datasets": ("stock_daily_basic",),
        "point_in_time": False,
        "dataset_policies": {
            "stock_daily_basic": {
                "required": True,
                "absence_semantics": "missing_input",
                "coverage_mode": "stock_daily_sessions",
            },
        },
    },
    {
        "id": "fundamentals_pit@v1",
        "required": False,
        "description": "Statements and disclosures bounded by announcement availability.",
        "datasets": (
            "income", "balancesheet", "cashflow", "financial_indicator",
            "forecast", "express",
        ),
        "point_in_time": True,
        "dataset_policies": {
            "forecast": {"required": False, "absence_semantics": "no_observed_event_not_proven_absent"},
            "express": {"required": False, "absence_semantics": "no_observed_event_not_proven_absent"},
        },
        "excluded": {
            "disclosure_date": (
                "no governed historical availability column; later schedule "
                "revisions would leak into an as-of snapshot"
            ),
        },
    },
    {
        "id": "flow_sentiment@v1",
        "required": False,
        "description": "Money flow, financing, northbound, block-trade and chip observations.",
        "datasets": (
            "moneyflow", "margin", "margin_detail", "margin_secs", "hk_hold",
            "stock_hsgt", "hsgt_top10", "ggt_top10", "block_trade",
            "top_list", "top_inst", "cyq_chips", "cyq_perf", "stk_factor",
            "stk_factor_pro", "factor_value", "fama_french_daily",
            "technical_factor_snapshot",
        ),
        "point_in_time": False,
        "dataset_policies": {
            "moneyflow": {
                "required": True,
                "absence_semantics": "missing_input",
                "coverage_mode": "stock_daily_sessions",
            },
            "margin_detail": {"required": False, "absence_semantics": "not_eligible_or_missing"},
            "hk_hold": {"required": False, "absence_semantics": "not_eligible_or_missing"},
            "block_trade": {"required": False, "absence_semantics": "no_observed_event_not_proven_absent"},
            "cyq_perf": {
                "required": True,
                "absence_semantics": "missing_input",
                "coverage_mode": "stock_daily_sessions",
            },
        },
    },
    {
        "id": "technical_descriptors@v1",
        "required": False,
        "description": "Deterministic technical descriptions without predictive evaluation.",
        "datasets": (
            "stk_factor", "stk_factor_pro", "technical_factor_snapshot",
        ),
        "point_in_time": False,
        "dataset_policies": {
            "stk_factor": {
                "required": True,
                "absence_semantics": "missing_input",
                "coverage_mode": "stock_daily_sessions",
            },
            "stk_factor_pro": {
                "required": True,
                "absence_semantics": "missing_input",
                "coverage_mode": "stock_daily_sessions",
            },
            "technical_factor_snapshot": {"required": False, "absence_semantics": "forward_materialization_not_historical"},
        },
    },
    {
        "id": "fundamentals_reference@v1",
        "required": False,
        "description": (
            "Financial audit, segment, disclosure-schedule and analyst-report "
            "observations; consumers must honor each dataset's availability field."
        ),
        "datasets": (
            "fina_audit", "fina_mainbz", "disclosure_date", "report_rc",
        ),
        "point_in_time": False,
    },
    {
        "id": "corporate_events@v1",
        "required": False,
        "description": (
            "Corporate actions, ownership, pledges and management events. "
            "Absence of an event row is not proof that no event occurred."
        ),
        "datasets": (
            "dividend", "repurchase", "share_float", "new_share",
            "pledge_detail", "pledge_stat", "top10_holders",
            "top10_floatholders", "stk_holdernumber", "stk_holdertrade",
            "stk_managers", "stk_rewards",
        ),
        "point_in_time": False,
    },
    {
        "id": "company_news@v1",
        "required": False,
        "description": (
            "Financial news, broker recommendations and security-linked analyst "
            "reports. Consumers must perform explicit entity binding for news text."
        ),
        "datasets": (
            "major_news", "broker_recommend", "report_rc",
        ),
        "point_in_time": False,
        "dataset_policies": {
            "major_news": {
                "required": False,
                "absence_semantics": "no_observed_article_not_proven_absent",
            },
            "broker_recommend": {
                "required": False,
                "absence_semantics": "no_observed_recommendation_not_proven_absent",
            },
            "report_rc": {
                "required": False,
                "absence_semantics": "no_observed_report_not_proven_absent",
            },
        },
    },
    {
        "id": "etf_market@v1",
        "required": False,
        "description": (
            "ETF identity, bars, adjustment, shares, constituents, NAV, "
            "portfolio and distribution observations."
        ),
        "datasets": (
            "fund_basic", "etf_basic", "etf_index", "fund_daily", "fund_adj",
            "etf_share_size", "etf_sh_cons", "etf_sz_cons", "fund_company",
            "fund_manager", "fund_nav", "fund_share", "fund_portfolio",
            "fund_div", "fund_factor_pro", "mkt_idx_bmk",
        ),
        "point_in_time": False,
    },
    {
        "id": "index_industry@v1",
        "required": False,
        "description": (
            "Broad index and industry identities, memberships, weights, bars, "
            "announcements and market summaries."
        ),
        "datasets": (
            "index_basic", "index_daily", "index_classify", "index_member_all",
            "ci_index_member", "index_weight", "sw_daily", "ci_daily",
            "industry_daily", "ths_index", "idx_factor_pro", "idx_anns",
            "daily_info",
        ),
        "point_in_time": False,
    },
    {
        "id": "macro@v1",
        "required": False,
        "description": (
            "China growth, inflation, money, rates, calendars and global yield "
            "observations for regime and risk features."
        ),
        "datasets": (
            "cn_gdp", "cn_cpi", "cn_pmi", "cn_ppi", "cn_m", "sf_month",
            "cn_lpr", "shibor", "shibor_quote", "libor", "hibor", "gz_index",
            "wz_index", "us_tbr", "us_tltr", "us_trltr", "us_trycr", "us_tycr",
            "repo_daily", "eco_cal", "cn_schedule",
        ),
        "point_in_time": False,
    },
)


def factor_input_catalog() -> dict[str, Any]:
    bundles: list[dict[str, Any]] = []
    for definition in FACTOR_INPUT_BUNDLES:
        datasets = []
        for name in definition["datasets"]:
            spec = DATASETS.get(name)
            datasets.append({
                "name": name,
                "date_column": spec.date_column,
                "availability_column": spec.availability_column,
                "source_ids": list(spec.source_ids),
                "storage_semantics": spec.storage_semantics,
            })
        policies = definition.get("dataset_policies", {})
        normalized_policies = {
            item["name"]: {
                "required": policies.get(item["name"], {}).get("required", True),
                "absence_semantics": policies.get(item["name"], {}).get(
                    "absence_semantics", "missing_input"
                ),
                "coverage_mode": policies.get(item["name"], {}).get(
                    "coverage_mode", "presence"
                ),
            }
            for item in datasets
        }
        bundles.append({
            **definition,
            "datasets": datasets,
            "dataset_policies": normalized_policies,
        })
    return {
        "contract": "claw-factor-inputs@v1",
        "boundary": {
            "claw_data": "stored observations and deterministic descriptions",
            "factor_lab": "factors, labels, transforms, tests, models and backtests",
        },
        "delivery": {
            "read_api": "/api/v1/data/datasets/{dataset}/records",
            "snapshot_required": True,
            "atomic_database_snapshot": False,
            "availability_cutoff_required": True,
        },
        "bundles": bundles,
    }

