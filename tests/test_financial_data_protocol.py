from __future__ import annotations

import pytest

from service.source_connectors.financial_data import FinancialDataProtocolError
from service.source_connectors.financial_data_protocol import tabular_rows


ROUTE = "/api/v1/stock_fnd/consensus-stats"


def _response(*, fields, data):
    return {
        "status": "SUCCESS",
        "results": [
            {
                "url": ROUTE,
                "meta": {"fields": fields},
                "data": data,
            }
        ],
    }


def test_tabular_rows_accepts_provider_empty_result_shape():
    assert tabular_rows(_response(fields=[], data=[]), route=ROUTE) == []


def test_tabular_rows_rejects_rows_without_a_field_contract():
    with pytest.raises(FinancialDataProtocolError, match="fields are invalid"):
        tabular_rows(_response(fields=[], data=[["300750.SZ"]]), route=ROUTE)


def test_quota_exhaustion_is_not_transient_rate_limit(monkeypatch):
    import requests
    from service.source_connectors.financial_data import FinancialDataConnector, FinancialDataQuotaExceeded
    from service.acquisition_runtime.reliability import classify_failure
    response = requests.Response()
    response.status_code = 429
    response._content = b'{"issues":[{"code":"QUOTA_EXCEEDED","hint":"secret-echo"}]}'
    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: response)
    with pytest.raises(FinancialDataQuotaExceeded) as error:
        FinancialDataConnector(api_key='test-key')._send({})
    assert classify_failure(error.value) == 'quota'
    assert 'secret-echo' not in str(error.value)


def test_unknown_429_remains_rate_limited(monkeypatch):
    import requests
    from service.source_connectors.financial_data import FinancialDataConnector
    from service.acquisition_runtime.reliability import classify_failure
    response = requests.Response()
    response.status_code = 429
    response._content = b'not-json'
    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: response)
    with pytest.raises(requests.HTTPError) as error:
        FinancialDataConnector(api_key='test-key')._send({})
    assert classify_failure(error.value) == 'rate_limited'
