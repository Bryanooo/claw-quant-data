from dataclasses import replace
from datetime import datetime, date, time
from zoneinfo import ZoneInfo

import pytest

from scripts.audit_capability_coverage import select_scope, sanitized
from service.data_coverage.registry import COVERAGE_RULES
from service.clock import business_time
from service.orchestration_v2.scheduling import dispatch_closed_calendar_events
from service.orchestration_v2.audit_runtime import TaskAuditRuntime, TaskAuditPublicationDeferred
from service.orchestration_v2.contracts import TaskDefinitionDocument
from service.data_coverage.models import CoverageAuditResult
from tests.test_orchestration_v2 import acquisition_definition
from tests.test_orchestration_v2_audit_runtime import FakeRegistry, FakeRule


def test_weekly_acquisition_does_not_claim_an_unclosed_week_is_missing():
    now = datetime(2026, 11, 10, 21, tzinfo=ZoneInfo('Asia/Shanghai'))
    rule = COVERAGE_RULES.get('moneyflow_dc')
    start, end = select_scope(rule, now, cadence='weekly')
    assert end == date(2026, 11, 8)
    assert start == date(2026, 10, 10)


def test_snapshot_inspects_due_week_instead_of_an_old_successful_attempt():
    now = datetime(2026, 11, 10, 21, tzinfo=ZoneInfo('Asia/Shanghai'))
    rule = replace(COVERAGE_RULES.get('stock_basic'))
    old = {'observation_start': date(2026, 10, 19), 'observation_end': date(2026, 10, 25)}
    assert select_scope(rule, now, latest=old, cadence='weekly') == (date(2026, 11, 2), date(2026, 11, 8))


def test_review_drops_credentials_from_nested_error_contexts():
    assert sanitized({'Authorization': 'private', 'error': {'api_key': 'private', 'reason': 'timeout'}}) == {
        'error': {'reason': 'timeout'}}


def test_chunked_review_preserves_a_failed_day_as_unverified(monkeypatch):
    import scripts.audit_capability_coverage as audit
    probes = iter([
        {'status': 'gaps', 'expected': 1, 'present': 0, 'missing': 1, 'partial': 0,
         'issue_counts': {'missing_partition': 1}, 'seconds': .1},
        {'status': 'verification_timeout', 'start': date(2026, 11, 10), 'seconds': 1},
    ])
    monkeypatch.setattr(audit, 'fresh_probe', lambda *a: next(probes))
    now = datetime(2026, 11, 10, 21, tzinfo=ZoneInfo('Asia/Shanghai'))
    result = audit.daily_chunk_probe(object(), {'dataset': 'stock_daily'},
                                    {'cadence': 'daily'}, now, 2)
    assert result['status'] == 'verification_incomplete'
    assert result['missing'] == 1
    assert result['issue_counts'] == {'missing_partition': 1}
    assert result['failed_scans'] == [{'start': date(2026, 11, 10), 'status': 'verification_timeout'}]


def test_independent_intraday_worker_counts_current_slots_and_keeps_gaps():
    from contextlib import contextmanager
    from scripts.audit_capability_coverage import intraday_review
    class Cursor:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def execute(self,*a): pass
        def fetchall(self): return next(self.results)
        results = iter([
            [{'cal_date':date(2026,11,d)} for d in (4,5,6,9,10)],
            [{'scheduled_for':datetime(2026,11,10,9,30,tzinfo=ZoneInfo('Asia/Shanghai')),
              'status':'attention','trigger_source':'schedule'}]])
    class Connection:
        def cursor(self,**kw): return Cursor()
    class Repo:
        @contextmanager
        def _connection(self): yield Connection()
    result = intraday_review(Repo(),datetime(2026,11,10,21,tzinfo=ZoneInfo('Asia/Shanghai')))
    assert result['expected_slots'] == 80
    assert result['recorded_slots'] == 1
    assert len(result['missing_slots']) == 79
    assert result['status_counts'] == {'attention':1}


def test_reports_include_weekends_and_wait_for_final_same_day_release():
    class Store:
        def __init__(self): self.requests = []
        def active_task_keys(self): return {'report_rc'}
        def create_execution(self, request):
            self.requests.append(request)
            return {}, True
    before, after = Store(), Store()
    with business_time('2026-11-10T21:00:00+08:00'):
        dispatch_closed_calendar_events(date(2026, 11, 10), repository=before)
    assert len(before.requests) == 7
    assert {r.observation_start.weekday() for r in before.requests} >= {5, 6}
    assert all(r.observation_end < date(2026, 11, 10) for r in before.requests)
    with business_time('2026-11-10T23:15:00+08:00'):
        dispatch_closed_calendar_events(date(2026, 11, 10), repository=after)
    assert len(after.requests) == 8
    assert after.requests[0].idempotency_key == 'v2:daily:report_rc:2026-11-10'


def test_early_publication_validation_defers_without_spending_retry_budget():
    rule = FakeRule()
    rule.release_after = time(22, 30)
    day = date(2026, 11, 10)
    runtime = TaskAuditRuntime(repository=object(), registry=FakeRegistry(rule))
    class Calculator:
        def audit(self, *a, **kw):
            return CoverageAuditResult(
                dataset_name=rule.dataset_name, strategy='calendar_daily',
                start_date=day, end_date=day, status='empty', expected_partitions=0,
                present_partitions=0, missing_partitions=0, observed_partitions=0,
                coverage_ratio=None, partitions=(),
                evidence={'before_release': True, 'calendar_complete_for_range': True})
    runtime._calculator = Calculator()
    with pytest.raises(TaskAuditPublicationDeferred) as exc:
        runtime.audit_output(TaskDefinitionDocument.model_validate(acquisition_definition()),
            dataset_name=rule.dataset_name, observation_key=str(day), start_date=day, end_date=day,
            as_of=datetime(2026, 11, 10, 21, tzinfo=ZoneInfo('Asia/Shanghai')))
    assert exc.value.defer_without_failure
    assert exc.value.retry_after_seconds == 5401


def test_report_release_recovers_an_older_early_failure_under_one_stable_key():
    class Store:
        def __init__(self): self.requests = []
        def active_task_keys(self): return {'report_rc'}
        def create_execution(self, request):
            self.requests.append(request)
            if request.idempotency_key.startswith('v2:daily:'):
                return {'task_execution_id': 7, 'status': 'attention',
                        'final_error_message': 'TaskAuditNoMatureExpectedPartitionError'}, False
            return {}, True
    store = Store()
    with business_time('2026-11-10T23:15:00+08:00'):
        dispatch_closed_calendar_events(date(2026, 11, 10), repository=store, lookback=1)
    recovery = [r for r in store.requests if r.idempotency_key.startswith('v2:publication-recovery:')]
    assert len(recovery) == 2
    assert recovery[0].idempotency_key == 'v2:publication-recovery:report_rc:2026-11-10'
    assert all(r.frozen_scope['publication_recovery_for'] == 7 for r in recovery)
