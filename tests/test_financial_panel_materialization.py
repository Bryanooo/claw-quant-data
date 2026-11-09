from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from service.research.local_factors import materializer


def test_financial_panel_preserves_ttm_alignment_and_missing_values(monkeypatch):
    records = pd.DataFrame([
        dict(ts_code='A', end_date=date(2025, 6, 30), ann_date=date(2025, 8, 1), revenue=200.),
        dict(ts_code='A', end_date=date(2025, 12, 31), ann_date=date(2026, 4, 1), revenue=500.),
        dict(ts_code='A', end_date=date(2026, 6, 30), ann_date=date(2026, 8, 1), revenue=300.),
    ])
    monkeypatch.setattr(materializer, '_statement_rows', lambda conn, table, cols, day, **kw: records.copy() if table == 'income' else pd.DataFrame())
    monkeypatch.setattr(materializer, '_read_frame', lambda *args: pd.DataFrame())
    codes = pd.Index(['MISSING', 'A'])
    market = SimpleNamespace(
        alpha101=SimpleNamespace(close=pd.DataFrame([[20., 30.]], columns=codes)),
        total_mv=pd.DataFrame([[100., 200.]], columns=codes),
    )
    panel, evidence = materializer._load_financial_panel(None, date(2026, 10, 29), codes, market, include_lag=False)
    assert list(panel.values('ttm', 'revenue').index) == list(codes)
    assert panel.values('ttm', 'revenue')['A'] == pytest.approx(600.)
    assert pd.isna(panel.values('ttm', 'revenue')['MISSING'])
    assert pd.isna(panel.values('current', 'revenue')['A'])  # Q1 missing
    assert panel.total_mv['A'] == 2_000_000.
    assert evidence['statement_securities'] == 1


def test_preindexed_ttm_is_identical_to_reference_path():
    rows = pd.DataFrame({'end_date': pd.to_datetime(['2025-06-30', '2025-12-31', '2026-06-30']),
                         'revenue': [200., 500., 300.]})
    assert materializer._ttm_value(rows, 2, 'revenue', indexed=rows.set_index('end_date')) == materializer._ttm_value(rows, 2, 'revenue') == 600.


def test_ttm_preserves_statement_type_across_all_three_periods():
    rows = pd.DataFrame({
        'end_date': pd.to_datetime(['2025-06-30', '2025-12-31', '2026-06-30']),
        'income_report_type': [1, 4, 1], 'revenue': [200., 500., 300.],
    })
    assert pd.isna(materializer._ttm_value(rows, 2, 'revenue'))


def test_five_year_mean_requires_consecutive_complete_reports():
    records = pd.DataFrame({'end_date':pd.to_datetime(['2021-12-31','2022-12-31','2023-12-31','2024-12-31','2025-12-31']),
                            'net_profit':[1.,2.,3.,4.,5.]})
    target = pd.Timestamp('2025-12-31')
    assert materializer._complete_annual_mean(records,target,['net_profit'])['net_profit'] == 3
    assert pd.isna(materializer._complete_annual_mean(records.iloc[1:],target,['net_profit'])['net_profit'])
    records.loc[2,'net_profit'] = float('nan')
    assert pd.isna(materializer._complete_annual_mean(records,target,['net_profit'])['net_profit'])
    records.loc[2,'net_profit'] = 3
    records.loc[2,'end_date'] = pd.Timestamp('2020-12-31')
    assert pd.isna(materializer._complete_annual_mean(records,target,['net_profit'])['net_profit'])


def test_market_mean_uses_exact_calendar_window_without_skipna_or_extra_days():
    dates = list(pd.date_range('2026-10-28',periods=3))
    codes = pd.Index(['A','B'])
    values = pd.DataFrame([[999.,999.],[10.,20.],[20.,float('nan')]],index=dates,columns=codes)
    result = materializer._complete_market_mean(values,dates[1:],codes)
    assert result['A'] == 150_000
    assert pd.isna(result['B'])
    assert pd.isna(materializer._complete_market_mean(values.iloc[-1:],dates[1:],codes)['A'])
