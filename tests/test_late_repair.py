from datetime import datetime
from zoneinfo import ZoneInfo

from service.orchestration_v2.late_repair import (
    LATE_PUBLISHED_DATASETS,
    next_late_repair_at,
)


TZ = ZoneInfo("Asia/Shanghai")


def test_stock_factor_market_request_and_coverage_are_consistent():
    from service.tushare_policy import TusharePolicyRegistry
    from service.data_coverage.registry import COVERAGE_RULES
    for name in ('stk_factor', 'stk_factor_pro'):
        assert TusharePolicyRegistry().get(name).page_size == 6000
        rule = COVERAGE_RULES.get(name)
        assert (rule.entity_reference, rule.min_entity_ratio, rule.revision) == ('stock_daily', 1.0, 7)


def test_next_late_repair_uses_the_nearest_post_close_window():
    assert next_late_repair_at(datetime(2026, 10, 1, 13, 55, tzinfo=TZ)) == (
        datetime(2026, 10, 1, 15, 58, tzinfo=TZ)
    )
    assert next_late_repair_at(datetime(2026, 10, 1, 19, 0, tzinfo=TZ)) == (
        datetime(2026, 10, 1, 21, 58, tzinfo=TZ)
    )
    assert next_late_repair_at(datetime(2026, 10, 1, 23, 59, tzinfo=TZ)) == (
        datetime(2026, 10, 2, 15, 58, tzinfo=TZ)
    )


def test_progressively_published_factor_snapshots_are_repaired():
    assert {
        "fund_factor_pro",
        "stk_factor",
        "stk_factor_pro",
    } <= LATE_PUBLISHED_DATASETS


def test_late_index_repairs_select_published_dataset_keys():
    from service.orchestration_v2.gap_repair import dataset_task_map

    owners = dataset_task_map()
    for dataset, task in [('industry_daily', 'ths_daily'), ('index_daily', 'index_daily')]:
        assert dataset in LATE_PUBLISHED_DATASETS
        assert owners[dataset] == task
def test_overdue_empty_recheck_skips_spent_and_only_selects_exact_days(monkeypatch):
    from datetime import date
    from types import SimpleNamespace
    import service.orchestration_v2.gap_repair as repair
    day = date(2026, 10, 20)
    def proposal(task, reason):
        return SimpleNamespace(task_key=task, observation_key=str(day),
                               observation_start=day, observation_end=day, reasons=(reason,))
    spent, eligible, other = (proposal('fx_daily','recheck_empty'),
                              proposal('hk_hold','recheck_empty'),proposal('kpl_list','partial'))
    def plan(repo, **kwargs):
        assert kwargs['end_date'] == date(2026, 10, 26)
        assert 'forex_daily' in kwargs['included_datasets']
        return (spent, eligible, other)
    def create(repo, **kwargs):
        assert list(kwargs['proposals']) == [eligible]
        assert kwargs['purpose'] == 'backfill' and kwargs['limit'] == 16
        assert kwargs['idempotency_prefix'] == 'v2:overdue-empty:v1'
        return {'created': 1}
    monkeypatch.setattr(repair, 'plan_current_repairs', plan)
    monkeypatch.setattr(repair, 'create_repair_executions', create)
    repo = SimpleNamespace(overdue_empty_attempts=lambda tasks: {('fx_daily', str(day))})
    assert repair.dispatch_overdue_empty_rechecks(repo, date(2026,11,3))['created'] == 1
