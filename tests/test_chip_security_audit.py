from datetime import date

from service.data_coverage.chip_securities import summarize_day
from service.data_coverage.registry import COVERAGE_RULES
from service.orchestration_v2.audit_contracts import dataset_audit_contract


def test_chip_window_includes_midwindow_delistings(monkeypatch):
    from service.acquisition_runtime import fanout
    calls = []
    monkeypatch.setattr(fanout, 'query', lambda sql, params: calls.append(params) or [])
    start,end = date(2026,9,7),date(2026,9,18)
    fanout.list_fanout_values('stock', as_of=end, active_since=start)
    assert calls == [(end,end,start)]
    fanout.list_fanout_values('stock', as_of=end)
    assert calls[-1] == (end,end,end)


def test_chip_contract_requires_every_expected_security():
    assert COVERAGE_RULES.get('cyq_chips').min_entity_ratio == 1.0
    contract = dataset_audit_contract('cyq_chips')
    assert contract.min_entity_ratio == 1.0
    assert contract.rule_revision == 3


def test_absence_is_not_upstream_unavailable():
    result = summarize_day(dict(trade_date=date(2026,10,30), expected=100,
                                present=99, missing_codes=['000001.SZ']))
    assert result['status'] == 'missing'
    assert result['missing_codes'] == ['000001.SZ']
    assert result['provider_unavailable_confirmed'] == []


def test_empty_baseline_fails_closed_and_presence_is_not_full_acceptance():
    row = dict(trade_date=date(2026,10,30), expected=0, present=0, missing_codes=[])
    assert summarize_day(row)['status'] == 'baseline_unverified'
    row.update(expected=100,present=100)
    assert summarize_day(row)['status'] == 'security_presence_verified'


def test_99_percent_fails_coverage_and_missing_baseline_cannot_pass():
    from tests.test_data_coverage import FakeCoverageRepository
    from service.data_coverage.models import ActualPartition
    from service.data_coverage.calculator import CoverageCalculator
    day = date(2026,10,23)
    for expected in (100, None, 0):
        repo = FakeCoverageRepository(
            actual=[ActualPartition(day, 1000, 99)], expected=[day],
            expected_entities=expected,
        )
        result = CoverageCalculator(repo).audit(COVERAGE_RULES.get('cyq_chips'),
                                               day, day, as_of=date(2026,10,31))
        assert result.partial_partitions == 1
        assert result.present_partitions == 0


def test_old_chip_contract_only_migrates_to_stricter_rule():
    from service.orchestration_v2.audit_runtime import TaskAuditRuntime
    from tests.test_orchestration_v2_audit_runtime import FakeCalculator
    runtime = TaskAuditRuntime(repository=object())
    runtime._calculator = FakeCalculator()
    current = dataset_audit_contract('cyq_chips')
    old = current.model_copy(update={'rule_revision': 2, 'min_entity_ratio': .90})
    day = date(2026,10,23)
    result = runtime._audit_registered_dataset(old, day, day, date(2026,10,31), set(), set())
    assert result.status == 'gaps'
