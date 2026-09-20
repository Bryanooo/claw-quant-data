from datetime import date

import pytest

from scripts import manage_research_backfills as backfills


def test_news_backfill_uses_resumable_source_year_scopes(monkeypatch):
    captured = []

    def fake_create(children, window_start, window_end):
        captured.append((children, window_start, window_end))
        return True

    monkeypatch.setattr(backfills, "_create_news_batch", fake_create)

    result = backfills.queue_news(date(2026, 9, 17), date(2026, 9, 18))

    assert result == {"jobs_created": 9, "campaigns_created": 0, "batches_created": 1}
    assert captured[0][0][0].parameters["parameters"] == {
        "src": "新华网", "start_date": "20260917", "end_date": "20260918"
    }
    assert captured[0][0][-1].parameters["parameters"] == {
        "src": "财联社", "start_date": "20260917", "end_date": "20260918"
    }
    assert all(child.api_name == "major_news" for child in captured[0][0])
    assert all(child.resource_class == "news-backfill" for child in captured[0][0])
    assert captured[0][1:] == (date(2026, 9, 17), date(2026, 9, 18))


def test_analyst_backfill_uses_independently_verifiable_daily_scopes(monkeypatch):
    captured = []

    def fake_create(group, api_name, parameters, **metadata):
        captured.append((group, api_name, parameters, metadata))
        return True

    monkeypatch.setattr(backfills, "_create_job", fake_create)

    result = backfills.queue_analyst(date(2026, 9, 17), date(2026, 9, 19))

    assert result == {"jobs_created": 3, "campaigns_created": 0}
    assert [item[2] for item in captured] == [
        {"start_date": "20260917", "end_date": "20260917"},
        {"start_date": "20260918", "end_date": "20260918"},
        {"start_date": "20260919", "end_date": "20260919"},
    ]
    assert all(item[0] == "analyst" and item[1] == "report_rc" for item in captured)


def test_intraday_backfill_enforces_the_upstream_daily_call_limit(monkeypatch):
    monkeypatch.setattr(backfills, "_create_job", lambda *_args, **_kwargs: True)

    with pytest.raises(SystemExit, match="one or two"):
        backfills.queue_intraday(
            ["000001.SZ", "000002.SZ", "000003.SZ"],
            day=date(2026, 9, 18),
            frequency="5min",
        )


def test_chip_backfill_requires_an_explicit_high_cardinality_flag():
    with pytest.raises(SystemExit, match="high-cardinality"):
        backfills.queue_chips(
            date(2026, 9, 1),
            date(2026, 9, 18),
            allow_high_cardinality=False,
        )
