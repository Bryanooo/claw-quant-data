from datetime import date

from service.history_recovery import (
    build_reverse_fanout_scopes,
    build_reverse_recovery_plan,
)


def test_reverse_recovery_uses_exact_dates_for_high_cross_section_apis():
    plan = build_reverse_recovery_plan(
        dataset_apis={"bak_daily": "bak_daily", "cn_pmi": "cn_pmi"},
        targets_by_dataset={
            "bak_daily": [date(2024, 1, 2), date(2024, 2, 1)],
            "cn_pmi": [date(2024, 1, 31), date(2024, 2, 29)],
        },
        history_start=date(2024, 1, 1),
        history_end=date(2024, 2, 29),
        trade_dates=(date(2024, 1, 2), date(2024, 2, 1)),
    )

    assert not plan.unsupported
    assert [item.expected_for for item in plan.specs] == sorted(
        [item.expected_for for item in plan.specs], reverse=True
    )
    bak = [item for item in plan.specs if item.api_name == "bak_daily"]
    assert [item.parameters["parameters"] for item in bak] == [
        {"trade_date": "20240201"},
        {"trade_date": "20240102"},
    ]
    assert all(item.cadence == "backfill" for item in plan.specs)
    assert all(item.resource_class == "backfill" for item in plan.specs)
    assert all(item.max_attempts == 8 for item in plan.specs)


def test_reverse_recovery_uses_trade_date_for_provider_rejected_range_apis():
    targets = {
        "fund_daily": date(2021, 3, 26),
        "index_daily": date(2021, 3, 26),
        "index_monthly": date(2016, 8, 31),
    }
    plan = build_reverse_recovery_plan(
        dataset_apis={name: name for name in targets},
        targets_by_dataset={name: [value] for name, value in targets.items()},
        history_start=date(2016, 8, 31),
        history_end=date(2021, 3, 26),
        trade_dates=tuple(targets.values()),
    )

    by_api = {item.api_name: item for item in plan.specs}
    assert by_api["fund_daily"].parameters["parameters"] == {
        "trade_date": "20210326"
    }
    assert by_api["index_monthly"].parameters["parameters"] == {
        "trade_date": "20160831"
    }
    assert by_api["index_daily"].parameters["parameters"] == {
        "trade_date": "20210326"
    }


def test_reverse_recovery_respects_verified_provider_availability_boundaries():
    trade_dates = (
        date(2014, 11, 14),
        date(2014, 11, 17),
        date(2016, 8, 8),
        date(2016, 8, 9),
        date(2025, 3, 27),
        date(2025, 3, 28),
    )

    ggt = build_reverse_recovery_plan(
        dataset_apis={"ggt_top10": "ggt_top10"},
        targets_by_dataset={"ggt_top10": trade_dates},
        history_start=date(2014, 11, 14),
        history_end=date(2014, 11, 17),
        trade_dates=trade_dates,
    )
    assert [item.expected_for for item in ggt.specs] == [date(2014, 11, 17)]

    generic = build_reverse_recovery_plan(
        dataset_apis={"bak_basic": "bak_basic", "tdx_index": "tdx_index"},
        targets_by_dataset={
            "bak_basic": (date(2016, 8, 8), date(2016, 8, 9)),
            "tdx_index": (date(2025, 3, 27), date(2025, 3, 28)),
        },
        history_start=date(2014, 1, 1),
        history_end=date(2025, 3, 28),
        trade_dates=trade_dates,
    )
    assert {
        (item.api_name, item.expected_for) for item in generic.specs
    } == {
        ("bak_basic", date(2016, 8, 9)),
        ("tdx_index", date(2025, 3, 28)),
    }


def test_reverse_recovery_builds_exact_date_jobs_when_ranges_are_unsupported():
    plan = build_reverse_recovery_plan(
        dataset_apis={"ths_hot": "ths_hot"},
        targets_by_dataset={
            "ths_hot": [date(2024, 1, 2), date(2024, 1, 3)],
        },
        history_start=date(2024, 1, 1),
        history_end=date(2024, 1, 31),
        trade_dates=(date(2024, 1, 2), date(2024, 1, 3)),
    )

    assert len(plan.specs) == 18
    assert {
        item.parameters["parameters"]["trade_date"] for item in plan.specs
    } == {"20240103", "20240102"}
    assert {
        item.parameters["parameters"]["market"] for item in plan.specs
    } == {
        "热股", "ETF", "可转债", "行业板块", "概念板块",
        "期货", "港股", "热基", "美股",
    }
    assert all(
        item.parameters["parameters"]["is_new"] == "Y" for item in plan.specs
    )


def test_ths_hot_history_respects_verified_provider_start_date():
    plan = build_reverse_recovery_plan(
        dataset_apis={"ths_hot": "ths_hot"},
        targets_by_dataset={
            "ths_hot": [date(2023, 8, 18), date(2023, 8, 21)],
        },
        history_start=date(2023, 8, 18),
        history_end=date(2023, 8, 21),
        trade_dates=(date(2023, 8, 18), date(2023, 8, 21)),
    )

    assert len(plan.specs) == 9
    assert {item.expected_for for item in plan.specs} == {date(2023, 8, 21)}
    assert all(
        item.parameters["parameters"]["is_new"] == "Y" for item in plan.specs
    )


def test_reverse_recovery_uses_quarter_contract_for_gdp():
    plan = build_reverse_recovery_plan(
        dataset_apis={"cn_gdp": "cn_gdp"},
        targets_by_dataset={"cn_gdp": [date(2023, 12, 31)]},
        history_start=date(2023, 1, 1),
        history_end=date(2024, 1, 31),
        trade_dates=(),
    )

    assert len(plan.specs) == 1
    assert plan.specs[0].parameters["parameters"] == {
        "start_q": "2023Q4", "end_q": "2023Q4",
    }


def test_reverse_recovery_routes_derived_ggt_monthly_newest_first():
    plan = build_reverse_recovery_plan(
        dataset_apis={"ggt_monthly": "ggt_monthly"},
        targets_by_dataset={
            "ggt_monthly": [date(2024, 1, 31), date(2024, 2, 29)]
        },
        history_start=date(2024, 1, 1),
        history_end=date(2024, 2, 29),
        trade_dates=(),
    )

    assert not plan.unsupported
    assert [item.task_name for item in plan.specs] == [
        "ggt_monthly", "ggt_monthly"
    ]
    assert [item.parameters for item in plan.specs] == [
        {"month": "202402"}, {"month": "202401"}
    ]
    assert [item.expected_for for item in plan.specs] == [
        date(2024, 2, 29), date(2024, 1, 31)
    ]


def test_reverse_recovery_never_uses_incomplete_market_wide_dividend_scope():
    plan = build_reverse_recovery_plan(
        dataset_apis={"dividend": "dividend"},
        targets_by_dataset={"dividend": []},
        history_start=date(2024, 1, 1),
        history_end=date(2024, 12, 31),
        trade_dates=(date(2024, 1, 2),),
    )

    assert not plan.specs
    assert plan.unsupported["dividend"] == (
        "requires bounded fan-out history campaign"
    )


def test_reverse_fanout_scopes_are_bounded_and_newest_first():
    scopes = build_reverse_fanout_scopes(
        api_names=("moneyflow_dc", "dividend"),
        history_start=date(2024, 1, 1),
        history_end=date(2024, 3, 31),
        trade_dates=(),
    )

    moneyflow = [item for item in scopes if item.api_name == "moneyflow_dc"]
    assert [item.expected_for for item in moneyflow] == sorted(
        [item.expected_for for item in moneyflow], reverse=True
    )
    assert all(
        (item.request["end_date"] - item.request["start_date"]).days < 31
        for item in moneyflow
    )
    dividend = [item for item in scopes if item.api_name == "dividend"]
    assert len(dividend) == 1
    assert dividend[0].request == {"api_name": "dividend", "page_size": 200}
