from datetime import date, timedelta
from decimal import Decimal

import pytest

from service.research.service import (
    ResearchService,
    _adjust_ohlcv,
    _chan_analysis,
    _fibonacci_retracement,
    _pivot_systems,
    _zigzag,
)


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
    assert result["data"]["momentum"]["kdj"]["k"] is not None
    assert result["data"]["trend_strength"]["adx_14"] is not None
    assert result["data"]["trend"]["bull_bear_boundary"]["value"] is not None
    assert result["data"]["trend"]["weighted_trend"]["bull_line"] is not None
    assert result["data"]["levels"]["classic_pivots"]["pivot"] is not None
    assert set(result["data"]["levels"]["pivot_systems"]) == {
        "classic", "fibonacci", "woodie", "camarilla", "demark", "cpr"
    }
    assert result["data"]["timeframes"]["1w"]["observations"] > 40
    assert result["data"]["timeframes"]["1mo"]["observations"] >= 10
    assert result["data"]["timeframes"]["1mo"]["observation"]["period_complete"] is False
    assert (
        result["data"]["timeframes"]["1mo"]["chan_analysis"]["source_bar_count"]
        == result["data"]["timeframes"]["1mo"]["observations"] - 1
    )
    assert result["data"]["long_horizon"]["calendar_year_returns"]
    assert result["data"]["wave_analysis"]["status"] == "candidate_only"
    assert result["data"]["chan_analysis"]["variant"].startswith("deterministic")
    assert result["data"]["trend"]["systems"]["ichimoku"]["state"] != "unavailable"
    assert result["data"]["trend"]["systems"]["supertrend_10_3"]["status"] == "ready"
    assert result["data"]["trend"]["systems"]["aroon_25"]["status"] == "ready"
    assert result["data"]["trend"]["systems"]["parabolic_sar"]["status"] == "ready"
    assert result["data"]["momentum"]["stochastic_rsi_14"] is not None
    assert result["data"]["volume_price"]["chaikin_money_flow_20"] is not None
    assert result["data"]["volatility"]["downside_risk"]["status"] == "ready"
    assert result["data"]["levels"]["gaps"]["status"] == "ready"
    assert len(result["data"]["chart"]["points"]) == 120
    assert result["data"]["chart"]["price_basis"] == "latest-factor-adjusted"
    assert result["data"]["total_return"]["status"] == "ready"
    assert result["data"]["relative_strength"]["excess_return_60d_pct"] == 0.0
    assert result["data"]["relative_strength"]["risk_metrics"]["windows"]["60"]["status"] == "ready"


def test_stock_relative_risk_is_suppressed_without_adjustment_factors():
    stock = _daily_rows("000001.SZ")
    benchmark = _daily_rows("399006.SZ", base=20)
    result = ResearchService(
        FakeDataService({
            "stock_basic": [{"ts_code": "000001.SZ"}],
            "stock_daily": stock,
            "index_daily": benchmark,
        }),
        FakeRepository(),
    ).technicals("000001.SZ", as_of=date(2026, 9, 18))

    relative = result["data"]["relative_strength"]
    assert result["meta"]["price_adjustment"]["status"] == "missing"
    assert result["meta"]["quality"]["status"] == "warning"
    assert relative["status"] == "unavailable_unadjusted"
    assert relative["excess_return_60d_pct"] is None
    assert relative["risk_metrics"]["windows"] == {}
    assert result["data"]["total_return"]["status"] == "unavailable_unadjusted"
    assert result["data"]["total_return"]["adjusted_return_pct"] is None
    assert result["data"]["chart"]["price_basis"] == "raw"


def test_common_pivot_families_have_auditable_prior_bar_basis():
    systems = _pivot_systems({
        "trade_date": date(2026, 9, 18),
        "open": 100, "high": 110, "low": 90, "close": 105,
    })

    assert systems["classic"]["pivot"] == pytest.approx(101.6667)
    assert systems["fibonacci"]["resistance_2"] == pytest.approx(114.0267)
    assert systems["cpr"]["basis_date"] == date(2026, 9, 18)
    assert systems["demark"]["method"].startswith("DeMark")


def test_adjusted_ohlcv_never_mixes_factor_covered_and_raw_history():
    rows = [
        {"trade_date": date(2026, 1, 1), "open": 100, "high": 102, "low": 98, "close": 100},
        {"trade_date": date(2026, 1, 2), "open": 50, "high": 51, "low": 49, "close": 50},
    ]
    complete, complete_meta = _adjust_ohlcv(
        rows,
        [
            {"trade_date": date(2026, 1, 1), "adj_factor": 1},
            {"trade_date": date(2026, 1, 2), "adj_factor": 2},
        ],
        dataset="fund_adj",
    )
    partial, partial_meta = _adjust_ohlcv(
        rows,
        [{"trade_date": date(2026, 1, 2), "adj_factor": 2}],
        dataset="fund_adj",
    )

    assert complete_meta["status"] == "applied"
    assert complete[0]["close"] == pytest.approx(50)
    assert complete[1]["close"] == pytest.approx(50)
    assert partial_meta["status"] == "partial_history"
    assert len(partial) == 1
    assert partial[0]["trade_date"] == date(2026, 1, 2)


def test_fibonacci_retracement_uses_only_last_confirmed_swing():
    result = _fibonacci_retracement(
        [
            {"trade_date": "2026-01-01", "price": 100, "type": "low", "confirmed": True},
            {"trade_date": "2026-02-01", "price": 200, "type": "high", "confirmed": True},
            {"trade_date": "2026-02-20", "price": 160, "type": "low", "confirmed": False},
        ],
        150,
    )

    assert result["status"] == "ready"
    assert result["direction"] == "up"
    assert result["retracement_levels"]["23.6"] == pytest.approx(176.4)
    assert result["retracement_levels"]["61.8"] == pytest.approx(138.2)
    assert result["extension_levels"]["161.8"] == pytest.approx(261.8)
    assert result["current_retracement_pct"] == pytest.approx(50.0)
    assert result["live_pivot_excluded"]["price"] == 160


def test_chan_candidate_contract_builds_fractals_strokes_and_centers():
    closes = [
        100, 102, 104, 106, 108,
        106, 104, 102, 100,
        102, 104, 106, 110,
        108, 106, 104, 102,
        104, 106, 108, 112,
        110, 108, 106, 104,
    ]
    rows = [
        {
            "trade_date": date(2026, 1, 1) + timedelta(days=index),
            "open": close - 0.2,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "vol": 1000 + index,
        }
        for index, close in enumerate(closes)
    ]

    result = _chan_analysis(rows, closes[-1])

    assert result["status"] == "ready"
    assert len(result["fractals"]) >= 5
    assert len(result["strokes"]) >= 4
    assert result["segment_candidates"]
    assert result["centers"]
    assert result["current_position"] in {"above_center", "inside_center", "below_center"}
    assert "signals" in result


@pytest.mark.parametrize(
    ("asset_type", "code", "dataset", "basic_dataset"),
    [
        ("index", "000688.SH", "index_daily", "index_basic"),
        ("etf", "512480.SH", "fund_daily", "fund_basic"),
        ("spot", "Au99.99", "sge_daily", "sge_basic"),
        ("sector", "884229.TI", "industry_daily", None),
    ],
)
def test_instrument_technicals_supports_non_stock_assets(
    asset_type, code, dataset, basic_dataset
):
    datasets = {dataset: _daily_rows(code, count=300)}
    if basic_dataset:
        datasets[basic_dataset] = [{"ts_code": code, "name": code}]

    result = ResearchService(
        FakeDataService(datasets), FakeRepository()
    ).instrument_technicals(
        asset_type, code, provider="ths" if asset_type == "sector" else None
    )

    assert result["data"]["instrument"]["code"] == code
    assert result["data"]["timeframes"]["1d"]["status"] == "ready"
    assert result["data"]["timeframes"]["1w"]["levels"]["pivot_systems"]["classic"]
    assert result["meta"]["provenance"][0] == {
        "dataset": dataset, "returned": 300
    }


def test_instrument_relative_risk_is_suppressed_without_adjustment_factors():
    datasets = {
        "fund_daily": _daily_rows("512480.SH", count=300),
        "fund_basic": [{"ts_code": "512480.SH", "name": "半导体ETF"}],
        "index_daily": _daily_rows("000300.SH", count=300, base=20),
    }

    result = ResearchService(
        FakeDataService(datasets), FakeRepository()
    ).instrument_technicals(
        "etf", "512480.SH", benchmark="000300.SH"
    )

    relative = result["data"]["relative_strength"]
    assert result["meta"]["price_adjustment"]["status"] == "missing"
    assert relative["status"] == "unavailable_unadjusted"
    assert relative["excess_return_60d_pct"] is None
    assert relative["risk_metrics"]["windows"] == {}
    assert result["meta"]["provenance"][-1] == {
        "dataset": "index_daily", "returned": 0
    }


def test_repurchase_progress_uses_latest_cumulative_execution_not_sum():
    datasets = {
        "stock_basic": [{"ts_code": "300750.SZ"}],
        "repurchase": [
            {"ts_code": "300750.SZ", "ann_date": date(2026, 8, 12), "proc": "股东大会通过", "amount": 40_000_000_000, "high_limit": 573},
            {"ts_code": "300750.SZ", "ann_date": date(2026, 9, 11), "proc": "实施", "vol": 604_293, "amount": 199_978_827.46},
            {"ts_code": "300750.SZ", "ann_date": date(2026, 9, 18), "proc": "实施", "vol": 5_215_160, "amount": 1_603_313_093.92},
        ],
        "stock_daily": _daily_rows("300750.SZ", count=20, start=date(2026, 9, 1), base=300),
        "index_daily": _daily_rows("399006.SZ", count=20, start=date(2026, 9, 1), base=2000),
    }

    result = ResearchService(
        FakeDataService(datasets), FakeRepository()
    ).repurchase_progress("300750.SZ", as_of=date(2026, 9, 20))

    progress = result["data"]["progress"]
    assert progress["executed_amount"] == 1_603_313_093.92
    assert progress["amount_progress_pct"] == pytest.approx(4.0083)
    assert progress["average_execution_price"] == pytest.approx(307.4332)
    assert result["data"]["status"] == "in_progress"


def test_zigzag_confirms_cumulative_move_without_requiring_one_day_jump():
    rows = [
        {"trade_date": date(2026, 9, day), "close": close}
        for day, close in enumerate((100, 102, 105, 109), start=1)
    ]

    pivots = _zigzag(rows, 8.0)

    assert pivots == [
        {"trade_date": "2026-09-01", "price": 100.0, "type": "low", "confirmed": True},
        {"trade_date": "2026-09-04", "price": 109.0, "type": "high", "confirmed": False},
    ]


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
    assert catalog["summary"]["agent_endpoints"] == 11
    assert catalog["summary"]["derived_endpoints"] == 9
    assert catalog["summary"]["backfill_workstreams"] == 6
    assert catalog["summary"]["new_source_todos"] == 3
    assert catalog["summary"]["baseline_techniques"] == 56
    assert catalog["summary"]["currently_served"] == 48
    assert catalog["summary"]["planned_from_existing_sources"] == 3
    assert catalog["summary"]["external_or_constrained"] == 5
    assert len(catalog["techniques"]["served"]) == 48
    assert len(catalog["techniques"]["gaps"]) == 8
    analyst = next(item for item in catalog["backfills"] if item["group"] == "analyst")
    assert analyst["status"] == "running"
    assert analyst["active"] == 2
