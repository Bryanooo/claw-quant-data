from datetime import date

import pytest

from service.api.schemas import CanonicalEquityFinancialPeriodsResponse
from service.data_service.canonical_equity import CanonicalEquityDataService
from service.data_service.models import InvalidQueryError
from service.source_connectors.contracts import AcquisitionMode, ConnectorResult


class FakeFinancialDataService:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.calls = []

    def query_dataset(self, name, **kwargs):
        self.calls.append((name, kwargs))
        symbol = kwargs["exact_filters"]["ts_code"]
        return {"data": self.rows.get((name, symbol), [])}


class QueueBroker:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def query(self, request):
        self.calls.append(request)
        return ConnectorResult(
            source_id="financial_data",
            endpoint_key="common_query",
            acquisition_mode=AcquisitionMode.QUERY_THROUGH,
            records=(self.responses.pop(0),),
            fetched_rows=1,
            status="complete",
        )


def _provider_response(route, fields, rows):
    return {
        "status": "SUCCESS",
        "results": [{"url": route, "meta": {"fields": fields}, "data": rows}],
    }


def test_financial_periods_use_local_sections_and_select_latest_disclosure():
    old_income = {
        "ts_code": "300750.SZ", "end_date": "20260630",
        "ann_date": "20260724", "f_ann_date": "20260724",
        "report_type": "2", "update_flag": "0", "revenue": 1,
    }
    current_income = {
        "ts_code": "300750.SZ", "end_date": "20260630",
        "ann_date": "20260725", "f_ann_date": "20260725",
        "report_type": "1", "update_flag": "1",
        "total_revenue": 276_916_580_000, "revenue": 276_916_580_000,
        "operate_profit": 55_664_757_000, "total_profit": 55_766_857_000,
        "n_income": 47_030_638_000, "n_income_attr_p": 43_284_002_000,
    }
    cashflow = {
        "ts_code": "300750.SZ", "end_date": date(2026, 6, 30),
        "ann_date": date(2026, 7, 25), "report_type": "1",
        "n_cashflow_act": 60_216_851_000,
        "n_cashflow_inv_act": -36_929_091_000,
        "n_cash_flows_fnc_act": 24_310_261_000,
        "c_pay_acq_const_fiolta": 25_072_772_000,
    }
    balance = {
        "ts_code": "300750.SZ", "end_date": date(2026, 6, 30),
        "ann_date": date(2026, 7, 25), "report_type": "1",
        "total_assets": 1_138_880_789_000,
        "total_liab": 724_925_558_000,
        "total_hldr_eqy_inc_min_int": 413_955_232_000,
        "money_cap": 372_053_275_000,
        "inventories": 130_819_205_000,
        "accounts_receiv": 88_417_984_000,
        "acct_payable": 202_508_781_000,
    }
    data = FakeFinancialDataService({
        ("income", "300750.SZ"): [old_income, current_income],
        ("cashflow", "300750.SZ"): [cashflow],
        ("balancesheet", "300750.SZ"): [balance],
    })
    broker = QueueBroker()

    result = CanonicalEquityDataService(data, broker).financial_periods(
        symbols=["300750.SZ"],
        report_dates=[date(2026, 6, 30)],
    )

    assert broker.calls == []
    row = result["data"][0]
    assert row["disclosure_date"] == date(2026, 7, 25)
    assert row["income"]["revenue"] == 276_916_580_000
    assert row["cash_flow"]["operating_cash_flow"] == 60_216_851_000
    assert row["balance_sheet"]["total_equity"] == 413_955_232_000
    assert row["source_sections"]["income"]["source_id"] == "tushare"
    assert result["meta"]["unresolved"] == []
    CanonicalEquityFinancialPeriodsResponse.model_validate(result)


def test_financial_periods_fill_only_missing_sections_from_provider():
    local_income = {
        "ts_code": "300750.SZ", "end_date": "20260630",
        "ann_date": "20260725", "report_type": "1",
        "total_revenue": 10, "revenue": 11, "operate_profit": 12,
        "total_profit": 13, "n_income": 14, "n_income_attr_p": 15,
    }
    income_cash_fields = [
        "symbol", "report_period", "disclosure_date",
        "total_operating_revenue", "operating_revenue", "operating_profit",
        "total_profit", "net_profit", "npoc", "cfo_net", "cfi_net",
        "cff_net", "cash_pay_acq_const_fiolta",
    ]
    balance_fields = [
        "symbol", "report_period", "disclosure_date", "total_liab",
        "total_assets", "monetary_capital", "total_equity",
        "acct_payable", "acct_receivable", "inventories",
    ]
    broker = QueueBroker(
        _provider_response(
            "/api/v1/stock_fnd/income-cashflow-acc",
            income_cash_fields,
            [[
                "300750.SZ", "2026-06-30 00:00:00", "2026-07-25",
                999, 999, 999, 999, 999, 999, 60, -36, 24, 25,
            ]],
        ),
        _provider_response(
            "/api/v1/stock_fnd/balance-sheet",
            balance_fields,
            [[
                "300750.SZ", "2026-06-30 00:00:00", "2026-07-25",
                724, 1138, 372, 413, 202, 88, 130,
            ]],
        ),
    )
    data = FakeFinancialDataService({
        ("income", "300750.SZ"): [local_income],
    })

    result = CanonicalEquityDataService(data, broker).financial_periods(
        symbols=["300750.SZ"],
        report_dates=[date(2026, 6, 30)],
    )

    row = result["data"][0]
    assert row["income"]["revenue"] == 11
    assert row["source_sections"]["income"]["source_id"] == "tushare"
    assert row["cash_flow"]["operating_cash_flow"] == 60
    assert row["source_sections"]["cash_flow"]["source_id"] == "financial_data"
    assert row["balance_sheet"]["total_assets"] == 1138
    assert result["meta"]["fallback_used"] is True
    assert result["meta"]["unresolved"] == []
    assert result["meta"]["coverage"]["300750.SZ"] == {
        "requested_periods": 1,
        "local_income_periods": 1,
        "local_cash_flow_periods": 0,
        "local_balance_sheet_periods": 0,
        "fallback_income_periods": 0,
        "fallback_cash_flow_periods": 1,
        "fallback_balance_sheet_periods": 1,
    }


def test_financial_periods_report_unresolved_without_quota_and_validate_periods():
    service = CanonicalEquityDataService(FakeFinancialDataService(), QueueBroker())

    result = service.financial_periods(
        symbols=["300750.SZ"],
        report_dates=[date(2026, 6, 30)],
        allow_quota_fallback=False,
    )
    assert result["data"] == []
    assert result["meta"]["fallback_used"] is False
    assert result["meta"]["unresolved"][0]["missing_sections"] == [
        "income", "cash_flow", "balance_sheet"
    ]

    with pytest.raises(InvalidQueryError, match="quarter ends"):
        service.financial_periods(
            symbols=["300750.SZ"],
            report_dates=[date(2026, 7, 1)],
        )
