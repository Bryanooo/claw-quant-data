from collections import Counter
from datetime import date
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from collectors.stock.finance.balancesheet import BalancesheetCollector
from service.research.local_factors.materializer import (
    _BALANCE_COLUMNS,
    _fill_documented_suspension_sessions,
    _single_quarter,
    frame_digest,
)
from service.research.local_factors.quality import audit_security
from service.research.local_factors.catalog import FACTOR_SPECS
from service.research.local_factors.ownership import TECHNICAL_FEATURES
from service.research.local_factors.financial import FinancialFactorEvaluator
from service.research.local_factors.market import MarketFactorEvaluator
from service.research import technical_indicators as ti
from service.orchestration_v2.transformations import build_technical_factor_snapshot_row
from test_local_factor_272 import _market_panel, _financial_panel
from test_technical_factor_transformation import _bars


def test_financial_diagnostics_name_missing_bucket_and_metric():
    from service.research.local_factors.quality import financial_input_diagnostic
    market = _market_panel(days=100, securities=1)
    codes = market.alpha101.close.columns
    panel = _financial_panel(codes)
    panel.ttm['ebitda'] = pd.Series(np.nan, index=codes)
    assert financial_input_diagnostic('ebitda_to_market', codes[0], panel) == 'missing_financial_inputs:ttm.ebitda'
    panel.ttm['ebitda'] = pd.Series(0., index=codes)
    assert financial_input_diagnostic('ebitda_to_market', codes[0], panel).startswith('financial_zero_input_requires_domain_audit:')


@pytest.mark.parametrize('factor,bucket,metric', [
    ('lra_yoy', 'year_ago', 'longterm_receivable'),
    ('delta_inventory_turnover', 'ttm_year_ago', 'oper_cost'),
    ('delta_inventory_turnover', 'current', 'inventories'),
])
def test_financial_diagnostics_identify_comparable_period_inputs(factor, bucket, metric):
    from service.research.local_factors.quality import financial_input_diagnostic
    codes = _market_panel(days=100, securities=1).alpha101.close.columns
    panel = _financial_panel(codes)
    getattr(panel, bucket)[metric] = pd.Series(np.nan, index=codes)
    reason = financial_input_diagnostic(factor, codes[0], panel)
    assert reason.startswith('missing_financial_inputs:')
    assert f'{bucket}.{metric}' in reason


def test_alpha_domain_exclusion_rejects_a_hole_inside_recent_window():
    market = _market_panel(days=600, securities=1)
    code = market.alpha101.close.columns[0]
    values = {spec.name: pd.Series(1., index=[code]) for spec in FACTOR_SPECS}
    values['alpha101_53'].loc[code] = np.nan
    market.alpha101.close.iloc[-5, 0] = np.nan
    technical = {name: 1. for name in TECHNICAL_FEATURES}
    technical['adjustment_status'] = 'applied'
    result = audit_security(code, values, technical, market)
    assert 'alpha101_53' in result['unresolved']
    assert 'alpha101_53' not in result['excluded']


@pytest.mark.parametrize('gaps,expected_exclusion', [(0, True), (1, False), (None, False)])
def test_technical_warmup_uses_traded_bars_only_with_complete_suspension_proof(gaps, expected_exclusion):
    market = _market_panel(days=123, securities=1)
    code = market.alpha101.close.columns[0]
    market.listing_dates = pd.Series('20200101', index=[code])
    market.unexplained_market_gaps = None if gaps is None else pd.Series(gaps, index=[code])
    values = {spec.name: pd.Series(1., index=[code]) for spec in FACTOR_SPECS}
    technical = {name: 1. for name in TECHNICAL_FEATURES}
    technical.update(adjustment_status='applied', source_bar_count=120, roc_120=None)
    result = audit_security(code, values, technical, market)
    assert ('roc_120' in result['excluded']) is expected_exclusion
    assert ('roc_120' in result['unresolved']) is not expected_exclusion


def test_finance_collector_and_loader_agree_on_longterm_receivables():
    assert 'lt_rec' in BalancesheetCollector.CORE_FIELDS
    assert _BALANCE_COLUMNS['lt_rec'] == 'longterm_receivable'


def test_quarter_conversion_rejects_missing_or_nonadjacent_prior():
    q3 = pd.Series({'end_date':pd.Timestamp('2026-09-30'),'revenue':900.})
    q1 = pd.Series({'end_date':pd.Timestamp('2026-03-31'),'revenue':100.})
    q2 = pd.Series({'end_date':pd.Timestamp('2026-06-30'),'revenue':500.})
    assert np.isnan(_single_quarter(q3,None,'revenue'))
    assert np.isnan(_single_quarter(q3,q1,'revenue'))
    assert _single_quarter(q3,q2,'revenue') == 400
    assert _single_quarter(q1,None,'revenue') == 100


def test_same_count_source_revision_changes_fingerprint():
    a = pd.DataFrame({'close':[10.,20.], 'day':['20260101','20260102']})
    b = a.copy(); b.loc[1,'close'] = 21.
    assert frame_digest(a) != frame_digest(b)
    assert frame_digest(a) == frame_digest(a.copy())


def test_investing_inflow_identity_is_same_statement_and_conservative():
    from service.research.local_factors.materializer import _derive_investing_inflow
    frame = pd.DataFrame({
        'ts_code': list('abcdef'), 'end_date': ['2026-06-30']*6,
        'investing_cash_inflow': [np.nan, np.nan, 7., np.nan, np.nan, np.nan],
        'investing_cash_outflow': [100., 100., 100., np.nan, 10., np.inf],
        'investing_cashflow': [-100., -60., -100., 4., -20., 0.],
    })
    before = frame_digest(frame)
    result, proof = _derive_investing_inflow(frame)
    assert result.investing_cash_inflow.iloc[:3].tolist() == [0., 40., 7.]
    assert result.investing_cash_inflow.iloc[3:].isna().all()
    assert proof['rows'] == 2
    assert frame_digest(frame) == before
    assert len(proof['examples']) == 2


@pytest.mark.parametrize('name,needed', [
    ('bias_turn_21d_504d', 505), ('bias_std_turn_42d_252d', 253),
    ('return_63d', 64),
])
def test_all_window_lengths_are_parsed(name, needed):
    from service.research.local_factors.quality import required_bars
    assert required_bars(name) == needed


@pytest.mark.parametrize('days,excluded', [(193, True), (600, False)])
def test_dual_window_warmup_requires_listing_proof(days, excluded):
    market = _market_panel(days=days, securities=1)
    code = market.alpha101.close.columns[0]
    market.listing_dates = pd.Series(market.alpha101.close.index[0].strftime('%Y%m%d'), index=[code])
    values = {s.name: pd.Series(1., index=[code]) for s in FACTOR_SPECS}
    values['bias_turn_21d_504d'].iloc[0] = np.nan
    technical = {name: 1. for name in TECHNICAL_FEATURES}
    technical['adjustment_status'] = 'applied'
    result = audit_security(code, values, technical, market)
    assert ('bias_turn_21d_504d' in result['excluded']) is excluded
    assert ('bias_turn_21d_504d' in result['unresolved']) is not excluded


def test_only_documented_suspensions_are_filled_for_rolling_factors():
    dates = pd.bdate_range("2026-01-01", periods=3)
    codes = pd.Index(["000001.SZ", "000002.SZ"])
    close = pd.DataFrame(
        [[10.0, 20.0], [np.nan, np.nan], [11.0, 21.0]],
        index=dates,
        columns=codes,
    )
    matrices = {
        name: close.copy()
        for name in ("open", "high", "low", "close", "total_mv", "circ_mv")
    }
    for name in ("vol", "amount", "turnover_rate"):
        matrices[name] = close.copy()
    amount = close.copy() * 1000
    suspensions = pd.DataFrame({
        "trade_date": [dates[1]],
        "ts_code": ["000001.SZ"],
    })
    listing = pd.Series(["20200101", "20200101"], index=codes)

    amount, unexplained, filled = _fill_documented_suspension_sessions(
        matrices, amount, suspensions, listing
    )

    assert filled == 1
    assert matrices["close"].loc[dates[1], "000001.SZ"] == 10.0
    assert matrices["vol"].loc[dates[1], "000001.SZ"] == 0.0
    assert amount.loc[dates[1], "000001.SZ"] == 0.0
    assert np.isnan(matrices["close"].loc[dates[1], "000002.SZ"])
    assert unexplained.to_dict() == {"000001.SZ": 0, "000002.SZ": 1}


def test_ema_and_sma_close_primitives_are_shared_between_packs():
    bars = _bars(260); closes = [x['close'] for x in bars]
    calls = Counter()
    original = ti._ema_series
    def traced(values,window):
        if values == closes: calls[window] += 1
        return original(values,window)
    with patch.object(ti,'_ema_series',traced):
        build_technical_factor_snapshot_row('000001.SZ',date(2026,10,21),bars)
    assert all(calls[w] == 1 for w in (12,20,26,50,200))


def test_unexplained_missing_feature_cannot_be_certified_by_other_values():
    p = _market_panel(days=100,securities=1); code = p.alpha101.close.columns[0]
    vals = {s.name:pd.Series([1.],index=[code]) for s in FACTOR_SPECS}
    tech = {n:1. for n in TECHNICAL_FEATURES}; tech['adjustment_status']='applied'
    vals['lra_yoy'].loc[code] = np.nan
    result = audit_security(code,vals,tech,p)
    assert result['status'] == 'partial'
    assert 'lra_yoy' in result['unresolved']
    vals['lra_yoy'].loc[code] = 1.
    assert audit_security(code,vals,tech,p)['status'] == 'ready'


def test_proven_new_listing_short_history_is_excluded_not_filled():
    p = _market_panel(days=100,securities=1); code=p.alpha101.close.columns[0]
    p.listing_dates=pd.Series([p.alpha101.close.index[0].strftime('%Y%m%d')],index=[code])
    vals={s.name:pd.Series([1.],index=[code]) for s in FACTOR_SPECS}
    vals['beta_1320d_000001'].loc[code]=np.nan
    tech={n:1. for n in TECHNICAL_FEATURES}; tech['adjustment_status']='applied'
    result=audit_security(code,vals,tech,p)
    assert result['status']=='ready'
    assert result['excluded']['beta_1320d_000001']=='insufficient_listing_history'
    p.listing_dates=pd.Series(['19900101'],index=[code])
    assert audit_security(code,vals,tech,p)['status']=='partial'


def test_technical_warmup_and_zero_range_are_explained_not_false_failures():
    p = _market_panel(days=260, securities=1)
    code = p.alpha101.close.columns[0]
    p.listing_dates = pd.Series([
        p.alpha101.close.index[-171].strftime('%Y%m%d')
    ], index=[code])
    vals = {s.name: pd.Series([1.], index=[code]) for s in FACTOR_SPECS}
    tech = {name: 1. for name in TECHNICAL_FEATURES}
    tech['adjustment_status'] = 'applied'
    tech['ema_200_distance_pct'] = None

    result = audit_security(code, vals, tech, p)
    assert result['technical_status'] == 'ready'
    assert result['excluded']['ema_200_distance_pct'] == (
        'insufficient_listing_history'
    )

    # A one-price candle makes ratios over H-L mathematically undefined.  It
    # is a domain exclusion with direct OHLC evidence, not missing data.
    p.alpha101.high.loc[p.alpha101.high.index[-1], code] = 10.0
    p.alpha101.low.loc[p.alpha101.low.index[-1], code] = 10.0
    tech['body_to_range'] = None
    zero_range = audit_security(code, vals, tech, p)
    assert zero_range['technical_status'] == 'ready'
    assert zero_range['excluded']['body_to_range'] == (
        'undefined_for_zero_price_range'
    )


def test_lag63_never_falls_back_to_previous_report():
    p=_financial_panel(pd.Index(['000001.SZ']))
    assert np.isnan(FinancialFactorEvaluator(p).evaluate_latest()['roe_ttm_lag63d'].iloc[0])
    p.roe_ttm_lag63d=pd.Series([.123],index=p.securities)
    assert FinancialFactorEvaluator(p).evaluate_latest()['roe_ttm_lag63d'].iloc[0]==.123


def test_absent_longterm_receivable_is_excluded_only_with_comparable_statements():
    market = _market_panel(days=600, securities=1)
    code = market.alpha101.close.columns[0]
    financial = _financial_panel(pd.Index([code]))
    values = {s.name: pd.Series([1.], index=[code]) for s in FACTOR_SPECS}
    values['lra_yoy'].loc[code] = np.nan
    tech = {n: 1. for n in TECHNICAL_FEATURES}; tech['adjustment_status'] = 'applied'
    financial.current['longterm_receivable'] = pd.Series([np.nan], index=[code])
    financial.year_ago['longterm_receivable'] = pd.Series([np.nan], index=[code])

    result = audit_security(code, values, tech, market, financial)
    assert result['status'] == 'ready'
    assert result['excluded']['lra_yoy'] == (
        'line_item_not_reported_in_comparable_statements'
    )

    financial.year_ago['total_assets'] = pd.Series([np.nan], index=[code])
    result = audit_security(code, values, tech, market, financial)
    assert result['status'] == 'partial'
    assert result['unresolved']['lra_yoy'] == (
        'missing_financial_inputs:current.longterm_receivable,year_ago.longterm_receivable'
    )


def test_alpha101_domain_null_is_excluded_only_with_complete_market_window():
    market = _market_panel(days=600, securities=1)
    code = market.alpha101.close.columns[0]
    values = {s.name: pd.Series([1.], index=[code]) for s in FACTOR_SPECS}
    values['alpha101_53'].loc[code] = np.nan
    tech = {n: 1. for n in TECHNICAL_FEATURES}; tech['adjustment_status'] = 'applied'
    result = audit_security(code, values, tech, market)
    assert result['status'] == 'ready'
    assert result['excluded']['alpha101_53'] == (
        'undefined_formula_domain_with_complete_market_window'
    )

    market.alpha101.close.loc[market.alpha101.close.index[:100], code] = np.nan
    result = audit_security(code, values, tech, market)
    assert result['status'] == 'partial'
    assert result['unresolved']['alpha101_53'] == (
        'missing_input_or_undefined_requires_audit'
    )


def test_numerically_unstable_extreme_value_is_not_certified():
    market = _market_panel(days=100, securities=1)
    code = market.alpha101.close.columns[0]
    values = {s.name: pd.Series([1.], index=[code]) for s in FACTOR_SPECS}
    values['lra_yoy'].loc[code] = 1e200
    tech = {n: 1. for n in TECHNICAL_FEATURES}; tech['adjustment_status'] = 'applied'
    result = audit_security(code, values, tech, market)
    assert result['status'] == 'ready'
    assert result['excluded']['lra_yoy'] == (
        'numerically_unstable_extreme_value'
    )


def test_turnover_uses_actual_cny_not_adjusted_vwap_amount():
    p=_market_panel(days=350,securities=1)
    p.traded_amount_cny=p.alpha101.amount * 1000
    original=MarketFactorEvaluator(p)._turnover_factors()['amount_ma_20d']
    p.alpha101.amount *= .5
    pd.testing.assert_series_equal(original,MarketFactorEvaluator(p)._turnover_factors()['amount_ma_20d'])
