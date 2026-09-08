from datetime import date

from service.collection_jobs.scheduled_reconciliation import (
    ScheduledCompletionReconciler,
)
from service.collection_jobs.scheduled_verification import verify_scheduled_transport


def test_stock_basic_snapshot_requires_stored_count_and_status_partitions():
    def query(_sql, _params):
        return [{"row_count": 5897, "statuses": ["D", "L"]}]

    evidence = verify_scheduled_transport(
        "stock_basic_daily", "2026-09-08T08:30:00+08:00", 5897, query=query
    )

    assert evidence["verified"] is True
    assert evidence["scope"] == "atomic_snapshot"
    assert evidence["observed_statuses"] == ["D", "L"]


def test_trade_calendar_requires_every_day_for_both_exchanges():
    expected = (date(2027, 9, 9) - date(2016, 9, 10)).days + 1

    def query(_sql, params):
        assert params == (date(2016, 9, 10), date(2027, 9, 9))
        return [
            {"exchange": "SSE", "row_count": expected},
            {"exchange": "SZSE", "row_count": expected},
        ]

    evidence = verify_scheduled_transport(
        "trade_cal_daily",
        "2026-09-08T08:30:00+08:00",
        expected * 2,
        query=query,
    )

    assert evidence["verified"] is True
    assert evidence["scope"] == "bounded_exchange_calendar"


def test_index_basic_requires_atomic_snapshot_beyond_csi_response_cap():
    evidence = verify_scheduled_transport(
        "index_basic_weekly",
        "2026-09-08T07:00:00+08:00",
        11707,
        query=lambda _sql, _params: [{
            "row_count": 11707,
            "csi_rows": 8941,
            "markets": ["BSE", "CNI", "CSI", "SSE", "SW", "SZSE"],
        }],
    )

    assert evidence["verified"] is True
    assert evidence["scope"] == "atomic_market_category_snapshot"
    assert verify_scheduled_transport(
        "index_basic_weekly",
        "2026-09-08T07:00:00+08:00",
        8000,
        query=lambda _sql, _params: [{
            "row_count": 8000,
            "csi_rows": 8000,
            "markets": ["CSI", "SSE", "SW", "SZSE"],
        }],
    ) is None


def test_reference_snapshot_requires_all_partitions_and_exact_storage():
    rows = [
        {"partition": "SSE", "row_count": 2457},
        {"partition": "SZSE", "row_count": 3083},
        {"partition": "BSE", "row_count": 754},
    ]
    evidence = verify_scheduled_transport(
        "stock_company_weekly",
        "2026-09-07T08:30:00+08:00",
        6294,
        query=lambda _sql, _params: rows,
    )

    assert evidence["verified"] is True
    assert evidence["partition_rows"]["BSE"] == 754
    assert verify_scheduled_transport(
        "stock_company_weekly",
        "2026-09-07T08:30:00+08:00",
        5540,
        query=lambda _sql, _params: rows[:-1],
    ) is None


def test_top10_requires_both_market_types_and_exact_date_count():
    evidence = verify_scheduled_transport(
        "hsgt_top10_daily",
        "2026-09-07T20:00:00+08:00",
        20,
        query=lambda _sql, params: (
            [{"market_type": 1, "row_count": 10},
             {"market_type": 3, "row_count": 10}]
            if params == (date(2026, 9, 7),) else []
        ),
    )

    assert evidence["scope"] == "exact_trade_date_market_types"


def test_new_share_requires_exact_bounded_ipo_window():
    def query(_sql, params):
        assert params == (date(2026, 8, 8), date(2026, 9, 14))
        return [{"row_count": 22}]

    evidence = verify_scheduled_transport(
        "new_share_weekly", "2026-09-07T08:30:00+08:00", 22, query=query
    )

    assert evidence["scope"] == "bounded_ipo_window"


def test_ggt_windows_require_exact_stored_scope():
    daily = verify_scheduled_transport(
        "ggt_daily_daily",
        "2026-09-07T20:10:00+08:00",
        1,
        query=lambda _sql, params: (
            [{"row_count": 1}]
            if params == (date(2026, 9, 4), date(2026, 9, 7)) else []
        ),
    )
    monthly = verify_scheduled_transport(
        "ggt_monthly_daily",
        "2026-09-07T20:15:00+08:00",
        4,
        query=lambda _sql, params: (
            [{"row_count": 4}] if params == ("202606", "202609") else []
        ),
    )

    assert daily["scope"] == "bounded_calendar_window"
    assert monthly["scope"] == "bounded_month_window"


def test_non_month_end_zero_is_a_verified_conditional_skip():
    evidence = verify_scheduled_transport(
        "stk_monthly_monthly_eom",
        "2026-09-07T20:45:00+08:00",
        0,
        query=lambda _sql, params: (
            [{"is_month_end": False}]
            if params == (date(2026, 9, 7), date(2026, 9, 7)) else []
        ),
    )

    assert evidence["verified"] is True
    assert evidence["empty"] is True
    assert evidence["skip_reason"] == "not_last_open_day_of_month"


def test_month_end_zero_remains_unverified():
    assert verify_scheduled_transport(
        "stk_weekly_monthly_month_daily",
        "2026-09-30T20:35:00+08:00",
        0,
        query=lambda _sql, _params: [{"is_month_end": True}],
    ) is None


def test_non_week_end_zero_is_a_verified_conditional_skip():
    evidence = verify_scheduled_transport(
        "stk_weekly_monthly_week_daily",
        "2026-09-07T20:30:00+08:00",
        0,
        query=lambda _sql, params: (
            [{"is_week_end": False}]
            if params == (date(2026, 9, 7), date(2026, 9, 7)) else []
        ),
    )

    assert evidence["verified"] is True
    assert evidence["empty"] is True
    assert evidence["skip_reason"] == "not_last_open_day_of_week"


def test_week_end_zero_remains_unverified():
    assert verify_scheduled_transport(
        "stk_weekly_monthly_week_daily",
        "2026-09-11T20:30:00+08:00",
        0,
        query=lambda _sql, _params: [{"is_week_end": True}],
    ) is None


def test_weekly_close_correction_proves_exact_source_below_official_cap():
    evidence = verify_scheduled_transport(
        "stk_weekly_weekly_fri",
        "2026-09-04T20:40:00+08:00",
        5630,
        query=lambda _sql, params: (
            [{"row_count": 5630}]
            if params == (date(2026, 9, 4), "week", "weekly") else []
        ),
    )

    assert evidence["verified"] is True
    assert evidence["scope"] == "exact_stock_period_frequency_source"
    assert evidence["documented_row_limit"] == 6000

    assert verify_scheduled_transport(
        "stk_weekly_weekly_fri",
        "2026-09-04T20:40:00+08:00",
        6000,
        query=lambda _sql, _params: [{"row_count": 6000}],
    ) is None


def test_hsgt_requires_all_type_partitions_below_the_per_call_cap():
    rows = [
        {"type": "HK_SH", "row_count": 1643},
        {"type": "HK_SZ", "row_count": 1879},
        {"type": "SH_HK", "row_count": 660},
        {"type": "SZ_HK", "row_count": 660},
    ]
    evidence = verify_scheduled_transport(
        "stock_hsgt_daily",
        "2026-09-08T09:20:00+08:00",
        4842,
        query=lambda _sql, _params: rows,
    )

    assert evidence["verified"] is True
    assert evidence["scope"] == "bounded_hsgt_type_partitions"

    capped = [*rows[:1], {"type": "HK_SZ", "row_count": 2000}, *rows[2:]]
    assert verify_scheduled_transport(
        "stock_hsgt_daily",
        "2026-09-08T09:20:00+08:00",
        sum(item["row_count"] for item in capped),
        query=lambda _sql, _params: capped,
    ) is None


def test_exact_date_schedule_fails_closed_on_stored_count_mismatch():
    assert verify_scheduled_transport(
        "suspend_d_daily",
        "2026-09-08T09:10:00+08:00",
        10,
        query=lambda _sql, _params: [{"row_count": 9}],
    ) is None


def test_exact_date_market_snapshot_requires_exhaustion_below_default_cap():
    evidence = verify_scheduled_transport(
        "ths_daily_daily",
        "2026-09-08T18:20:00+08:00",
        462,
        query=lambda _sql, params: (
            [{"row_count": 462}] if params == (date(2026, 9, 8),) else []
        ),
    )

    assert evidence["verified"] is True
    assert evidence["scope"] == "exact_trade_date"
    assert verify_scheduled_transport(
        "index_global_daily",
        "2026-09-08T22:15:00+08:00",
        1000,
        query=lambda _sql, _params: [{"row_count": 1000}],
    ) is None


def test_dependency_window_requires_exact_stored_count_and_nonempty_reference():
    def query(_sql, params):
        assert params == (date(2026, 9, 1), date(2026, 9, 8))
        return [{
            "row_count": 253,
            "observed_symbols": 37,
            "reference_symbols": 41,
        }]

    evidence = verify_scheduled_transport(
        "fx_daily_daily",
        "2026-09-08T16:30:00+08:00",
        253,
        query=query,
    )

    assert evidence["verified"] is True
    assert evidence["scope"] == "dependency_universe_window"
    assert evidence["reference_symbols"] == 41

    assert verify_scheduled_transport(
        "fx_daily_daily",
        "2026-09-08T16:30:00+08:00",
        252,
        query=query,
    ) is None


class FakeRepository:
    def __init__(self, jobs):
        self.jobs = jobs
        self.promoted = []
        self.queued = []

    def list_unverified_scheduled(self, *, limit):
        assert limit == 50
        return self.jobs

    def apply_transport_verification(self, job_id, evidence):
        self.promoted.append((job_id, evidence))
        return True

    def queue_verification(self, job_id, verification):
        self.queued.append((job_id, verification))
        return 99


class FakePlanner:
    def plan(self, job):
        if job["job_id"] != 2:
            return None
        return type(
            "Verification",
            (),
            {"as_dict": lambda self: {"dataset_name": "index_daily"}},
        )()


def test_reconciler_promotes_transport_and_queues_coverage(monkeypatch):
    jobs = [
        {
            "job_id": 1,
            "parameters": {
                "schedule_id": "stock_basic_daily",
                "scheduled_for": "2026-09-08T08:30:00+08:00",
            },
            "rows_fetched": 5897,
        },
        {
            "job_id": 2,
            "parameters": {
                "schedule_id": "index_daily_finalize",
                "scheduled_for": "2026-09-08T09:35:00+08:00",
            },
            "rows_fetched": 9206,
        },
        {
            "job_id": 3,
            "parameters": {
                "schedule_id": "index_dailybasic_daily",
                "scheduled_for": "2026-09-08T16:10:00+08:00",
            },
            "rows_fetched": 0,
        },
    ]
    repository = FakeRepository(jobs)
    monkeypatch.setattr(
        "service.collection_jobs.scheduled_reconciliation.verify_scheduled_transport",
        lambda schedule_id, *_args: {"verified": True}
        if schedule_id == "stock_basic_daily"
        else None,
    )

    result = ScheduledCompletionReconciler(
        repository=repository, planner=FakePlanner()
    ).reconcile(limit=50)

    assert result == {"promoted": 1, "audits_queued": 1}
    assert repository.promoted[0][0] == 1
    assert repository.queued == [(2, {"dataset_name": "index_daily"})]
