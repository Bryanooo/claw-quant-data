"""Route every audited missing security/date to a bounded V2 repair, without overlap."""
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service.db import query
from service.orchestration_v2.repository import OrchestrationV2Repository
from service.orchestration_v2.gap_repair import create_repair_executions
from service.orchestration_v2.repair_planning import RepairInstanceProposal


def plan_month(days, active):
    """Split at active scope boundaries, so a union never re-fetches an active pair."""
    if not days:
        return []
    lower = date.fromisoformat(days[0]['trade_date'])
    upper = date.fromisoformat(days[-1]['trade_date']) + timedelta(days=1)
    cuts = {lower, upper}
    for scope in active:
        for bound in (scope['observation_start'], scope['observation_end'] + timedelta(days=1)):
            if lower < bound < upper:
                cuts.add(bound)
    result = []
    for start, stop in zip(sorted(cuts), sorted(cuts)[1:]):
        codes, missing = set(), 0
        for day in days:
            dt = date.fromisoformat(day['trade_date'])
            if not start <= dt < stop:
                continue
            uncovered = set(day['missing_codes'])
            for scope in active:
                if scope['observation_start'] <= dt <= scope['observation_end']:
                    selected = scope.get('fanout_values')
                    uncovered.difference_update(selected if selected is not None else uncovered.copy())
            codes.update(uncovered)
            missing += len(uncovered)
        if codes:
            result.append((start, stop - timedelta(days=1), sorted(codes), missing))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--not-before', type=datetime.fromisoformat)
    args = parser.parse_args()
    active = query("""SELECT task_execution_id,observation_start,observation_end,
        frozen_scope->'fanout_values' AS fanout_values
        FROM orchestration_v2.task_execution WHERE task_key='cyq_chips'
        AND status IN ('queued','created','running','retrying','waiting_dependency','validating','publishing')
        AND observation_start IS NOT NULL AND observation_end IS NOT NULL""")
    repo = OrchestrationV2Repository()
    report = {'generated_at':datetime.now(timezone.utc).isoformat(), 'applied':args.apply,
              'active_instances':active, 'audited_months':0, 'audited_days':0,
              'missing_security_dates':0, 'newly_routed_security_dates':0, 'repairs':[],
              'provider_unavailable_confirmed':[], 'acceptance':'not_complete'}
    for path in sorted(args.audit_dir.glob('*.json'), reverse=True):
        raw = path.read_bytes(); audit = json.loads(raw)
        if 'days' not in audit:
            continue
        days = sorted(audit['days'], key=lambda d:d['trade_date'])
        report['audited_months'] += 1
        report['audited_days'] += len(days)
        report['missing_security_dates'] += sum(len(d['missing_codes']) for d in days)
        for start,end,codes,missing in plan_month(days, active):
            entry = {'start':start,'end':end,'securities':len(codes),
                     'missing_security_dates':missing, 'audit_file':str(path),
                     'audit_sha256':hashlib.sha256(raw).hexdigest()}
            if args.apply:
                proposal = RepairInstanceProposal(task_key='cyq_chips',
                    observation_key=f'fanout-history:{start}:{end}',
                    observation_start=start, observation_end=end,
                    observation_period=f'{start}..{end}',datasets=('cyq_chips',),
                    reasons=('security_audit_revision_3_missing',))
                result = create_repair_executions(repo, proposals=(proposal,),
                    purpose='repair' if start >= date(2024,9,6) else 'backfill',
                    idempotency_prefix='v2:chip-security-full-history:v3',
                    frozen_scope_extra={'fanout_values':codes,
                        'recovery_scope':'bounded_fanout_history','max_window_days':31,
                        'history_order':'newest_first','security_audit_sha256':entry['audit_sha256'],
                        'missing_security_dates':missing})
                entry['execution_id'] = result['first_execution_id']
                entry['created'] = result['created']
                if args.not_before and result['created']:
                    with repo._connection() as conn, conn.cursor() as cur:
                        cur.execute("""UPDATE orchestration_v2.task_execution SET eligible_at=%s,
                            updated_at=NOW() WHERE task_execution_id=%s AND status='queued'""",
                            (args.not_before, entry['execution_id']))
            report['repairs'].append(entry)
            report['newly_routed_security_dates'] += missing
    report['already_active_security_dates'] = report['missing_security_dates'] - report['newly_routed_security_dates']
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str))
    print(json.dumps({k:v for k,v in report.items() if k not in {'repairs','active_instances'}},default=str))
    print('bounded_repair_windows',len(report['repairs']))


if __name__ == '__main__':
    main()
