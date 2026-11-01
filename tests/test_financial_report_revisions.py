import pandas as pd

from collectors.stock.finance.base import _select_latest_reports
from collectors.stock.finance.balancesheet import BalancesheetCollector


def test_fixed_asset_components_are_collected_without_overwriting_original():
    assert {'fix_assets', 'fix_assets_total', 'fixed_assets_disp'} <= set(BalancesheetCollector.CORE_FIELDS)
    row = pd.DataFrame([dict(ts_code='A', end_date='20260930', report_type='1',
                            fix_assets=None, fix_assets_total=93036801.17,
                            fixed_assets_disp=None)])
    result = _select_latest_reports(row, BalancesheetCollector.PK_COLUMNS)
    assert result.iloc[0].fix_assets is None
    assert result.iloc[0].fix_assets_total == 93036801.17


def test_same_revision_rich_row_is_not_lost_to_page_order():
    rows = [dict(ts_code='A', end_date='20260930', report_type='1',
                 ann_date='20261024', ebit=123, ebitda=None),
            dict(ts_code='A', end_date='20260930', report_type='1',
                 ann_date='20261024', ebit=None, ebitda=None)]
    for ordered in (rows, rows[::-1]):
        result = _select_latest_reports(pd.DataFrame(ordered), ['ts_code', 'end_date', 'report_type'])
        assert len(result) == 1
        assert result.iloc[0].ebit == 123
        assert list(result.columns) == list(pd.DataFrame(rows).columns)


def test_newer_sparse_revision_does_not_inherit_old_values():
    rows = [dict(ts_code='A', end_date='20260930', ann_date='20261024',
                 f_ann_date='20261026', value=None),
            dict(ts_code='A', end_date='20260930', ann_date='20261024',
                 f_ann_date='20261024', value=123)]
    result = _select_latest_reports(pd.DataFrame(rows), ['ts_code', 'end_date'])
    assert result.iloc[0].f_ann_date == '20261026'
    assert pd.isna(result.iloc[0].value)
