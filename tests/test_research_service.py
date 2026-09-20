from datetime import date, timedelta
from decimal import Decimal

from service.research.service import ResearchService


class FakeDataService:
    def __init__(self, datasets):
        self.datasets = datasets

    def query_dataset(self, name, **kwargs):
        rows = list(self.datasets.get(name, []))
        filters = kwargs.get("exact_filters") or {}
        for key, value in filters.items():
            rows = [row for row in rows if row.get(key) == value]
        return {"data": rows[: kwargs["limit"]]}

    def stock_peers(self, *_args, **_kwargs):
        return {"data": [{"ts_code": "000002.SZ", "shared_sector_count": 2}]}

    def list_sectors(self, **_kwargs):
        return {
            "data": [
                {"sector_code": "885001.TI", "name": "人工智能"},
                {"sector_code": "885002.TI", "name": "机器人"},
            ]
        }


class FakeRepository:
    def backfill_statuses(self):
        return {"analyst": {"status": "running", "active": 2}}

    def market_breadth(self, _as_of):
        return {
            "trade_date": date(2026, 9, 18),
            "securities": 100,
            "advancing": 60,
            "declining": 30,
            "unchanged": 10,
            "average_return_pct": Decimal("1.23456"),
            "amount": Decimal("123456.78"),
            "above_ma20": 55,
            "above_ma60": 45,
            "limit_up": 8,
            "limit_down": 2,
        }

    def sector_rotation(self, *_args, **_kwargs):
        return [
            {
                "ts_code": "885001.TI",
                "trade_date": date(2026, 9, 18),
                "period_return_pct": Decimal("8.2"),
            },
            {
                "ts_code": "885002.TI",
                "trade_date": date(2026, 9, 18),
                "period_return_pct": Decimal("-3.1"),
            },
        ]


def _daily_rows(ts_code, count=300, start=date(2025, 7, 1), base=10):
    rows = []
    price = float(base)
    for index in range(count):
        observed = start + timedelta(days=index)
        previous = price
        price *= 1.001
        rows.append(
            {
                "ts_code": ts_code,
                "trade_date": observed,
                "open": previous,
                "high": price * 1.01,
                "low": previous * 0.99,
                "close": price,
                "pre_close": previous,
                "pct_chg": (price / previous - 1) * 100,
                "vol": 1000 + index,
                "amount": 10000 + index,
            }
        )
    return list(reversed(rows))


def test_fundamentals_derives_growth_quality_and_dupont():
    datasets = {
        "stock_basic": [{"ts_code": "000001.SZ", "name": "平安银行"}],
        "financial_indicator": [
            {
                "ts_code": "000001.SZ", "end_date": date(2025, 12, 31),
                "ann_date": date(2026, 3, 20), "netprofit_margin": 10,
                "grossprofit_margin": 30, "roe": 12, "roa": 2, "roic": 8,
                "assets_turn": 0.8, "current_ratio": 1.5,
            },
            {
                "ts_code": "000001.SZ", "end_date": date(2024, 12, 31),
                "ann_date": date(2025, 3, 20), "netprofit_margin": 9,
                "grossprofit_margin": 28, "roe": 11, "assets_turn": 0.75,
            },
        ],
        "income": [
            {"ts_code": "000001.SZ", "end_date": date(2025, 12, 31), "ann_date": date(2026, 3, 20), "revenue": 120, "n_income_attr_p": 12},
            {"ts_code": "000001.SZ", "end_date": date(2024, 12, 31), "ann_date": date(2025, 3, 20), "revenue": 100, "n_income_attr_p": 10},
        ],
        "balancesheet": [
            {"ts_code": "000001.SZ", "end_date": date(2025, 12, 31), "ann_date": date(2026, 3, 20), "total_assets": 200, "total_hldr_eqy_inc_min_int": 100},
        ],
        "cashflow": [
            {"ts_code": "000001.SZ", "end_date": date(2025, 12, 31), "ann_date": date(2026, 3, 20), "n_cashflow_act": 15, "c_fr_sale_sg": 110},
            {"ts_code": "000001.SZ", "end_date": date(2024, 12, 31), "ann_date": date(2025, 3, 20), "n_cashflow_act": 10},
        ],
        "fina_mainbz": [
            {"ts_code": "000001.SZ", "end_date": date(2025, 12, 31), "bz_item": "零售", "bz_sales": 80},
            {"ts_code": "000001.SZ", "end_date": date(2025, 12, 31), "bz_item": "对公", "bz_sales": 20},
        ],
    }
    result = ResearchService(FakeDataService(datasets), FakeRepository()).fundamentals(
        "000001.SZ", periods=8, as_of=date(2026, 9, 18)
    )
    latest = result["data"]["latest"]
    assert latest["growth"]["revenue_yoy_pct"] == 20.0
    assert latest["quality"]["operating_cash_to_net_income"] == 1.25
    assert latest["dupont"]["derived_roe_pct"] == 16.0
    assert result["data"]["segments"]["items"][0]["sales_share_pct"] == 80.0


def test_technicals_uses_long_daily_history_instead_of_shallow_factor_table():
    stock = _daily_rows("000001.SZ")
    benchmark = _daily_rows("399006.SZ", base=20)
    factors = [
        {"ts_code": "000001.SZ", "trade_date": row["trade_date"], "adj_factor": 1.0}
        for row in stock
    ]
    datasets = {
        "stock_basic": [{"ts_code": "000001.SZ"}],
        "stock_daily": stock + benchmark,
        "index_daily": benchmark,
        "adj_factor": factors,
    }
    result = ResearchService(FakeDataService(datasets), FakeRepository()).technicals(
        "000001.SZ", as_of=date(2026, 9, 18)
    )
    assert result["meta"]["quality"]["status"] == "ready"
    assert result["data"]["trend"]["moving_averages"]["250"] is not None
    assert result["data"]["momentum"]["rsi_14"] > 50
    assert result["data"]["relative_strength"]["excess_return_60d_pct"] == 0.0


def test_market_and_sector_derivations_are_evidence_carrying():
    service = ResearchService(FakeDataService({}), FakeRepository())
    breadth = service.market_breadth(as_of=date(2026, 9, 19))
    rotation = service.sector_rotation("ths", as_of=date(2026, 9, 19))
    assert breadth["data"]["advance_decline_ratio"] == 2.0
    assert breadth["data"]["above_ma20_share_pct"] == 55.0
    assert breadth["data"]["average_return_pct"] == 1.2346
    assert isinstance(breadth["data"]["amount"], float)
    assert rotation["data"]["leaders"][0]["name"] == "人工智能"
    assert rotation["meta"]["provider"] == "ths"
    assert rotation["meta"]["effective_date"] == date(2026, 9, 18)
    assert rotation["meta"]["quality"]["status"] == "ready"


def test_capability_catalog_separates_derived_backfill_and_new_sources():
    catalog = ResearchService(FakeDataService({}), FakeRepository()).capabilities()
    assert catalog["api_namespace"]["path"] == "/api/v1/research"
    assert catalog["summary"]["agent_endpoints"] == 9
    assert catalog["summary"]["derived_endpoints"] == 7
    assert catalog["summary"]["backfill_workstreams"] == 6
    assert catalog["summary"]["new_source_todos"] == 3
    assert catalog["summary"]["baseline_techniques"] == 35
    assert catalog["summary"]["currently_served"] == 27
    assert catalog["summary"]["planned_from_existing_sources"] == 3
    assert catalog["summary"]["external_or_constrained"] == 5
    assert len(catalog["techniques"]["served"]) == 27
    assert len(catalog["techniques"]["gaps"]) == 8
    analyst = next(item for item in catalog["backfills"] if item["group"] == "analyst")
    assert analyst["status"] == "running"
    assert analyst["active"] == 2
