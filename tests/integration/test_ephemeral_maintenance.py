from contextlib import contextmanager
import os

import pytest

from service.db import get_conn
from service import maintenance

pytestmark = pytest.mark.skipif(os.getenv('RUN_DB_INTEGRATION') != '1', reason='isolated PostgreSQL required')


def test_only_expired_operational_records_are_pruned(monkeypatch):
    conn = get_conn()
    class Transaction:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def cursor(self): return conn.cursor()
        def close(self): pass
    monkeypatch.setattr(maintenance, 'get_conn', Transaction)
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TEMP TABLE ant_query_cache(cache_key text PRIMARY KEY,response jsonb,expires_at timestamptz);
                INSERT INTO ant_query_cache VALUES('expired','{}',now()-interval '1 second'),('live','{}',now()+interval '1 day');
                CREATE TEMP TABLE ant_scheduled_checkpoint(request_hash text PRIMARY KEY,observed_at timestamptz);
                INSERT INTO ant_scheduled_checkpoint VALUES('expired',now()-interval '15 days'),('recent',now()-interval '8 days');
                CREATE TEMP TABLE sys_service_heartbeat(component text,instance_id text,last_seen_at timestamptz);
                INSERT INTO sys_service_heartbeat VALUES('worker','old',now()-interval '8 days'),('worker','live',now());
                CREATE TEMP TABLE ant_request_budget(id int); INSERT INTO ant_request_budget VALUES(1);
            """)
        result = maintenance.prune_ephemeral_state()
        assert result == {'expired_query_cache': 1, 'expired_scheduled_checkpoints': 1, 'expired_process_heartbeats': 1}
        with conn.cursor() as cursor:
            cursor.execute('SELECT cache_key FROM ant_query_cache'); assert cursor.fetchone() == ('live',)
            cursor.execute('SELECT request_hash FROM ant_scheduled_checkpoint'); assert cursor.fetchone() == ('recent',)
            cursor.execute('SELECT instance_id FROM sys_service_heartbeat'); assert cursor.fetchone() == ('live',)
            cursor.execute('SELECT count(*) FROM ant_request_budget'); assert cursor.fetchone() == (1,)
    finally:
        conn.rollback()
        conn.close()
