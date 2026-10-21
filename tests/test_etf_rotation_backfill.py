from datetime import date
from scripts.backfill_etf_rotation import scopes, SYMBOLS


def test_only_requested_funds_and_bounded_calendar_years():
    jobs = list(scopes(date(2019, 3, 1), date(2020, 2, 1)))
    assert len(jobs) == len(SYMBOLS) * 9
    assert {params["ts_code"] for _, params in jobs} == set(SYMBOLS)
    for dataset, params in jobs:
        if dataset == "fund_div":
            assert set(params) == {"ts_code"}  # API has no date-range parameters
        else:
            assert (params["start_date"], params["end_date"]) in {
                ("20190301", "20191231"), ("20200101", "20200201")}
