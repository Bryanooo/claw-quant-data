"""Bounded retention of expired operational caches, never collection evidence."""
from service.db import get_conn


def prune_ephemeral_state(*, batch_size=10000):
    if not 1 <= batch_size <= 10000:
        raise ValueError('maintenance batch_size must be 1..10000')
    # Preserve raw data, request budgets, task receipts and audit certificates.
    statements = {
        'expired_query_cache': """WITH expired AS (
            SELECT cache_key FROM ant_query_cache WHERE expires_at<now()
            ORDER BY expires_at LIMIT %s FOR UPDATE SKIP LOCKED
        ) DELETE FROM ant_query_cache c USING expired e WHERE c.cache_key=e.cache_key""",
        'expired_scheduled_checkpoints': """WITH expired AS (
            SELECT request_hash FROM ant_scheduled_checkpoint
            WHERE observed_at<now()-interval '14 days'
            ORDER BY observed_at LIMIT %s FOR UPDATE SKIP LOCKED
        ) DELETE FROM ant_scheduled_checkpoint c USING expired e WHERE c.request_hash=e.request_hash""",
        'expired_process_heartbeats': """WITH expired AS (
            SELECT component,instance_id FROM sys_service_heartbeat
            WHERE last_seen_at<now()-interval '7 days'
            ORDER BY last_seen_at LIMIT %s FOR UPDATE SKIP LOCKED
        ) DELETE FROM sys_service_heartbeat c USING expired e
            WHERE c.component=e.component AND c.instance_id=e.instance_id""",
    }
    conn = get_conn()
    try:
        counts = {}
        with conn, conn.cursor() as cursor:
            cursor.execute('SET LOCAL lock_timeout=1000')
            cursor.execute('SET LOCAL statement_timeout=10000')
            for name, statement in statements.items():
                cursor.execute(statement, (batch_size,))
                counts[name] = cursor.rowcount
        return counts
    finally:
        conn.close()
