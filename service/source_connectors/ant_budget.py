"""Shared, fail-closed rolling seven-day subrequest budget and cache.

The unused 271 units are not a borrowing pool: expansion requires an explicit
allocation change. Failed/ambiguous network sends keep their reservation.
"""
from contextlib import contextmanager, closing
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
import hashlib
import json

import psycopg2
from psycopg2.extras import Json
from service.config import DB_CONFIG

LIMIT = 1000
CAPS = {'intraday':245, 'rankings':10, 'weekly':224, 'monthly_rotation':100,
        'research':150, 'backfill':0}
ORIGIN = ContextVar('ant_budget_origin', default='research')
LOCK = 391610310


def budget_snapshot(database):
    rows=database.fetch_all("""SELECT category,sum(units)::bigint AS units
        FROM ant_request_budget WHERE requested_at>NOW()-INTERVAL '7 days' GROUP BY category""")
    used={row['category']:int(row['units']) for row in rows}
    return {'window':'rolling_7_days_conservative','limit':LIMIT,'used':sum(used.values()),
            'remaining_hard_limit':max(0,LIMIT-sum(used.values())),
            'allocations':CAPS,'used_by_category':used,
            'reserved_for_intraday_expansion':LIMIT-sum(CAPS.values()),
            'borrowing_enabled':False,
            'control':database.fetch_one('SELECT blocked_until,reason FROM ant_budget_control WHERE singleton'),
            'note':'历史定时采集审计不完整；此计数不是供应商账单。缓存命中不扣额，失败不退款。'}


class AntBudgetDeferred(RuntimeError):
    defer_without_failure = True
    retry_after_seconds = 86400
    provider_error_code = 'QUOTA_EXCEEDED'


@contextmanager
def budget_scope(category):
    token = ORIGIN.set(category)
    try:
        yield
    finally:
        ORIGIN.reset(token)


def check_capacity(total, category_used, category, units):
    if units <= 0 or category not in CAPS:
        raise ValueError('invalid ant request allocation')
    if total + units > LIMIT or category_used + units > CAPS[category]:
        raise AntBudgetDeferred('蚂蚁滚动7天额度不足；保留盘中扩容储备，不自动借用或重试')


def reserve(payload):
    units=len(payload['requests']); category=ORIGIN.get()
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
    with closing(psycopg2.connect(**DB_CONFIG)) as conn, conn, conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(%s)',(LOCK,))
        cur.execute('SELECT blocked_until>NOW() FROM ant_budget_control WHERE singleton')
        if cur.fetchone()[0]:
            raise AntBudgetDeferred('蚂蚁上游额度熔断中，等待安全恢复窗口')
        cur.execute("""SELECT coalesce(sum(units),0),
            coalesce(sum(units) FILTER(WHERE category=%s),0)
            FROM ant_request_budget WHERE requested_at>NOW()-INTERVAL '7 days'""",(category,))
        total,used=cur.fetchone()
        check_capacity(total,used,category,units)
        cur.execute("""INSERT INTO ant_request_budget(category,units,request_hash)
            VALUES(%s,%s,%s) RETURNING request_id""",(category,units,digest))
        return cur.fetchone()[0]


def finish(request_id, status, http_status=None, *, quota_exhausted=False):
    with closing(psycopg2.connect(**DB_CONFIG)) as conn, conn, conn.cursor() as cur:
        cur.execute('UPDATE ant_request_budget SET status=%s,http_status=%s WHERE request_id=%s',
                    (status,http_status,request_id))
        if quota_exhausted:
            # Reset timezone/weekday is not yet independently established.
            cur.execute("""UPDATE ant_budget_control SET blocked_until=NOW()+INTERVAL '7 days',
                reason='provider_QUOTA_EXCEEDED_reset_unconfirmed' WHERE singleton""")


@contextmanager
def cached_directory(payload):
    """Single-flight, cross-process cache only for the low-volatility directory."""
    items=payload.get('requests',[])
    category=ORIGIN.get()
    directory=len(items)==1 and items[0].get('url')=='/api/v1/sector/plate-list'
    eligible=directory or category in {'weekly','monthly_rotation','rankings'}
    if not eligible:
        yield None, lambda response: None
        return
    today=datetime.now(timezone(timedelta(hours=8))).date()
    period = (today-timedelta(days=today.weekday())).isoformat() if category in {'weekly','monthly_rotation'} else today.isoformat()
    key=hashlib.sha256(json.dumps([payload,period],sort_keys=True).encode()).hexdigest()
    conn=psycopg2.connect(**DB_CONFIG)
    try:
        with conn, conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(%s)',(int(key[:15],16),))
            cur.execute('SELECT response FROM ant_query_cache WHERE cache_key=%s AND expires_at>NOW()',(key,))
            row=cur.fetchone()
            def save(response):
                results=response.get('results')
                if (response.get('status')=='SUCCESS' and isinstance(results,list)
                        and len(results)==len(items)
                        and all(isinstance(item,dict) and item.get('status','SUCCESS')=='SUCCESS'
                                for item in results)):
                    cur.execute("""INSERT INTO ant_query_cache VALUES(%s,%s,NOW()+INTERVAL '7 days')
                        ON CONFLICT(cache_key) DO UPDATE SET response=EXCLUDED.response,expires_at=EXCLUDED.expires_at""",
                        (key,Json(dict(response))))
            yield row[0] if row else None, save
    finally:
        conn.close()
