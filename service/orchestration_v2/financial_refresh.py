"""Refresh explicitly bounded financial periods while disclosures evolve.

Financial collectors require a report period and are therefore not generic
daily interfaces. A successful period fetch is a point-in-time observation,
not permission to skip all later disclosures for that quarter.
"""
from datetime import date, timedelta

from service.orchestration_v2.gap_repair import create_repair_executions
from service.orchestration_v2.repair_planning import RepairInstanceProposal


from service.orchestration_v2.automation_status import FINANCIAL_ROLLING_REFRESH_TASKS as FINANCIAL_TASKS


def recent_report_periods(as_of: date) -> tuple[date, date]:
    quarter_start = date(as_of.year, ((as_of.month - 1) // 3) * 3 + 1, 1)
    last = quarter_start - timedelta(days=1)
    prior_start = date(last.year, ((last.month - 1) // 3) * 3 + 1, 1)
    return last, prior_start - timedelta(days=1)


def refresh_financial_disclosures(as_of: date, repository):
    proposals = tuple(
        RepairInstanceProposal(
            task_key=task, observation_key=f'{end.year}-Q{end.month // 3}',
            observation_start=date(end.year, end.month - 2, 1),
            observation_end=end, observation_period=f'{end.year}-Q{end.month // 3}',
            datasets=(task,), reasons=('rolling_financial_disclosure_refresh',),
        )
        for end in recent_report_periods(as_of) for task in FINANCIAL_TASKS
    )
    return create_repair_executions(
        repository, proposals=proposals, purpose='daily', trigger_source='schedule',
        idempotency_prefix=f'v2:financial-disclosures:{as_of.isoformat()}',
        frozen_scope_extra={'force_acquire': True, 'disclosure_as_of': as_of.isoformat()},
    )
