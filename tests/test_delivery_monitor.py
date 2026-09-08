from datetime import date, datetime, timezone

from service.delivery_monitor import DeliveryMonitorService, DeliveryPlanBuilder


class FakeBuilder:
    def build(self, business_date):
        return [{"business_date": business_date}]


class FakeRepository:
    def __init__(self, rows):
        self.rows = rows
        self.upserted = []

    def upsert(self, rows):
        self.upserted.extend(rows)
        return len(rows)

    def list_with_execution(self, business_date):
        return self.rows


def plan_row(name, scheduled_hour, due_hour, **overrides):
    row = {
        "delivery_plan_id": 1,
        "business_date": date(2026, 9, 8),
        "plan_key": f"policy:{name}:daily",
        "source_type": "policy",
        "source_key": name,
        "api_name": name,
        "title": name,
        "cadence": "daily",
        "scheduled_for": datetime(2026, 9, 8, scheduled_hour, tzinfo=timezone.utc),
        "due_at": datetime(2026, 9, 8, due_hour, tzinfo=timezone.utc),
        "expected_for": date(2026, 9, 8),
        "period_key": "2026-09-08",
        "metadata": {},
        "created_at": datetime(2026, 9, 7, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 9, 7, tzinfo=timezone.utc),
        "job_id": None,
        "job_status": None,
        "job_completion_status": None,
        "job_rows_fetched": None,
        "job_rows_inserted": None,
        "job_attempt": None,
        "job_finished_at": None,
        "job_error_message": None,
    }
    row.update(overrides)
    return row


def test_today_progress_separates_not_due_overdue_and_strict_completion():
    now = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
    rows = [
        plan_row(
            "complete_api",
            8,
            10,
            job_id=10,
            job_status="success",
            job_completion_status="complete",
            job_rows_fetched=100,
            job_rows_inserted=100,
            job_finished_at=datetime(2026, 9, 8, 9, tzinfo=timezone.utc),
        ),
        plan_row("missing_api", 8, 10),
        plan_row("future_api", 19, 23),
        plan_row(
            "unverified_api",
            11,
            18,
            job_id=11,
            job_status="success",
            job_completion_status="unverified",
        ),
    ]
    repository = FakeRepository(rows)
    payload = DeliveryMonitorService(
        repository=repository,
        builder=FakeBuilder(),
        now_factory=lambda: now,
    ).today(date(2026, 9, 8))

    states = {item["api_name"]: item["delivery_status"] for item in payload["items"]}
    assert states == {
        "complete_api": "complete",
        "missing_api": "overdue",
        "future_api": "not_due",
        "unverified_api": "unverified",
    }
    assert payload["summary"]["due_now"] == 3
    assert payload["summary"]["completed_due"] == 1
    assert payload["summary"]["attention"] == 1
    assert [item["api_name"] for item in payload["issues"]] == ["missing_api"]
    assert repository.upserted == [{"business_date": date(2026, 9, 8)}]


def test_completed_delivery_is_not_reclassified_by_due_time():
    now = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
    row = plan_row(
        "late_but_recovered",
        8,
        10,
        job_id=12,
        job_status="success",
        job_completion_status="complete",
        job_finished_at=datetime(2026, 9, 8, 11, tzinfo=timezone.utc),
    )
    payload = DeliveryMonitorService(
        repository=FakeRepository([row]),
        builder=FakeBuilder(),
        now_factory=lambda: now,
    ).today(date(2026, 9, 8))

    assert payload["items"][0]["delivery_status"] == "complete"
    assert payload["items"][0]["on_time"] is False
    assert payload["summary"]["attention"] == 0


def test_unverified_delivery_becomes_incomplete_after_due_time():
    now = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
    row = plan_row(
        "unverified_after_deadline",
        8,
        10,
        job_id=13,
        job_status="success",
        job_completion_status="unverified",
        job_rows_fetched=20,
        job_rows_inserted=20,
    )
    payload = DeliveryMonitorService(
        repository=FakeRepository([row]),
        builder=FakeBuilder(),
        now_factory=lambda: now,
    ).today(date(2026, 9, 8))

    assert payload["items"][0]["delivery_status"] == "incomplete"
    assert payload["items"][0]["attention"] is True
    assert payload["summary"]["attention"] == 1


def test_partial_intraday_delivery_waits_until_its_deadline():
    now = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
    row = plan_row(
        "still_publishing",
        8,
        14,
        job_id=14,
        job_status="success",
        job_completion_status="incomplete",
        job_rows_fetched=1200,
        job_rows_inserted=1200,
    )
    payload = DeliveryMonitorService(
        repository=FakeRepository([row]),
        builder=FakeBuilder(),
        now_factory=lambda: now,
    ).today(date(2026, 9, 8))

    assert payload["items"][0]["delivery_status"] == "waiting"
    assert payload["items"][0]["attention"] is False
    assert payload["summary"]["attention"] == 0


def test_policy_plan_only_schedules_daily_work_on_market_days():
    empty_scheduler = type("Scheduler", (), {"get_jobs": lambda self: []})()
    closed = DeliveryPlanBuilder(
        market_open=lambda day: False,
        scheduler_factory=lambda: empty_scheduler,
    ).build(date(2026, 9, 8))
    opened = DeliveryPlanBuilder(
        market_open=lambda day: True,
        scheduler_factory=lambda: empty_scheduler,
    ).build(date(2026, 9, 8))

    assert not any(item["cadence"] == "daily" for item in closed)
    assert any(item["source_type"] == "policy" for item in opened)
    assert any(item["source_type"] == "fanout" for item in opened)


def test_t_plus_one_delivery_targets_previous_trade_date(monkeypatch):
    from collectors.scheduler import create_scheduler

    monkeypatch.setattr(
        "service.tushare_scheduling._latest_trade_date",
        lambda _at: "20260907",
    )
    plans = DeliveryPlanBuilder(
        market_open=lambda _day: True,
        scheduler_factory=lambda: create_scheduler(
            durabilize=False, set_active=False
        ),
    ).build(date(2026, 9, 8))
    plan = next(
        item for item in plans if item["source_key"] == "index_daily_finalize"
    )

    assert plan["expected_for"] == date(2026, 9, 7)
    assert plan["period_key"] == "2026-09-07"
