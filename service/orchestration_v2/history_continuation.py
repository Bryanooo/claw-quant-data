"""Advance explicitly seeded chip history, one independently certified window at a time."""
from datetime import timedelta

from service.data_coverage.registry import COVERAGE_RULES
from service.orchestration_v2.gap_repair import create_repair_executions
from service.orchestration_v2.repair_planning import RepairInstanceProposal


def next_window(previous, *, boundary):
    if not previous or previous.get('status') != 'success' or not previous.get('certified'):
        return None
    end = previous['observation_start'] - timedelta(days=1)
    if end < boundary:
        return None
    return max(boundary, end - timedelta(days=30)), end


def advance_chip_history(repository):
    """Only explicit seeds opt in; failures, active work and missing proof stop advancement."""
    previous = repository.latest_chip_history_window()
    window = next_window(previous, boundary=COVERAGE_RULES.get('cyq_chips').availability_start)
    if window is None:
        return {'created': 0, 'reason': 'awaiting_certified_window_or_complete'}
    start, end = window
    proposal = RepairInstanceProposal(
        task_key='cyq_chips', observation_key=f'fanout-history:{start}:{end}',
        observation_start=start, observation_end=end,
        observation_period=f'{start}..{end}', datasets=('cyq_chips',),
        reasons=('certified_history_continuation',),
    )
    return create_repair_executions(
        repository, proposals=(proposal,), purpose='backfill',
        idempotency_prefix='v2:cyq-chips-history:v1',
        frozen_scope_extra={
            'recovery_scope': 'bounded_fanout_history',
            'history_order': 'newest_first', 'max_window_days': 31,
            'predecessor_execution_id': previous['task_execution_id'],
        },
    )
