from datetime import date

from scripts.queue_factor_input_backfill import daily_proposals


def test_daily_proposals_keep_one_execution_per_logical_day():
    values = daily_proposals(
        "fama_french_daily",
        "fama_french_daily",
        (date(2020, 1, 2), date(2020, 1, 3)),
    )
    assert [item.observation_key for item in values] == [
        "2020-01-02",
        "2020-01-03",
    ]
    assert all(item.observation_start == item.observation_end for item in values)
