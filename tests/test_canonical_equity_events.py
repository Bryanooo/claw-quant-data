from datetime import date

import pytest

from service.api.schemas import (
    CanonicalEquityBusinessSegmentsResponse,
    CanonicalEquityDividendsResponse,
    CanonicalEquityFinancialMetricsResponse,
    CanonicalEquityHolderCountsResponse,
    CanonicalEquityPerformanceUpdatesResponse,
    CanonicalEquityRepurchasesResponse,
    CanonicalEquityTtmFinancialsResponse,
)
from service.data_service.canonical_equity_events import CanonicalEquityEventService
from service.source_connectors.contracts import AcquisitionMode, ConnectorResult


class FakeEventDataService:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.calls = []

    def query_dataset(self, name, **kwargs):
        self.calls.append((name, kwargs))
        symbol = kwargs["exact_filters"]["ts_code"]
        values = list(self.rows.get((name, symbol), []))
        end_date = kwargs["exact_filters"].get("end_date")
        if end_date:
            values = [
                row for row in values
                if str(row.get("end_date"))[:10].replace("-", "")
                == end_date.replace("-", "")
            ]
        return {"data": values}


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


def test_performance_updates_use_local_forecast_units_and_provider_preliminary():
    forecast = {
        "ts_code": "300750.SZ", "end_date": date(2024, 12, 31),
        "ann_date": date(2025, 1, 21), "type": "略增",
        "p_change_min": 11.06, "p_change_max": 20.12,
        "net_profit_min": 4_900_000, "net_profit_max": 5_300_000,
        "summary": "预计净利润增长", "change_reason": "产品竞争力增强",
    }
    prelim_fields = [
        "symbol", "report_period", "disclosure_date",
        "prel_operating_revenue", "prel_npoc", "prel_cfo_net",
        "prel_basic_eps", "prel_roe_diluted",
    ]
    broker = QueueBroker(_provider_response(
        "/api/v1/stock_fnd/prelim-acc",
        prelim_fields,
        [[
            "300750.SZ", "2024-12-31", "2025-02-01",
            300_000_000_000, 50_000_000_000, 60_000_000_000, 11.0, 25.0,
        ]],
    ))
    data = FakeEventDataService({("forecast", "300750.SZ"): [forecast]})

    result = CanonicalEquityEventService(data, broker).performance_updates(
        symbols=["300750.SZ"], report_dates=[date(2024, 12, 31)]
    )

    assert len(broker.calls) == 1
    assert broker.calls[0].parameters["requests"][0]["url"].endswith("prelim-acc")
    by_type = {row["update_type"]: row for row in result["data"]}
    assert by_type["forecast"]["parent_net_profit_lower"] == 49_000_000_000
    assert by_type["forecast"]["forecast_direction"] == "positive"
    assert by_type["forecast"]["source_id"] == "tushare"
    assert by_type["preliminary"]["reported_revenue"] == 300_000_000_000
    assert by_type["preliminary"]["source_id"] == "financial_data"
    assert result["meta"]["unresolved"] == []
    CanonicalEquityPerformanceUpdatesResponse.model_validate(result)


def test_dividend_fallback_derives_per_share_cash_from_total_and_equity_base():
    fields = [
        "symbol", "dividend_end_date", "dividend_scheme_type",
        "dividend_proposal_publish_date", "dividend_record_date",
        "ex_rights_div_date", "dividend_equity_base",
        "total_cash_dividend_cny", "dividend_scheme",
    ]
    broker = QueueBroker(_provider_response(
        "/api/v1/stock_fnd/dividend-details",
        fields,
        [[
            "600519.SH", "2025-12-31", "公司提出方案", "2026-04-17",
            "2026-06-25", "2026-06-26", 1_250_081_601,
            35_032_574_305.19, "每10股派280.2423元",
        ]],
    ))

    result = CanonicalEquityEventService(
        FakeEventDataService(), broker
    ).dividends(
        symbols=["600519.SH"], report_dates=[date(2025, 12, 31)]
    )

    row = result["data"][0]
    assert row["cash_per_share_before_tax"] == pytest.approx(28.02423)
    assert row["total_cash_dividend"] == pytest.approx(35_032_574_305.19)
    assert row["source_id"] == "financial_data"
    CanonicalEquityDividendsResponse.model_validate(result)


def test_financial_metrics_keep_local_values_and_units():
    local = {
        "ts_code": "300750.SZ", "end_date": date(2026, 6, 30),
        "ann_date": date(2026, 7, 25), "report_type": 1,
        "eps": 9.69, "dt_eps": 9.69, "bps": 87.15, "ocfps": 13.03,
        "revenue_ps": 59.86, "roe": 11.65, "roe_waa": 11.71,
        "roe_dt": 10.72, "roa": 4.22, "roic": 5.1,
        "grossprofit_margin": 25.32, "netprofit_margin": 16.98,
        "current_ratio": 1.83, "quick_ratio": 1.54,
        "debt_to_assets": 63.65, "ebit_to_interest": 22.5,
        "ar_turn": 3.4, "inv_turn": 2.3, "assets_turn": 0.26,
        "salescash_to_or": 1.02,
    }
    broker = QueueBroker()
    data = FakeEventDataService({("financial_indicator", "300750.SZ"): [local]})
    result = CanonicalEquityEventService(data, broker).financial_metrics(
        symbols=["300750.SZ"], report_dates=[date(2026, 6, 30)]
    )

    assert broker.calls == []
    _, query = data.calls[0]
    assert query["exact_filters"] == {"ts_code": "300750.SZ"}
    assert query["start_date"] == "2026-06-30"
    assert query["end_date"] == "2026-06-30"
    row = result["data"][0]
    assert row["roe_weighted_pct"] == pytest.approx(11.71)
    assert row["debt_to_assets_pct"] == pytest.approx(63.65)
    assert row["source_id"] == "tushare"
    CanonicalEquityFinancialMetricsResponse.model_validate(result)


def test_ttm_financials_are_derived_from_auditable_cumulative_periods():
    income_rows = [
        {
            "ts_code": "300750.SZ", "end_date": date(2025, 6, 30),
            "ann_date": date(2025, 7, 30), "report_type": "1",
            "total_revenue": 200, "revenue": 200, "n_income_attr_p": 30,
        },
        {
            "ts_code": "300750.SZ", "end_date": date(2025, 12, 31),
            "ann_date": date(2026, 3, 10), "report_type": "1",
            "total_revenue": 400, "revenue": 400, "n_income_attr_p": 70,
        },
        {
            "ts_code": "300750.SZ", "end_date": date(2026, 6, 30),
            "ann_date": date(2026, 7, 25), "report_type": "1",
            "total_revenue": 250, "revenue": 250, "n_income_attr_p": 50,
        },
    ]
    cash_rows = [
        {
            "ts_code": "300750.SZ", "end_date": date(2025, 6, 30),
            "ann_date": date(2025, 7, 30), "report_type": "1",
            "n_cashflow_act": 40, "c_pay_acq_const_fiolta": 10,
        },
        {
            "ts_code": "300750.SZ", "end_date": date(2025, 12, 31),
            "ann_date": date(2026, 3, 10), "report_type": "1",
            "n_cashflow_act": 80, "c_pay_acq_const_fiolta": 20,
        },
        {
            "ts_code": "300750.SZ", "end_date": date(2026, 6, 30),
            "ann_date": date(2026, 7, 25), "report_type": "1",
            "n_cashflow_act": 60, "c_pay_acq_const_fiolta": 15,
        },
    ]
    data = FakeEventDataService({
        ("income", "300750.SZ"): income_rows,
        ("cashflow", "300750.SZ"): cash_rows,
    })
    broker = QueueBroker()

    result = CanonicalEquityEventService(data, broker).ttm_financials(
        symbols=["300750.SZ"], report_dates=[date(2026, 6, 30)]
    )

    assert broker.calls == []
    row = result["data"][0]
    assert row["revenue_ttm"] == 450
    assert row["parent_net_profit_ttm"] == 90
    assert row["operating_cash_flow_ttm"] == 100
    assert row["capital_expenditure_ttm"] == 25
    assert row["free_cash_flow_ttm"] == 75
    assert row["calculation"] == "prior_annual+current_ytd-prior_ytd"
    CanonicalEquityTtmFinancialsResponse.model_validate(result)


def test_repurchase_uses_local_progress_without_spending_quota():
    local = {
        "ts_code": "300750.SZ", "ann_date": date(2026, 9, 29),
        "end_date": date(2026, 9, 29), "proc": "实施", "vol": 10_945_162,
        "amount": 3_303_155_138.38, "high_limit": 287.27,
        "low_limit": 286.53,
    }
    broker = QueueBroker()
    result = CanonicalEquityEventService(
        FakeEventDataService({("repurchase", "300750.SZ"): [local]}), broker
    ).repurchases(
        symbols=["300750.SZ"], start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
    )

    assert broker.calls == []
    assert result["data"][0]["current_shares"] == 10_945_162
    assert result["data"][0]["source_id"] == "tushare"
    CanonicalEquityRepurchasesResponse.model_validate(result)


def test_holder_count_fallback_preserves_ratio_as_percentage_points():
    fields = [
        "symbol", "end_date", "total_shareholder_number",
        "shareholder_number_change", "shareholder_number_change_ratio",
        "avg_hold_shares", "avg_hold_mv", "a_share_shareholder_number",
    ]
    broker = QueueBroker(_provider_response(
        "/api/v1/stock_fnd/holder-count",
        fields,
        [[
            "300750.SZ", "2024-02-29", 260_219, -773, -0.296177660618,
            16_905.15, 2_764_161.0816, 260_219,
        ]],
    ))

    result = CanonicalEquityEventService(
        FakeEventDataService(), broker
    ).holder_counts(
        symbols=["300750.SZ"], start_date=date(2024, 2, 1),
        end_date=date(2024, 2, 29),
    )

    row = result["data"][0]
    assert row["shareholder_change_pct"] == pytest.approx(-0.296177660618)
    assert row["publication_date"] is None
    assert row["source_id"] == "financial_data"
    CanonicalEquityHolderCountsResponse.model_validate(result)


def test_business_segments_use_local_product_and_industry_without_quota():
    report_date = date(2026, 6, 30)
    rows = [
        {
            "ts_code": "300750.SZ", "end_date": report_date,
            "bz_code": "P", "bz_item": "产品", "bz_sales": 400,
            "bz_cost": 300, "bz_profit": 100,
        },
        {
            "ts_code": "300750.SZ", "end_date": report_date,
            "bz_code": "P", "bz_item": "动力电池", "bz_sales": 300,
            "bz_cost": 210, "bz_profit": 90,
        },
        {
            "ts_code": "300750.SZ", "end_date": report_date,
            "bz_code": "I", "bz_item": "行业", "bz_sales": 400,
            "bz_cost": 300, "bz_profit": 100,
        },
        {
            "ts_code": "300750.SZ", "end_date": report_date,
            "bz_code": "I", "bz_item": "电气机械", "bz_sales": 400,
            "bz_cost": 300, "bz_profit": 100,
        },
    ]
    broker = QueueBroker()
    result = CanonicalEquityEventService(
        FakeEventDataService({("fina_mainbz", "300750.SZ"): rows}), broker
    ).business_segments(
        symbols=["300750.SZ"], report_dates=[report_date],
        classifications=["product", "industry"],
    )

    assert broker.calls == []
    detail = next(row for row in result["data"] if row["segment_name"] == "动力电池")
    assert detail["classification"] == "product"
    assert detail["revenue_share_pct"] == pytest.approx(75.0)
    assert detail["gross_margin_pct"] == pytest.approx(30.0)
    assert result["meta"]["unresolved"] == []
    CanonicalEquityBusinessSegmentsResponse.model_validate(result)


def test_business_segments_fallback_normalizes_explicit_region_period():
    fields = [
        "symbol", "report_period", "information_source",
        "main_classification", "segment_name", "main_oper_income",
        "main_oper_cost", "main_oper_profit", "main_gross_margin",
        "main_oper_income_ratio", "main_oper_income_yoy",
    ]
    route = "/api/v1/stock_fnd/main-business-region"
    broker = QueueBroker(_provider_response(route, fields, [[
        "300750.SZ", "2026-06-30", "2026年半年报", "地区", "境外",
        180_000_000_000, 130_000_000_000, 50_000_000_000,
        27.7778, 45.0, 12.5,
    ]]))

    result = CanonicalEquityEventService(
        FakeEventDataService(), broker
    ).business_segments(
        symbols=["300750.SZ"], report_dates=[date(2026, 6, 30)],
        classifications=["region"],
    )

    row = result["data"][0]
    assert row["classification"] == "region"
    assert row["revenue"] == 180_000_000_000
    assert row["revenue_share_pct"] == pytest.approx(45.0)
    assert row["source_id"] == "financial_data"
    assert result["meta"]["fallback_routes"] == [route]
    CanonicalEquityBusinessSegmentsResponse.model_validate(result)


def test_business_segments_reject_unknown_classification():
    with pytest.raises(Exception, match="classifications must use"):
        CanonicalEquityEventService(
            FakeEventDataService(), QueueBroker()
        ).business_segments(
            symbols=["300750.SZ"], report_dates=[date(2026, 6, 30)],
            classifications=["theme"],
        )
