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
