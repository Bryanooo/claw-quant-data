"""Bounded daily group distributions with a separate SQL numerical check."""

from datetime import date
from math import isclose

from psycopg2.extras import Json, RealDictCursor

from service.db import get_conn

GROUPS = ('000300.SH', '000688.SH')
FORMULA_VERSION = 'group-valuation-v1'


def materialize_group_valuation(observation_date: date, *, source_execution_id=None):
    # Imports here avoid the research/service/transform registry import cycle.
    from service.research.repository import ResearchRepository
    from service.research.service import ResearchService

    connection = get_conn()
    try:
        connection.set_session(isolation_level='REPEATABLE READ')
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute('SET LOCAL statement_timeout=30000')
            cursor.execute('SELECT pg_advisory_xact_lock(107, %s)', (observation_date.toordinal(),))
            class Database:
                def fetch_all(self, query, params=None):
                    cursor.execute(query, params)
                    return [dict(row) for row in cursor.fetchall()]

            service = ResearchService(None, ResearchRepository(Database()))
            snapshots = {}
            ready = True
            for code in GROUPS:
                payload = service.group_valuation(code, trade_date=observation_date)
                cursor.execute("""
                    SELECT count(*) FILTER (WHERE d.pe_ttm>0) AS valid,
                           percentile_cont(0.5) WITHIN GROUP (ORDER BY d.pe_ttm)
                             FILTER (WHERE d.pe_ttm>0) AS median
                    FROM tushare_current_daily_basic d
                    JOIN tushare_current_index_weight w ON w.con_code=d.ts_code
                    WHERE d.trade_date=%s AND w.index_code=%s AND w.trade_date=%s
                """, (observation_date, code, payload['meta']['membership_date']))
                check = dict(cursor.fetchone())
                metric = payload['data']['metrics']['pe_ttm']
                equal = check['valid'] == metric['valid_count'] and (
                    check['median'] is None and metric['median'] is None or
                    check['median'] is not None and metric['median'] is not None and
                    isclose(float(check['median']), metric['median'], rel_tol=1e-10, abs_tol=1e-10))
                if not equal:
                    raise ValueError(f'independent PE distribution check failed: {code}')
                payload['meta']['numerical_check'] = {'pe_ttm_count_median': 'passed'}
                ready = ready and payload['meta']['quality']['status'] == 'computed'
                snapshots[code] = payload
            import json
            cursor.execute("""
                INSERT INTO valuation_percentile_snapshot
                  (trade_date,formula_version,audit_status,snapshots,source_execution_id)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (trade_date) DO UPDATE SET
                  formula_version=excluded.formula_version,audit_status=excluded.audit_status,
                  snapshots=excluded.snapshots,source_execution_id=excluded.source_execution_id,
                  computed_at=now()
            """, (observation_date, FORMULA_VERSION, 'ready' if ready else 'partial',
                  Json(snapshots, dumps=lambda x: json.dumps(x, default=str)), source_execution_id))
        connection.commit()
        return {'dataset': 'valuation_percentile_snapshot', 'rows_written': 1,
                'status': 'ready' if ready else 'partial', 'publishable': ready,
                'groups': list(GROUPS), 'formula_version': FORMULA_VERSION,
                'reasons': {
                    code: {'warnings': payload['meta']['quality']['warnings'],
                           'missing_fields': {field: len(metric['missing_codes'])
                                              for field, metric in payload['data']['metrics'].items()
                                              if metric['missing_codes']}}
                    for code, payload in snapshots.items()
                    if payload['meta']['quality']['status'] != 'computed'
                }}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
