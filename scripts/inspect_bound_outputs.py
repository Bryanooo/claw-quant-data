"""Read-only inventory of published output bindings and dated coverage evidence."""
from collections import Counter
from datetime import date, datetime, timezone
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from psycopg2 import sql
from service.db import get_conn, query
from service.data_service.registry import DATASETS
from service.data_coverage.registry import COVERAGE_RULES
from service.orchestration_v2.gap_repair import current_problem_partitions


def inspect(end, campaign_prefix=None):
    gaps = current_problem_partitions(end_date=end)
    specs = {s.name: s for s in DATASETS.list()}
    rules = {r.dataset_name: r for r in COVERAGE_RULES.list()}
    definitions = query("""
        SELECT task_key, workflow_kind, definition->'output_datasets' outputs,
          ARRAY(SELECT DISTINCT e.source_id FROM jsonb_array_elements_text(
                d.definition->'acquisition_endpoint_ids') i(id)
                JOIN orchestration_v2.acquisition_endpoint e
                ON e.acquisition_endpoint_id=i.id::bigint) sources
        FROM orchestration_v2.task_definition d WHERE lifecycle_status='active' ORDER BY task_key
    """, ())
    states = {r['dataset_name']: r for r in query("""
        SELECT DISTINCT ON(dataset_name) dataset_name,observation_end,ready,data_status,source_execution_id
        FROM orchestration_v2.dataset_state WHERE observation_end<=%s
        ORDER BY dataset_name,observation_end DESC,updated_at DESC
    """, (end,))}
    audits = {(r['dataset_name'],r['revision']):r for r in query("""
        WITH a AS MATERIALIZED (SELECT dataset_name, start_date,end_date,status,finished_at,
           COALESCE((evidence->>'rule_revision')::int,1) revision FROM sys_data_coverage_audit)
        SELECT DISTINCT ON(dataset_name,revision) * FROM a ORDER BY dataset_name,revision,finished_at DESC
    """, ())}
    rows = []
    with get_conn() as conn, conn.cursor() as cur:
        for d in definitions:
            for key in d['outputs']:
                spec, rule = specs.get(key), rules.get(key)
                present = None
                if spec:
                    cur.execute("SELECT to_regclass(%s)", (spec.table,))
                    if cur.fetchone()[0]:
                        cur.execute(sql.SQL("SELECT EXISTS(SELECT 1 FROM {})").format(sql.Identifier(spec.table)))
                        present = cur.fetchone()[0]
                dates = gaps.get(key, {})
                rows.append(dict(task=d['task_key'], kind=d['workflow_kind'], sources=d['sources'],
                    dataset=key, table=spec.table if spec else None, has_rows=present,
                    strict_mode=rule.strict_audit_mode if rule else None,
                    last_audit=audits.get((key,rule.revision)) if rule else None,
                    latest_state=states.get(key), counts=dict(Counter(dates.values())),
                    problems={str(k):v for k,v in sorted(dates.items())}))
    for row in rows:
        # Manifest-backed products do not promise a separate physical table.
        if row['dataset'] == 'factor_reference_sample':
            row['storage_kind'] = 'execution_manifest_and_reference_values'
            row['has_rows'] = None
        if row['kind'] == 'transformation' and row['table'] and row['dataset'] != 'ggt_monthly':
            with get_conn() as c, c.cursor() as cur:
                col = sql.Identifier(specs[row['dataset']].date_column)
                cur.execute(sql.SQL('select min({d}),max({d}),count(distinct {d}) from {t} where {d}<=%s')
                            .format(d=col,t=sql.Identifier(row['table'])),(end,))
                first,last,days=cur.fetchone()
                row['physical_date_span'] = dict(first=first,last=last,distinct_dates=days)
    campaign=query("""SELECT task_key,status,count(*) AS instances,
            min(task_execution_id) first_id,max(task_execution_id) last_id
        FROM orchestration_v2.task_execution WHERE starts_with(idempotency_key,%s)
        GROUP BY task_key,status ORDER BY task_key,status""", (campaign_prefix,)) if campaign_prefix else []
    return dict(as_of=end, generated_at=datetime.now(timezone.utc), definitions=len(definitions),
                repair_campaign=campaign,outputs=rows,
                note="Observed rows or no flagged partitions do not certify all historical dates.")


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--end', required=True, type=date.fromisoformat)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--campaign-prefix')
    args=parser.parse_args()
    report=json.dumps(inspect(args.end,args.campaign_prefix),default=str,ensure_ascii=False,indent=2)
    if args.output:
        args.output.write_text(report+'\n',encoding='utf-8')
    else:
        print(report)
