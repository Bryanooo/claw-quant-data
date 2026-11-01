"""Explain recent residual gaps using stored provider responses, never infer exemptions."""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from service.db import query


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    missing={}
    for path in sorted(args.audit_dir.glob('*.json')):
        for day in json.loads(path.read_text()).get('days',[]):
            if '2024-09-06' <= day['trade_date'] < '2026-10-26':
                for code in day['missing_codes']:
                    missing.setdefault(code,[]).append(day['trade_date'])
    rows=query("""
        SELECT t.task_execution_id,
               coalesce(r->'parameters'->'parameters',r->'parameters') AS parameters,
               e.occurred_at,e.payload->>'rows_fetched' AS rows_fetched,
               e.payload->>'completion_status' AS completion_status,
               e.payload->'completion_evidence' AS completion_evidence
        FROM orchestration_v2.task_execution t
        CROSS JOIN LATERAL jsonb_array_elements(t.frozen_scope->'requests') r
        JOIN orchestration_v2.task_execution_event e
          ON e.task_execution_id=t.task_execution_id
         AND e.event_type='node.acquire.request_completed'
         AND e.payload->>'request_key'=r->>'request_key'
        WHERE t.task_key='cyq_chips' AND t.observation_end>='2024-09-06'
          AND coalesce(r->'parameters'->'parameters',r->'parameters')->>'ts_code'=ANY(%s)
        ORDER BY t.task_execution_id,e.occurred_at
    """,(list(missing),))
    evidence=[]
    for row in rows:
        params=row['parameters']; code=params['ts_code']
        start=params.get('start_date') or params.get('trade_date')
        end=params.get('end_date') or params.get('trade_date')
        dates=[d for d in missing[code] if start and end and start<=d.replace('-','')<=end]
        if not dates:
            continue
        evidence.append({**row,'missing_dates':dates,
            'reason':'provider_returned_empty' if int(row['rows_fetched'] or 0)==0 else 'provider_response_did_not_fill_expected_dates',
            'permanent_unavailability_confirmed':False,
            'exempt_from_completeness':False})
    args.output.write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),
        'scope':'residual missing dates 2024-09-06..2026-10-25',
        'missing_dates_by_security':missing,'responses':evidence,
        'conclusion':'Prior responses are evidence, not permanent unavailability or completeness.'},
        ensure_ascii=False,indent=2,default=str))
    print('securities',len(missing),'response_evidence',len(evidence))


if __name__=='__main__':
    main()
