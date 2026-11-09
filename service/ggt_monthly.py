"""Database-only monthly Connect totals, guarded by whole-month source proof."""
from calendar import monthrange
from datetime import date
from decimal import Decimal

from psycopg2.extras import RealDictCursor

from service.db import get_conn

INPUT_FIELDS = ('buy_amount', 'buy_volume', 'sell_amount', 'sell_volume')
OUTPUT_FIELDS = ('day_buy_amt', 'day_buy_vol', 'day_sell_amt', 'day_sell_vol',
                 'total_buy_amt', 'total_buy_vol', 'total_sell_amt', 'total_sell_vol')


class GgtMonthlySourceError(ValueError):
    """Persisted source observations cannot form a valid month."""
    retryable = False


def month_bounds(day):
    return day.replace(day=1), day.replace(day=monthrange(day.year, day.month)[1])


def aggregate_month(rows, day):
    start, end = month_bounds(day)
    if not rows:
        raise GgtMonthlySourceError('ggt_monthly: no source observations')
    seen, columns = set(), {field: [] for field in INPUT_FIELDS}
    for row in rows:
        source_date = row['trade_date']
        if source_date in seen or not start <= source_date <= end:
            raise GgtMonthlySourceError('ggt_monthly: duplicate or out-of-month source date')
        seen.add(source_date)
        for field in INPUT_FIELDS:
            if row.get(field) is None:
                raise GgtMonthlySourceError(f'ggt_monthly: missing source {field} at {source_date}')
            value = Decimal(str(row[field]))
            if not value.is_finite() or value < 0:
                raise GgtMonthlySourceError(f'ggt_monthly: invalid source {field} at {source_date}')
            columns[field].append(value)
    totals = [sum(columns[field]) for field in INPUT_FIELDS]
    values = [value / len(rows) for value in totals] + totals
    return {'month': start.strftime('%Y%m'), **dict(zip(OUTPUT_FIELDS, values))}


def source_audit(day, repository=None):
    from service.data_coverage.calculator import CoverageCalculator
    from service.data_coverage.registry import COVERAGE_RULES
    from service.data_coverage.repository import CoverageRepository
    start, end = month_bounds(day)
    from dataclasses import replace
    from service.data_coverage.models import CoverageStrategy
    repo = repository or CoverageRepository()
    calculator = CoverageCalculator(repo)
    rule = COVERAGE_RULES.get('ggt_daily')
    audit = calculator.audit(rule, start, end)
    scope = audit.evidence.get('declared_scope_evidence') or {}
    if (audit.status != 'unverified' or audit.partial_partitions
            or scope.get('active_jobs') or scope.get('unresolved_failures')):
        return audit
    # Daily requests need not cover weekends/holidays. Both full calendars
    # must be available, and each potentially open Connect session (plus any
    # extra observed day) needs its own verified result.
    markets = []
    for exchange in ('SSE', 'HK'):
        lo, hi, n = repo.calendar_coverage(exchange, start, end)
        if not lo or not hi or lo > start or hi < end or n != (end-start).days + 1:
            return audit
        markets.append(set(repo.expected_market_partitions(
            replace(rule, strategy=CoverageStrategy.TRADING_DAILY, calendar_exchange=exchange), start, end)))
    sessions = set.intersection(*markets) | {p.partition_date for p in audit.partitions}
    if not sessions or not audit.observed_partitions:
        return audit
    for session in sorted(sessions):
        one = calculator.audit(rule, session, session)
        if one.status not in {'complete','empty'}:
            return replace(audit, evidence={**audit.evidence,'first_unverified_connect_session':str(session)})
    return replace(audit, status='complete', coverage_ratio=1.0,
                   evidence={**audit.evidence, 'scope_basis':'verified_connect_sessions',
                             'verified_session_count':len(sessions)})


def materialize_ggt_monthly(observation_date: date, *, source_execution_id=None):
    from service.clock import business_today
    from service.data_coverage.diagnostics import audit_issues
    start, end = month_bounds(observation_date)
    if observation_date != end or end >= business_today():
        raise ValueError('ggt_monthly requires a closed full calendar month')
    audit = source_audit(observation_date)
    if audit.status != 'complete':
        return {'dataset': 'ggt_monthly', 'status': 'partial', 'publishable': False, 'rows_written': 0,
                'reasons': {'ggt_daily': audit_issues(audit)}}
    conn = get_conn()
    try:
        conn.set_session(isolation_level='REPEATABLE READ')
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SET LOCAL statement_timeout=30000')
            cur.execute('SELECT trade_date,buy_amount,buy_volume,sell_amount,sell_volume '
                        'FROM ggt_daily WHERE trade_date BETWEEN %s AND %s ORDER BY trade_date',
                        (start, end))
            rows = list(cur.fetchall())
            output = aggregate_month(rows, end)
            fields = ('month', *OUTPUT_FIELDS)
            cur.execute('INSERT INTO ggt_monthly (' + ','.join(fields) + ') VALUES ('
                        + ','.join(['%s'] * len(fields)) + ') ON CONFLICT (month) DO UPDATE SET '
                        + ','.join(f'{field}=EXCLUDED.{field}' for field in OUTPUT_FIELDS),
                        tuple(output[field] for field in fields))
        conn.commit()
        return {'dataset': 'ggt_monthly', 'status': 'ready', 'publishable': True, 'rows_written': 1,
                'source_rows': len(rows), 'source_scope': [str(start), str(end)],
                'source_execution_id': source_execution_id}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
