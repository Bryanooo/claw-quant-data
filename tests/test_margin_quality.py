from datetime import date
from unittest.mock import Mock

import pytest

from service.margin_quality import balance_issues, market_balances
from service.research.service import ResearchService


def row(exchange="SSE", **values):
    return dict(
        trade_date="20261103",
        exchange_id=exchange,
        rzye=100000000,
        rqye=20000000,
        rzrqye=120000000,
        **values,
    )


def test_market_total_is_not_financing_and_keeps_three_explicit_fields():
    service = ResearchService.__new__(ResearchService)
    service._load_many = Mock(
        side_effect=[[row(e) for e in ("SSE", "SZSE", "BSE")], [], []]
    )
    result = service.market_funds(days=20, as_of=date(2026, 11, 4))
    assert result["data"]["margin_balance"]["series"] == [("2026-11-03", 3.6)]
    assert result["data"]["financing_balance"]["series"] == [("2026-11-03", 3.0)]
    assert result["data"]["securities_lending_balance"]["series"] == [
        ("2026-11-03", 0.6)
    ]
    assert result["meta"]["margin_quality"]["status"] == "ready"


def test_market_flow_yuan_and_northbound_10k_yuan_are_not_interchangeable():
    service = ResearchService.__new__(ResearchService)
    service._load_many = Mock(side_effect=[[],
        [{"trade_date": "20261103", "north_money": 340000}],
        [{"trade_date": "20261104", "net_amount": 50028113920}],
    ])
    result = service.market_funds(days=20, as_of=date(2026, 11, 4))
    assert result["data"]["north_money"]["series"] == [("2026-11-03", 34)]
    assert result["data"]["market_flow"]["series"] == [("2026-11-04", 500.28)]
    assert result["meta"]["margin_quality"]["status"] == "missing"


@pytest.mark.parametrize(
    "field,value",
    [
        ("rzye", None),
        ("rqye", float("nan")),
        ("rqye", float("inf")),
        ("rzrqye", -1),
        ("rzrqye", 100000000),
    ],
)
def test_invalid_fields_or_sum_never_satisfy_completeness(field, value):
    invalid = dict(row(), **{field: value})
    assert balance_issues(invalid)
    result = market_balances([invalid, row("SZSE"), row("BSE")], 20)
    assert result["status"] == "partial"
    assert result["series"]["rzrqye"] == []
    assert result["incomplete_dates"][0]["invalid_rows"]


def test_missing_exchange_duplicate_exchange_and_beijing_start_boundary():
    for rows in ([row(), row("SZSE")], [row(), row("SZSE"), row("BSE"), row()]):
        assert market_balances(rows, 20)["status"] == "partial"
    early = [dict(row(e), trade_date="20230210") for e in ("SSE", "SZSE")]
    assert market_balances(early, 20)["status"] == "ready"
    assert balance_issues(dict(row(), rzye=0, rqye=0, rzrqye=0)) == []


def test_stock_capital_flow_surfaces_bad_balance_even_when_moneyflow_exists():
    service = ResearchService.__new__(ResearchService)
    service._ensure_stock = Mock()
    service._load = Mock(
        side_effect=[
            [{"net_mf_amount": 1}],
            [dict(row(), ts_code="601326.SH", rqye=None, rzrqye=None)],
            [],
            [],
            [],
        ]
    )
    service._provenance = Mock(return_value=[])
    result = service.capital_flow(
        "601326.SH", lookback_days=5, as_of=date(2026, 10, 30)
    )
    assert result["meta"]["quality"]["status"] == "warning"
    assert result["data"]["margin"]["quality"]["status"] == "partial"
    assert result["data"]["margin"]["latest"]["rqye"] is None
