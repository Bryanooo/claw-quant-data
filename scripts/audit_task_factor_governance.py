#!/usr/bin/env python3
"""Read-only task, stored-factor and coverage-evidence inventory.

This is a point-in-time diagnostic, never a substitute for fresh coverage jobs.
No upstream calls, repair scheduling, secret configuration or frozen requests.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from psycopg2.extras import RealDictCursor
from service.db import get_conn
from service.data_coverage.registry import COVERAGE_RULES
from service.research.local_factors.ownership import SHARED_TECHNICAL_FIELDS, TECHNICAL_ALIASES
from service.research.local_factors.catalog import FACTOR_SCHEMA_VERSION


def scan():
    conn = get_conn()
    conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            def rows(sql, args=None):
                cur.execute(sql, args)
                return [dict(row) for row in cur.fetchall()]
            tasks = rows("""SELECT task_definition_id, task_key, version, workflow_kind,
                lifecycle_status, definition->'scope_contract'->>'cadence' AS cadence,
                definition->'trigger' AS trigger,
                definition->'input_datasets' AS inputs, definition->'output_datasets' AS outputs,
                definition->'nodes' AS nodes
                FROM orchestration_v2.task_definition WHERE lifecycle_status IN ('active','draft')
                ORDER BY workflow_kind,task_key,version""")
            # Node parameters may contain future connector secrets. Only expose
            # executable identities, never serialized configuration wholesale.
            for task in tasks:
                task['nodes'] = [{key: node.get(key) for key in ('key','kind','handler_key')}
                                 for node in (task['nodes'] or [])]
                task.pop('trigger', None)
            dates = rows("""SELECT schema_version,trade_date,count(*) AS rows,
                count(*) FILTER(WHERE audit_status='ready') AS ready,
                count(*) FILTER(WHERE audit_status='partial') AS partial,
                count(*) FILTER(WHERE audit_status='not_expected') AS not_expected,
                count(*) FILTER(WHERE technical_audit_status='partial') AS technical_partial
                FROM local_factor_snapshot GROUP BY 1,2 ORDER BY 1,2""")
            factor_start = COVERAGE_RULES.get('local_factor_snapshot').availability_start
            missing_factor_securities = rows("""SELECT d.trade_date,count(*) AS missing_security_rows
                FROM daily d WHERE d.trade_date >= %s AND NOT EXISTS (
                    SELECT 1 FROM local_factor_snapshot s WHERE s.schema_version=%s
                      AND s.trade_date=d.trade_date AND s.ts_code=d.ts_code)
                GROUP BY d.trade_date ORDER BY d.trade_date""", (factor_start, FACTOR_SCHEMA_VERSION))
            unresolved = rows("""SELECT problem.key AS factor,problem.value AS reason,count(*) AS security_dates
                FROM local_factor_snapshot s
                CROSS JOIN LATERAL jsonb_each_text(COALESCE(s.audit_evidence->'unresolved','{}'::jsonb)) problem
                WHERE schema_version=%s GROUP BY 1,2 ORDER BY 3 DESC,1,2""", (FACTOR_SCHEMA_VERSION,))
            duplicate = rows("""SELECT count(*) AS checked_rows,
                count(*) FILTER(WHERE technical_values ?| %s) AS duplicate_shared_storage_rows
                FROM local_factor_snapshot""", (list(SHARED_TECHNICAL_FIELDS) + list(TECHNICAL_ALIASES),))
            coverage = rows("""SELECT DISTINCT ON(dataset_name) dataset_name,status,start_date,end_date,
                missing_partitions,partial_partitions,finished_at
                FROM sys_data_coverage_audit ORDER BY dataset_name,finished_at DESC NULLS LAST,audit_id DESC""")
            pending = rows("""SELECT task_execution_id,task_key,status,observation_start,observation_end
                FROM orchestration_v2.task_execution
                WHERE status IN ('queued','running','retrying','waiting_dependency','validating','publishing')
                ORDER BY task_execution_id""")
            return dict(generated_at=datetime.now(timezone.utc).isoformat(),
                        acceptance='not_final', scope='stored rows and latest persisted audit evidence',
                        task_counts=dict(Counter(f"{t['workflow_kind']}:{t['lifecycle_status']}" for t in tasks)),
                        tasks=tasks, factor_dates=dates, unresolved_factor_inputs=unresolved,
                        factor_contract_start=factor_start,
                        missing_factor_security_dates=missing_factor_securities,
                        registered_shared_storage_check=duplicate[0],
                        coverage_evidence=coverage, pending_executions=pending,
                        limitations=['Existing audit timestamps must be checked before final acceptance.',
                                     'Shared storage check does not prove algebraic uniqueness of all formulas.',
                                     'Missing upstream values are not automatically non-applicable.'])
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = scan()
    text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + '\n', encoding='utf-8')
        print(json.dumps({'output': str(args.output.resolve()), 'task_counts': report['task_counts'],
                          'factor_dates': len(report['factor_dates']),
                          'coverage_datasets': len(report['coverage_evidence']),
                          'pending_executions': len(report['pending_executions']),
                          'acceptance': report['acceptance']}, ensure_ascii=False))
    else:
        print(text)
