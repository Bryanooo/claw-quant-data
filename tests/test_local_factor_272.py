from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from service.orchestration_v2.catalog import transformation_task_blueprints
from service.orchestration_v2.transformations import SUPPORTED_TRANSFORMATION_TASK_KEYS
from service.research.local_factors.alpha101 import Alpha101Evaluator, Alpha101Panel
from service.research.local_factors.catalog import (
    FACTOR_BY_NAME,
    FACTOR_COUNT,
    FACTOR_SCHEMA_VERSION,
    FACTOR_SPECS,
    FAMILY_NAMES,
)
from service.research.local_factors.financial import (
    FinancialCrossSection,
    FinancialFactorEvaluator,
)
from service.research.local_factors.materializer import _snapshot_rows
from service.research.local_factors.market import (
    MarketFactorEvaluator,
    MarketFactorPanel,
    _rolling_regression,
)
from service.research.local_factors.storage import estimate_ten_year_storage
from service.research.local_factors.service import (
    factor_catalog_payload,
    normalize_factor_names,
)


def _market_panel(days: int = 1400, securities: int = 8) -> MarketFactorPanel:
    random = np.random.default_rng(4)
    dates = pd.bdate_range("2020-01-01", periods=days)
    codes = pd.Index([f"{value:06d}.SZ" for value in range(securities)])
    close = pd.DataFrame(
        np.cumprod(1 + random.normal(0, 0.01, (days, securities)), axis=0) * 20,
        index=dates, columns=codes,
    )
    opening = close * (1 + random.normal(0, 0.003, close.shape))
    high = np.maximum(opening, close) * (1 + random.random(close.shape) * 0.01)
    low = np.minimum(opening, close) * (1 - random.random(close.shape) * 0.01)
    volume = pd.DataFrame(
        random.lognormal(12, 1, close.shape), index=dates, columns=codes
    )
    amount = volume * (opening + close) / 20
    total_mv = close * 1e6
    turnover = pd.DataFrame(random.random(close.shape) * 4, index=dates, columns=codes)
    groups = pd.Series([f"g{i // 2}" for i in range(securities)], index=codes)
    benchmark300 = pd.Series(
        np.cumprod(1 + random.normal(0, 0.008, days)) * 4000, index=dates
    )
    benchmark1 = pd.Series(
        np.cumprod(1 + random.normal(0, 0.009, days)) * 3000, index=dates
    )
    benchmark_volume = pd.Series(random.lognormal(15, 1, days), index=dates)
    return MarketFactorPanel(
        Alpha101Panel(opening, high, low, close, volume, amount, total_mv, groups),
        turnover, total_mv, total_mv * 0.8, benchmark300, benchmark1,
        benchmark_volume, benchmark_volume * 1.1,
    )


def test_vectorized_rolling_regression_matches_pairwise_complete_formula():
    index = pd.bdate_range("2026-01-01", periods=40)
    benchmark = pd.Series(np.linspace(-0.03, 0.04, 40), index=index)
    stocks = pd.DataFrame({
        "complete_a": benchmark * 1.7 + 0.002,
        "complete_b": benchmark * -0.4 + np.sin(np.arange(40)) / 100,
        "incomplete": benchmark * 0.8,
    }, index=index)
    stocks.loc[index[-3], "incomplete"] = np.nan

    alpha, beta, sigma = _rolling_regression(stocks, benchmark, 30)
    selected_market = benchmark.tail(30)
    for column in ("complete_a", "complete_b"):
        selected = stocks[column].tail(30)
        expected_beta = selected.cov(selected_market) / selected_market.var(ddof=1)
        expected_alpha = selected.mean() - expected_beta * selected_market.mean()
        expected_sigma = (
            selected - selected_market * expected_beta - expected_alpha
        ).std(ddof=1)
        assert beta[column] == pytest.approx(expected_beta)
        assert alpha[column] == pytest.approx(expected_alpha)
        assert sigma[column] == pytest.approx(expected_sigma)
    assert pd.isna(alpha["incomplete"])
    assert pd.isna(beta["incomplete"])
    assert pd.isna(sigma["incomplete"])


def _financial_panel(codes: pd.Index) -> FinancialCrossSection:
    series = lambda value: pd.Series(
        np.linspace(value, value * 1.2, len(codes)), index=codes
    )
    metrics = {
        name: series(index + 1)
        for index, name in enumerate((
            "net_profit_parent", "total_share", "net_profit",
            "operating_cashflow", "revenue", "oper_cost", "total_assets",
            "equity_parent", "equity", "basic_eps", "operate_profit",
            "total_profit", "income_tax", "ebit", "fin_exp",
            "total_cur_assets", "total_cur_liab", "inventories", "cash",
            "trad_asset", "total_liab", "total_ncl", "operating_cash_inflow",
            "investing_cash_inflow", "sell_exp", "admin_exp", "adv_receipts",
            "prepayment", "defer_tax_assets", "fix_assets", "accounts_receiv",
            "longterm_receivable", "staff_paid", "biz_tax_surchg",
            "investing_cashflow", "financing_cashflow",
            "investing_cash_outflow", "ebitda", "profit_dedt", "market_cap",
        ))
    }
    return FinancialCrossSection(
        codes, series(20), series(1e8),
        current=metrics.copy(), previous=metrics.copy(), year_ago=metrics.copy(),
        previous_year_ago=metrics.copy(), ttm=metrics.copy(),
        ttm_previous=metrics.copy(), ttm_year_ago=metrics.copy(),
        annual=metrics.copy(), annual_year_ago=metrics.copy(),
        annual_five_year_ago=metrics.copy(), five_year_mean=metrics.copy(),
        dividend_cash_3y=series(1),
    )


def test_catalog_is_position_stable_and_contains_declared_families():
    assert FACTOR_COUNT == 272
    assert len(FACTOR_BY_NAME) == 272
    assert [item.position for item in FACTOR_SPECS] == list(range(1, 273))
    assert sum(map(len, FAMILY_NAMES.values())) == 171
    assert len([item for item in FACTOR_SPECS if item.family == "Alpha101"]) == 101
    assert FACTOR_BY_NAME["rsi"].overlap_kind == "exact_value"


def test_all_alpha101_formulas_execute_on_one_shared_panel():
    panel = _market_panel(days=320, securities=5).alpha101
    evaluator = Alpha101Evaluator(panel)
    for number in range(1, 102):
        result = evaluator.evaluate(number)
        assert result.shape == panel.close.shape


def test_alpha_adv_uses_the_volume_primitive_not_cash_amount():
    panel = _market_panel(days=30, securities=3).alpha101
    expected = panel.volume.rolling(20, min_periods=20).mean()
    pd.testing.assert_frame_equal(panel.adv(20), expected)


def test_vectorized_alpha_rolling_operators_match_reference_semantics():
    frame = pd.DataFrame({
        "a": [1.0, 3.0, 2.0, 2.0, 5.0],
        "b": [2.0, np.nan, 1.0, 4.0, 3.0],
    })
    window = 3
    reference_rank = frame.rolling(window, min_periods=window).apply(
        lambda values: float(pd.Series(values).rank(pct=True).iloc[-1]),
        raw=True,
    )
    reference_decay = frame.rolling(window, min_periods=window).apply(
        lambda values: float(np.dot(values, np.array([1, 2, 3]) / 6)),
        raw=True,
    )
    reference_product = frame.rolling(window, min_periods=window).apply(
        np.prod, raw=True,
    )
    reference_max = frame.rolling(window, min_periods=window).apply(
        lambda values: float(np.argmax(values) + 1), raw=True,
    )
    reference_min = frame.rolling(window, min_periods=window).apply(
        lambda values: float(np.argmin(values) + 1), raw=True,
    )

    pd.testing.assert_frame_equal(
        Alpha101Evaluator.ts_rank(frame, window), reference_rank
    )
    pd.testing.assert_frame_equal(
        Alpha101Evaluator.decay_linear(frame, window), reference_decay
    )
    pd.testing.assert_frame_equal(
        Alpha101Evaluator.ts_product(frame, window), reference_product
    )
    pd.testing.assert_frame_equal(
        Alpha101Evaluator.ts_argmax(frame, window), reference_max
    )
    pd.testing.assert_frame_equal(
        Alpha101Evaluator.ts_argmin(frame, window), reference_min
    )


def test_alpha_correlation_treats_complete_constant_window_as_zero():
    constant = pd.DataFrame({"a": [1.0, 1.0, 1.0, 1.0]})
    changing = pd.DataFrame({"a": [2.0, 3.0, 4.0, 5.0]})

    result = Alpha101Evaluator.correlation(constant, changing, 3)

    assert result.iloc[:2].isna().all().all()
    assert result.iloc[2:, 0].tolist() == [0.0, 0.0]


def test_market_and_financial_producers_cover_all_272_without_overlap():
    market_panel = _market_panel()
    market = MarketFactorEvaluator(market_panel).evaluate_latest()
    financial = FinancialFactorEvaluator(
        _financial_panel(market_panel.alpha101.close.columns)
    ).evaluate_latest()
    assert len(market) == 187
    assert len(financial) == 85
    assert not set(market).intersection(financial)
    assert set(market) | set(financial) == set(FACTOR_BY_NAME)


def test_snapshot_rows_have_fixed_array_and_explicit_availability_mask():
    codes = pd.Index(["000001.SZ", "000002.SZ"])
    values = {
        item.name: pd.Series([float(item.position), np.nan], index=codes)
        for item in FACTOR_SPECS
    }
    rows = _snapshot_rows(
        pd.Timestamp("2026-10-22").date(), codes, values,
        source_execution_id=7, input_revision_digest="a" * 64,
    )
    assert len(rows[0][3]) == 272
    assert rows[0][4] == "1" * 272
    assert rows[0][5] == 272
    assert rows[0][7] == "ready"
    assert rows[1][4] == "0" * 272
    assert rows[1][5] == 0
    assert rows[1][7] == "missing_input"


def test_local_factor_task_is_dependency_scheduled_v2_transformation():
    task = {
        item.task_key: item for item in transformation_task_blueprints()
    }["local_factor_snapshot"]
    assert task.task_key in SUPPORTED_TRANSFORMATION_TASK_KEYS
    assert task.output_datasets == ("local_factor_snapshot", "technical_factor_snapshot")
    assert "technical_factor_snapshot" not in task.dependency_task_keys
    assert "technical_factor_snapshot" not in SUPPORTED_TRANSFORMATION_TASK_KEYS
    assert task.implementation_version == "unified-features-pit-v6"


def test_ten_year_capacity_uses_15m_rows_not_four_billion_rows():
    estimate = estimate_ten_year_storage()
    assert estimate.rows == 15_120_000
    assert estimate.long_form_rows == 4_112_640_000
    assert estimate.validation_rows == 685_440
    assert 40 < estimate.planned_low_gib < estimate.planned_high_gib < 70


def test_local_factor_catalog_and_query_names_keep_stable_positions():
    catalog = factor_catalog_payload(family="Size")

    assert catalog["schema_version"] == FACTOR_SCHEMA_VERSION
    assert [item["name"] for item in catalog["factors"]] == [
        "float_size", "nl_size", "size",
    ]
    assert normalize_factor_names(["size", "size", "rsi"]) == ("size", "rsi")
    with pytest.raises(ValueError, match="unknown local factors"):
        normalize_factor_names(["not_a_factor"])


def test_rolling_comovement_preserves_small_changes_on_large_levels():
    from service.research.local_factors.alpha101 import Alpha101Evaluator
    signal = np.array([0., 1., 3., 2., 4., 1., 2., 4., 3.])
    x = pd.DataFrame({'A': 1e12 + signal, 'B': 1e9 - signal})
    y = pd.DataFrame({'A': 1e12 - signal, 'B': 1e9 + signal})
    y.loc[0, 'B'] = np.nan
    corr = Alpha101Evaluator.correlation(x, y, 5)
    cov = Alpha101Evaluator.covariance(x, y, 5)
    for end in range(4, len(signal)):
        for name in x:
            if name == 'B' and end == 4:
                assert pd.isna(corr.loc[end, name]) and pd.isna(cov.loc[end, name])
            else:
                assert np.isclose(corr.loc[end, name], -1)
                assert np.isclose(cov.loc[end, name], -np.var(signal[end-4:end+1], ddof=1))


def test_unknown_group_and_identity_powers_do_not_publish_values():
    from service.research.local_factors.alpha101 import Alpha101Evaluator
    p = _market_panel(days=10, securities=3).alpha101
    e = Alpha101Evaluator(p)
    values = pd.Series([1.,2.,3.], index=p.close.columns)
    labels = pd.Series(['known',None,'__unknown__'], index=p.close.columns)
    assert e._neutralize_one_date(values, labels).isna().tolist() == [False,True,True]
    assert e.finite_power(1., np.nan).isna().all().all()
    assert e.finite_power(np.nan, 0.).isna().all().all()
    assert e.finite_power(3., 0.).eq(1).all().all()
