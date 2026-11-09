from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from service.research.local_factors.financial import FinancialCrossSection, FinancialFactorEvaluator
from service.research.local_factors.financial_dependencies import financial_dependencies, dependency_inputs, Dependency
from service.research.local_factors.quality import financial_input_diagnostic
from scripts.audit_financial_factor_dependencies import required_periods


def panel():
    rng = np.random.default_rng(523)
    codes = pd.Index(['A','B','C'])
    result = FinancialCrossSection(codes, pd.Series(20.,index=codes), pd.Series(1e8,index=codes))
    keys = set().union(*(d.required | d.optional for d in financial_dependencies().values()))
    for bucket, metric in sorted(keys):
        values = pd.Series(rng.uniform(10,100,3),index=codes)
        if bucket in {'market','special'}:
            setattr(result,metric,values)
        else:
            getattr(result,bucket)[metric] = values
    return result


def test_contract_covers_every_financial_formula_and_actual_missing_propagation():
    p = panel()
    baseline = FinancialFactorEvaluator(p).evaluate_latest()
    assert len(baseline) == len(financial_dependencies()) == 85
    assert all(np.isfinite(v).all() for v in baseline.values())
    keys = set().union(*(d.required for d in financial_dependencies().values()))
    for bucket, metric in sorted(keys):
        changed = deepcopy(p)
        series = getattr(changed,metric) if bucket in {'market','special'} else getattr(changed,bucket)[metric]
        series.loc['A'] = np.nan
        output = FinancialFactorEvaluator(changed).evaluate_latest()
        for name, d in financial_dependencies().items():
            if (bucket, metric) in d.required:
                assert pd.isna(output[name]['A']), (name,bucket,metric)


def test_ttm_margin_diagnostic_uses_actual_formula_not_single_quarter():
    p = panel()
    p.current['revenue'] = pd.Series(np.nan,index=p.securities)
    p.current['oper_cost'] = pd.Series(np.nan,index=p.securities)
    assert 'missing_financial_inputs' not in financial_input_diagnostic('gpm_qoq','A',p)
    p.ttm_previous['oper_cost']['A'] = np.nan
    assert financial_input_diagnostic('gpm_qoq','A',p) == 'missing_financial_inputs:ttm_previous.oper_cost'


def test_cached_diagnostics_equal_scalar_and_do_not_mutate_formula_values():
    p = panel()
    p.ttm['ebitda']['A'] = np.nan
    before = FinancialFactorEvaluator(p).evaluate_latest()
    cached = dependency_inputs(p)
    for name in financial_dependencies():
        assert financial_input_diagnostic(name,'A',p,cached) == financial_input_diagnostic(name,'A',p)
    after = FinancialFactorEvaluator(p).evaluate_latest()
    for name in before: pd.testing.assert_series_equal(before[name],after[name])


def test_optional_zero_fill_is_exposed_not_approved_or_silently_required():
    d = financial_dependencies()['cash_ratio']
    assert ('current','cash') in d.optional
    assert ('current','cash') not in d.required
    assert ('special','dividend_cash_3y') in financial_dependencies()['dividend_yield_3y_avg'].optional
    with pytest.raises(ValueError): Dependency().fillna(1)
    with pytest.raises(ValueError): np.log(Dependency())


def test_exact_period_expansion_and_missing_anchor():
    lineage = dict(current='2026-09-30',previous='2026-06-30',year_ago='2025-09-30',annual='2025-12-31')
    assert required_periods('ttm','revenue',lineage) == ['2026-09-30','2025-12-31','2025-09-30']
    assert required_periods('current','revenue',lineage) == ['2026-09-30','2026-06-30']
    assert required_periods('current','fix_assets',lineage) == ['2026-09-30']
    assert required_periods('annual','revenue',lineage) == ['2025-12-31']
    assert required_periods('current','revenue',{}) == []


def test_every_proven_zero_denominator_is_undefined_in_the_numeric_formula():
    contract = financial_dependencies()
    assert ('current', 'basic_eps') not in contract['eaa'].nonzero_required
    assert ('year_ago', 'basic_eps') in contract['eaa'].nonzero_required
    assert ('year_ago', 'revenue') in contract['sa'].nonzero_required
    base = panel()
    for bucket, metric in sorted(set().union(*(d.nonzero_required for d in contract.values()))):
        p = deepcopy(base)
        values = getattr(p, metric) if bucket in {'market', 'special'} else getattr(p, bucket)[metric]
        values.loc['A'] = 0
        actual = FinancialFactorEvaluator(p).evaluate_latest()
        for name, dep in contract.items():
            if (bucket, metric) in dep.nonzero_required:
                assert pd.isna(actual[name]['A']), (name, bucket, metric)
                assert financial_input_diagnostic(name, 'A', p).startswith('undefined_financial_zero_denominator:')
