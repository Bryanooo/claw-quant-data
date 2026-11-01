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
    monkeypatch.setattr(materializer, '_statement_rows', lambda conn, table, cols, day: records.copy() if table == 'income' else pd.DataFrame())
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
