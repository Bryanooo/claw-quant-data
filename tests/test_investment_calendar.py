from datetime import date, datetime, time, timezone

import pytest

from service.investment_calendar import (
    InvalidInvestmentCalendarRequest,
    InvestmentCalendarService,
)


class FakeRepository:
    def economic_events(self, start_date, end_date):
        rows = [
            {
                "date": date(2026, 9, 18),
                "time": time(9, 30),
                "currency": "CNY",
                "country": "中国",
                "event": "中国第二季度GDP年率",
                "value": "5.1%",
                "pre_value": "4.9%",
                "fore_value": "5.0%",
                "_source_collected_at": datetime(
                    2026, 9, 18, tzinfo=timezone.utc
                ),
            },
            {
                "date": date(2026, 9, 19),
                "time": time(9),
                "currency": "CNY",
                "country": "中国",
                "event": "中国9月官方制造业PMI",
                "value": None,
                "pre_value": "49.7",
                "fore_value": "50.1",
                "_source_collected_at": datetime(
                    2026, 9, 17, tzinfo=timezone.utc
                ),
            },
            {
                "date": date(2026, 9, 18),
                "time": time(15),
                "currency": "USD",
                "country": "美国",
                "event": "美国普通债券拍卖",
                "value": None,
                "pre_value": None,
                "fore_value": None,
                "_source_collected_at": datetime(
                    2026, 9, 17, tzinfo=timezone.utc
                ),
            },
        ]
        return [row for row in rows if start_date <= row["date"] <= end_date]

    def index_futures_deliveries(self, start_date, end_date):
        rows = [
            {
                "ts_code": f"{code}2609.CFX",
                "fut_code": code,
                "d_month": "202609",
                "last_ddate": "20260918",
                "name": f"{code} 2609",
                "_source_collected_at": datetime(
                    2026, 9, 13, tzinfo=timezone.utc
                ),
            }
            for code in ("IF", "IH", "IC", "IM")
        ]
        return rows if start_date <= date(2026, 9, 18) <= end_date else []

    def source_coverage(self):
        return {
            "economic_calendar": {
                "min_date": date(2026, 8, 1),
                "max_date": date(2026, 10, 31),
                "physical_rows": 1000,
            },
            "index_futures": {
                "max_date": date(2026, 12, 18),
                "physical_rows": 100,
            },
        }


def test_calendar_classifies_macro_events_and_groups_index_futures():
    result = InvestmentCalendarService(FakeRepository()).list_events(
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 30),
    )

    assert result["summary"] == {
        "total_events": 3,
        "days_with_events": 2,
        "high_events": 3,
        "scheduled_events": 2,
        "released_events": 1,
    }
    gdp = next(item for item in result["events"] if "GDP" in item["title"])
    assert gdp["event_type"] == "growth"
    assert gdp["importance"] == "high"
    assert gdp["status"] == "released"
    assert gdp["related_dataset"] == "cn_gdp"

    pmi = next(item for item in result["events"] if "PMI" in item["title"])
    assert pmi["event_type"] == "survey"
    assert pmi["status"] == "scheduled"
    assert pmi["related_dataset"] == "cn_pmi"

    delivery = next(
        item for item in result["events"] if item["event_type"] == "derivatives"
    )
    assert delivery["source"] == "fut_basic"
    assert {item["fut_code"] for item in delivery["contracts"]} == {
        "IF", "IH", "IC", "IM"
    }
    assert len([item for item in result["events"] if item["event_type"] == "derivatives"]) == 1


def test_calendar_filters_normal_events_by_default_and_can_return_all():
    service = InvestmentCalendarService(FakeRepository())

    important = service.day_events(date(2026, 9, 18))
    all_events = service.day_events(date(2026, 9, 18), importance="all")

    assert important["summary"]["total_events"] == 2
    assert all_events["summary"]["total_events"] == 3


def test_calendar_validates_range():
    service = InvestmentCalendarService(FakeRepository())

    with pytest.raises(InvalidInvestmentCalendarRequest):
        service.list_events(
            start_date=date(2026, 10, 1), end_date=date(2026, 9, 1)
        )
    with pytest.raises(InvalidInvestmentCalendarRequest):
        service.list_events(
            start_date=date(2026, 1, 1), end_date=date(2026, 4, 1)
        )
