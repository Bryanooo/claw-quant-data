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


class CalendarRepository(FakeRepository):
    def list_range_with_execution(self, start_date, end_date):
        return [
            row for row in self.rows
            if start_date <= row["business_date"] <= end_date
        ]

    def list_calendar_with_execution(
        self, start_date, end_date, *, date_basis="business_date"
    ):
        return [
            row for row in self.rows
            if row.get(date_basis) is not None
            and start_date <= row[date_basis] <= end_date
        ]


class DataFactRepository(CalendarRepository):
    def __init__(self, rows, *, facts=(), evidence=(), market_dates=()):
        super().__init__(rows)
        self.facts = list(facts)
        self.evidence = list(evidence)
        self.market_dates = set(market_dates)

    def list_daily_data_facts(self, start_date, end_date):
        return [
            item for item in self.facts
            if start_date <= item["data_date"] <= end_date
        ]

    def list_daily_coverage_evidence(self, start_date, end_date):
        return [
            item for item in self.evidence
            if start_date <= item["partition_date"] <= end_date
        ]

    def list_market_dates(self, start_date, end_date):
        return {day for day in self.market_dates if start_date <= day <= end_date}

    def daily_data_bounds(self):
        return date(1990, 12, 19), date(2026, 9, 11)

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
        "job_evidence": {"verified": True},
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


def test_delivery_calendar_classifies_complete_issue_and_untracked_days():
    complete = plan_row(
        "complete_api",
        8,
        10,
        business_date=date(2026, 9, 1),
        scheduled_for=datetime(2026, 9, 1, 8, tzinfo=timezone.utc),
        due_at=datetime(2026, 9, 1, 10, tzinfo=timezone.utc),
        job_id=20,
        job_status="success",
        job_completion_status="complete",
        job_finished_at=datetime(2026, 9, 1, 9, tzinfo=timezone.utc),
    )
    overdue = plan_row(
        "missing_api",
        8,
        10,
        business_date=date(2026, 9, 2),
        scheduled_for=datetime(2026, 9, 2, 8, tzinfo=timezone.utc),
        due_at=datetime(2026, 9, 2, 10, tzinfo=timezone.utc),
    )
    repository = CalendarRepository([complete, overdue])
    payload = DeliveryMonitorService(
        repository=repository,
        builder=FakeBuilder(),
        now_factory=lambda: datetime(2026, 9, 3, 12, tzinfo=timezone.utc),
    ).calendar(date(2026, 9, 1), date(2026, 9, 3))

    assert [item["status"] for item in payload["days"]] == [
        "complete", "issue", "untracked"
    ]
    assert payload["summary"] == {
        "days": 3,
        "complete_days": 1,
        "issue_days": 1,
        "in_progress_days": 0,
        "untracked_days": 1,
        "future_days": 0,
    }
    assert repository.upserted == [{"business_date": date(2026, 9, 3)}]


def test_delivery_calendar_rejects_unbounded_ranges():
    service = DeliveryMonitorService(
        repository=CalendarRepository([]), builder=FakeBuilder()
    )

    try:
        service.calendar(date(2026, 1, 1), date(2026, 4, 1))
    except ValueError as error:
        assert "63 days" in str(error)
    else:
        raise AssertionError("unbounded calendar range was accepted")


def test_data_calendar_uses_data_date_and_collapses_recovery_attempts():
    failed_same_day = plan_row(
        "daily_api",
        8,
        10,
        business_date=date(2026, 9, 8),
        expected_for=date(2026, 9, 8),
        scheduled_for=datetime(2026, 9, 8, 8, tzinfo=timezone.utc),
        due_at=datetime(2026, 9, 8, 10, tzinfo=timezone.utc),
        job_id=31,
        job_status="failed",
        job_completion_status="failed",
        job_error_message="temporary upstream failure",
    )
    verified_recovery = plan_row(
        "daily_api",
        12,
        14,
        delivery_plan_id=2,
        business_date=date(2026, 9, 9),
        expected_for=date(2026, 9, 8),
        scheduled_for=datetime(2026, 9, 9, 12, tzinfo=timezone.utc),
        due_at=datetime(2026, 9, 9, 14, tzinfo=timezone.utc),
        job_id=32,
        job_status="success",
        job_completion_status="complete",
        job_rows_fetched=100,
        job_rows_inserted=100,
        job_finished_at=datetime(2026, 9, 9, 13, tzinfo=timezone.utc),
    )
    repository = CalendarRepository([failed_same_day, verified_recovery])
    service = DeliveryMonitorService(
        repository=repository,
        builder=FakeBuilder(),
        now_factory=lambda: datetime(2026, 9, 11, 12, tzinfo=timezone.utc),
    )

    payload = service.data_calendar(date(2026, 9, 8), date(2026, 9, 9))
    detail = service.data_calendar_day(date(2026, 9, 8))

    assert [day["status"] for day in payload["days"]] == ["complete", "untracked"]
    assert payload["basis"] == "data_date"
    assert detail["summary"]["total"] == 1
    assert detail["summary"]["completed_total"] == 1
    assert detail["items"][0]["business_dates"] == ["2026-09-08", "2026-09-09"]
    assert detail["items"][0]["planned_attempt_total"] == 2
    assert detail["items"][0]["validation_state"] == "verified_complete"
    assert detail["items"][0]["attention"] is False


def test_data_calendar_does_not_mark_failed_attempt_red_before_final_deadline():
    failed = plan_row(
        "recoverable_api",
        8,
        10,
        business_date=date(2026, 9, 8),
        expected_for=date(2026, 9, 8),
        job_id=40,
        job_status="failed",
        job_completion_status="failed",
    )
    recovery = plan_row(
        "recoverable_api",
        19,
        23,
        delivery_plan_id=2,
        business_date=date(2026, 9, 9),
        expected_for=date(2026, 9, 8),
        scheduled_for=datetime(2026, 9, 9, 19, tzinfo=timezone.utc),
        due_at=datetime(2026, 9, 9, 23, tzinfo=timezone.utc),
        job_evidence={},
    )
    service = DeliveryMonitorService(
        repository=CalendarRepository([failed, recovery]),
        builder=FakeBuilder(),
        now_factory=lambda: datetime(2026, 9, 9, 12, tzinfo=timezone.utc),
    )

    detail = service.data_calendar_day(date(2026, 9, 8))

    assert detail["summary"]["status"] == "in_progress"
    assert detail["summary"]["attention"] == 0
    assert detail["items"][0]["delivery_status"] == "not_due"
    assert detail["items"][0]["validation_state"] == "pending_final_attempt"


def test_data_calendar_does_not_invent_denominator_from_t_plus_one_evidence():
    orphan_recovery = plan_row(
        "index_daily",
        8,
        10,
        business_date=date(2026, 9, 9),
        expected_for=date(2026, 9, 8),
        job_id=45,
        job_status="success",
        job_completion_status="complete",
    )
    service = DeliveryMonitorService(
        repository=CalendarRepository([orphan_recovery]),
        builder=FakeBuilder(),
        now_factory=lambda: datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
    )

    detail = service.data_calendar_day(date(2026, 9, 8))

    assert detail["summary"]["status"] == "untracked"
    assert detail["summary"]["requirement_snapshot_complete"] is False
    assert detail["summary"]["completed_total"] == 1


def test_terminal_job_without_verification_evidence_is_not_green():
    row = plan_row(
        "unsafe_complete",
        8,
        10,
        job_id=50,
        job_status="success",
        job_completion_status="complete",
        job_evidence={},
    )
    service = DeliveryMonitorService(
        repository=CalendarRepository([row]),
        builder=FakeBuilder(),
        now_factory=lambda: datetime(2026, 9, 8, 12, tzinfo=timezone.utc),
    )

    detail = service.data_calendar_day(date(2026, 9, 8))

    assert detail["summary"]["status"] == "issue"
    assert detail["items"][0]["delivery_status"] == "incomplete"
    assert detail["items"][0]["validation_state"] == "missing_verified_completion"


def test_data_calendar_recovers_true_cadence_from_old_dedicated_snapshot():
    old_bad_quarterly = plan_row(
        "income",
        8,
        10,
        source_type="dedicated",
        source_key="income_quarterly",
        cadence="daily",
        job_id=60,
        job_status="success",
        job_completion_status="complete",
    )
    genuine_daily = plan_row(
        "daily",
        8,
        10,
        delivery_plan_id=2,
        source_type="dedicated",
        source_key="stock_daily",
        cadence="daily",
        job_id=61,
        job_status="success",
        job_completion_status="complete",
    )
    service = DeliveryMonitorService(
        repository=CalendarRepository([old_bad_quarterly, genuine_daily]),
        builder=FakeBuilder(),
        now_factory=lambda: datetime(2026, 9, 9, 12, tzinfo=timezone.utc),
    )

    detail = service.data_calendar_day(date(2026, 9, 8))

    assert [item["api_name"] for item in detail["items"]] == ["daily"]


def test_data_calendar_never_turns_green_from_task_success_alone():
    day = date(2026, 9, 8)
    task = plan_row(
        "daily", 8, 10, job_id=70, job_status="success",
        job_completion_status="complete",
    )
    service = DeliveryMonitorService(
        repository=DataFactRepository([task], market_dates=[day]),
        builder=FakeBuilder(),
        now_factory=lambda: datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
    )

    result = service.data_calendar_day(day)

    assert result["summary"]["status"] == "untracked"
    assert result["summary"]["task_completed"] == 1
    assert result["summary"]["audited_present"] == 0


def test_data_calendar_shows_historical_physical_rows_as_observed():
    day = date(2018, 1, 2)
    service = DeliveryMonitorService(
        repository=DataFactRepository(
            [],
            facts=[{"dataset_name": "stock_daily", "data_date": day, "row_count": 3200}],
            market_dates=[day],
        ),
        builder=FakeBuilder(),
        now_factory=lambda: datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
    )

    result = service.data_calendar(day, day)

    assert result["days"][0]["status"] == "observed"
    assert result["days"][0]["observed_rows"] == 3200
    assert result["observed_min_date"] == "1990-12-19"


def test_data_calendar_ignores_obsolete_audit_revision_false_failure():
    day = date(1991, 2, 20)
    service = DeliveryMonitorService(
        repository=DataFactRepository(
            [],
            facts=[{"dataset_name": "stock_daily", "data_date": day, "row_count": 4}],
            evidence=[{
                "dataset_name": "stock_daily", "partition_date": day,
                "status": "partial", "expected": True, "row_count": 4,
                "rule_revision": None,
            }],
            market_dates=[day],
        ),
        builder=FakeBuilder(),
        now_factory=lambda: datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
    )

    result = service.data_calendar_day(day)

    assert result["summary"]["status"] == "observed"
    assert result["summary"]["audited_issues"] == 0


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
    finance = next(
        item for item in plans if item["source_key"] == "income_quarterly"
    )
    assert finance["cadence"] == "quarterly"
    assert finance["expected_for"] == date(2026, 6, 30)
    assert finance["period_key"] == "20260630"
    assert not any(
        item["source_key"] == "stk_monthly_monthly_eom" for item in plans
    )
