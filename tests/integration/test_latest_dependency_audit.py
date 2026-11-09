import os
from contextlib import contextmanager

import psycopg2.extras
import pytest

from service.data_coverage.registry import COVERAGE_RULES
from service.db import get_conn
from service.orchestration_v2.repository import OrchestrationV2Repository


@pytest.mark.skipif(os.getenv('RUN_DB_INTEGRATION') != '1',reason='requires PostgreSQL')
def test_latest_failed_or_obsolete_or_cancelled_dependency_never_falls_back_to_old_ready():
    conn=get_conn()
    class Cursor(psycopg2.extras.RealDictCursor):
        def execute(self,statement,params=None):
            statement=statement.replace('orchestration_v2.dataset_state','pg_temp.input_state').replace('orchestration_v2.task_execution','pg_temp.input_execution')
            return super().execute(statement,params)
    class Connection:
        def cursor(self,**kwargs): return conn.cursor(cursor_factory=Cursor)
    class Repository(OrchestrationV2Repository):
        @contextmanager
        def _connection(self): yield Connection()
    repo=Repository();version=COVERAGE_RULES.get('stock_daily').revision
    try:
        with conn.cursor() as cur:
            cur.execute('''CREATE TEMP TABLE input_state(dataset_state_id bigint,dataset_name text,observation_key text,
                observation_start date,observation_end date,revision int,source_execution_id bigint,published_at timestamptz,
                updated_at timestamptz,ready boolean,contract_version text,scope jsonb,data_status text);
                CREATE TEMP TABLE input_execution(task_execution_id bigint,status text);
                CREATE TEMP TABLE sys_data_coverage_partition(dataset_name text,partition_date date,expected boolean,status text,audit_id bigint);
                CREATE TEMP TABLE sys_data_coverage_audit(audit_id bigint,evidence jsonb);
                INSERT INTO input_execution VALUES (1,'success');''')
            cur.execute("INSERT INTO input_state VALUES (1,'stock_daily','2026-10-30','2026-10-30','2026-10-30',1,1,now(),now(),true,%s,'{}','complete')",(f'coverage-rule:{version}',))
            def ready(): return bool(repo.ready_input_states(('stock_daily',),'2026-10-30'))
            assert ready()
            cur.execute('INSERT INTO input_state SELECT 2,dataset_name,observation_key,observation_start,observation_end,2,1,now(),now(),false,contract_version,scope,\'gaps\' FROM input_state')
            assert not ready()
            cur.execute("UPDATE input_state SET ready=true,data_status='complete',contract_version='legacy-no-audit' WHERE revision=2")
            assert not ready()
            cur.execute('UPDATE input_state SET contract_version=%s WHERE revision=2',(f'coverage-rule:{version-1}',))
            assert not ready()
            cur.execute('UPDATE input_state SET contract_version=%s WHERE revision=2',(f'coverage-rule:{version}',))
            assert ready()
            assert repo.latest_common_ready_input_states(('stock_daily',))
            cur.execute("UPDATE input_execution SET status='cancelled'")
            assert not ready()
            assert not repo.latest_common_ready_input_states(('stock_daily',))
    finally:
        conn.rollback();conn.close()
