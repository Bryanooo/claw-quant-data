from types import SimpleNamespace
import pandas as pd
import pytest
from scripts import probe_factor_financial_fields as probe


def row(value=None, period='20260930'):
    return {'ts_code':'000001.SZ','end_date':period,'fix_assets':value}


def test_probe_preserves_explicit_null_and_requires_terminal_page(monkeypatch):
    pages = iter([pd.DataFrame([row()]), pd.DataFrame([])])
    monkeypatch.setattr(probe,'CatalogRawCollector',lambda _:SimpleNamespace(pro=SimpleNamespace(query=lambda *a,**kw:next(pages))))
    result = probe.probe('balancesheet','fix_assets','20260930',page_size=1)
    assert result['pagination_exhausted'] and result['pages'] == 2
    assert result['nonnull_rows'] == 0 and result['records'][0]['fix_assets'] is None


def test_probe_rejects_repeated_page(monkeypatch):
    monkeypatch.setattr(probe,'CatalogRawCollector',lambda _:SimpleNamespace(pro=SimpleNamespace(query=lambda *a,**kw:pd.DataFrame([row()]))))
    with pytest.raises(ValueError,match='repeated'):
        probe.probe('balancesheet','fix_assets','20260930',page_size=1)


def test_probe_rejects_wrong_period(monkeypatch):
    monkeypatch.setattr(probe,'CatalogRawCollector',lambda _:SimpleNamespace(pro=SimpleNamespace(query=lambda *a,**kw:pd.DataFrame([row(period='20260630')]))))
    with pytest.raises(ValueError,match='different report period'):
        probe.probe('balancesheet','fix_assets','20260930')
