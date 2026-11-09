"""Bounded daily group distributions with a separate SQL numerical check."""

from datetime import date, timedelta
from math import isclose

from psycopg2.extras import Json, RealDictCursor

from service.db import get_conn

GROUPS = ('000300.SH', '000688.SH')
FORMULA_VERSION = 'group-valuation-v2-sample-contract'


def distribution_publication(payload):
    """Certify the declared valid-sample distribution, not full numeric coverage.

    An observed source NULL stays unknown. Nonpositive ratios stay excluded.
    Missing securities, contradictory membership and unverified statistics block.
    """
    data, meta = payload["data"], payload["meta"]
    blockers = [w for w in meta["quality"]["warnings"]
                if w != "some metric inputs are missing"]
    for name, metric in data["metrics"].items():
        if metric["missing_member_rows"]:
            blockers.append(f"{name}:source_rows_missing")
        if metric.get("invalid_field_codes"):
            blockers.append(f"{name}:invalid_source_values")
        if metric["valid_count"] + len(metric["missing_codes"]) + len(metric["nonpositive_excluded_codes"]) != metric["population"]:
            blockers.append(f"{name}:population_accounting_mismatch")
        if metric["valid_count"] <= 0:
            blockers.append(f"{name}:no_valid_sample")
        if meta.get("numerical_check", {}).get(name+"_count_median") != "passed":
            blockers.append(f"{name}:independent_check_missing")
    return {
        "publishable": not blockers, "blockers": blockers,
        "certified_object": "same_date_valid_sample_distribution",
        "full_numeric_coverage": all(not m["missing_codes"] and not m["nonpositive_excluded_codes"]
                                     for m in data["metrics"].values()),
        "source_nulls": {n:m["unusable_field_codes"] for n,m in data["metrics"].items()},
        "domain_exclusions": {n:m["nonpositive_excluded_codes"] for n,m in data["metrics"].items()},
        "null_policy": "source NULL remains unknown; never zero or proof of no dividends",
    }


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

            repository = ResearchRepository(Database())
            service = ResearchService(None, repository)
            snapshots = {}
            ready = True
            for code in GROUPS:
                payload = service.group_valuation(code, trade_date=observation_date)
                # Only record corroboration from statements visible on that day.
                # A negative denominator is not proof of the vendor's null policy.
                metrics = payload['data']['metrics']
                for field, period in (
                    ('pe', date(observation_date.year-1,12,31)),
                    ('pe_ttm', date(observation_date.year,1+3*((observation_date.month-1)//3),1)-timedelta(days=1)),
                ):
                    codes = metrics[field]['unusable_field_codes']
                    inputs = repository.group_aggregate_inputs(codes,report_period=period,
                              as_of=observation_date) if codes else []
                    by_code = {r['ts_code']:r for r in inputs}
                    metrics[field]['denominator_check'] = {
                        'period': str(period), 'as_of': str(observation_date),
                        'by_security': {c: ('pit_profit_unavailable' if by_code.get(c,{}).get('net_income_ttm') is None
                                            else 'nonpositive_visible_profit' if by_code[c]['net_income_ttm'] <= 0
                                            else 'positive_visible_profit_vendor_value_missing') for c in codes},
                    }
                metrics['dv_ttm']['null_policy']='NULL is unknown, not evidence of zero dividends'
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
                for field in ('pe','pb','ps_ttm','dv_ttm'):
                    op = '>=' if field == 'dv_ttm' else '>'
                    cursor.execute(f"""SELECT count(d.{field}) AS valid,
                        percentile_cont(0.5) WITHIN GROUP (ORDER BY d.{field}) AS median
                        FROM tushare_current_daily_basic d JOIN tushare_current_index_weight w
                        ON w.con_code=d.ts_code WHERE d.trade_date=%s AND w.index_code=%s
                        AND w.trade_date=%s AND d.{field} {op} 0""",
                        (observation_date,code,payload['meta']['membership_date']))
                    check = cursor.fetchone()
                    metric = metrics[field]
                    if check['valid'] != metric['valid_count'] or (check['valid'] and
                            not isclose(float(check['median']),metric['median'],rel_tol=1e-10,abs_tol=1e-10)):
                        raise ValueError(f'independent {field} distribution check failed: {code}')
                    payload['meta']['numerical_check'][field+'_count_median']='passed'
                publication = distribution_publication(payload)
                payload["meta"]["publication"] = publication
                ready = ready and publication["publishable"]
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
                    if not payload['meta']['publication']['publishable']
                }}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
