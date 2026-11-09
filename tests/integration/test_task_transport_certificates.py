"""Real SQL verification; all mutations are transaction-local temp fixtures."""
import os

from psycopg2.extras import Json
import pytest

from service.data_coverage.transport import certified_execution_sql
from service.db import get_conn


@pytest.mark.skipif(os.getenv('RUN_DB_INTEGRATION') != '1',reason='requires PostgreSQL')
def test_certificate_requires_entire_plan_and_discards_reset_and_bad_latest_proof():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE proof_execution(task_execution_id bigint,frozen_scope jsonb,task_key text DEFAULT 'daily')")
            cur.execute('CREATE TEMP TABLE proof_event(task_execution_id bigint,event_type text,sequence_number int,payload jsonb)')
            plan = {'requests':[{'request_key':'a'},{'request_key':'b'}]}
            cur.execute('INSERT INTO proof_execution VALUES (1,%s)',(Json(plan),))
            predicate = certified_execution_sql().replace('orchestration_v2.task_execution_event','pg_temp.proof_event')
            seq = 0
            def add(kind,payload):
                nonlocal seq
                seq += 1
                cur.execute('INSERT INTO proof_event VALUES (1,%s,%s,%s)',(kind,seq,Json(payload)))
            def proven():
                cur.execute('SELECT '+predicate+' FROM proof_execution execution')
                return cur.fetchone()[0]
            def request(key,**kwargs):
                add('node.acquire.request_completed',{'request_key':key,'completion_status':'complete',
                    'completion_evidence':{'verified':True,**kwargs}})
            assert not proven()
            request('a'); add('node.acquire.completed',{})
            assert not proven()
            request('b'); assert proven()
            request('b',normalization={'quarantined_rows':1}); assert not proven()
            request('b'); assert proven()
            add('execution.operator_retry',{'reset_data_nodes':True}); assert not proven()
            request('a'); request('b'); assert not proven()
            add('node.acquire.completed',{}); assert proven()
            request('a',skip_store=True); assert not proven()
            cur.execute("UPDATE proof_execution SET task_key='fina_mainbz'")
            request('a'); request('b'); assert not proven()
            request('a',mainbz_classifications_verified=True)
            request('b',mainbz_classifications_verified=True); assert proven()
            for bad in (None,{},'invalid',[],[{}],[{'request_key':'a'},{'request_key':'a'}]):
                cur.execute('UPDATE proof_execution SET frozen_scope=%s',(Json({'requests':bad}),))
                assert not proven()
    finally:
        conn.rollback(); conn.close()


@pytest.mark.skipif(os.getenv('RUN_DB_INTEGRATION') != '1',reason='requires PostgreSQL')
def test_new_partial_state_cannot_borrow_an_older_transport_certificate():
    from contextlib import contextmanager
    from datetime import date
    import psycopg2.extras
    from service.data_coverage.repository import CoverageRepository
    from service.data_coverage.registry import COVERAGE_RULES
    conn=get_conn()
    class Cursor(psycopg2.extras.RealDictCursor):
        def execute(self,statement,params=None):
            if isinstance(statement,str):
                statement=statement.replace('orchestration_v2.task_execution_event','pg_temp.audit_event').replace('orchestration_v2.task_execution','pg_temp.audit_execution').replace('orchestration_v2.dataset_state','pg_temp.audit_state')
            return super().execute(statement,params)
    class Connection:
        def cursor(self,**kwargs): return conn.cursor(cursor_factory=Cursor)
    class Repository(CoverageRepository):
        @contextmanager
        def _connection(self): yield Connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''CREATE TEMP TABLE ggt_daily(trade_date date);
                INSERT INTO ggt_daily VALUES ('2026-10-30');
                CREATE TEMP TABLE audit_execution(task_execution_id bigint,task_key text,status text,observation_start date,observation_end date,frozen_scope jsonb);
                CREATE TEMP TABLE audit_event(task_execution_id bigint,event_type text,sequence_number int,payload jsonb);
                CREATE TEMP TABLE audit_state(dataset_name text,observation_key text,observation_start date,data_status text,source_execution_id bigint,revision int,updated_at timestamptz,dataset_state_id bigint);
                INSERT INTO audit_state VALUES ('ggt_daily','2026-10-30','2026-10-30','partial',2,2,now(),2);''')
            for identifier in (1,2):
                cur.execute("INSERT INTO audit_execution VALUES (%s,'ggt_daily','attention','2026-10-30','2026-10-30',%s)",(identifier,Json({'requests':[{'request_key':'a'}]})))
            def certify(identifier):
                cur.execute("INSERT INTO audit_event VALUES (%s,'node.acquire.request_completed',1,%s),(%s,'node.acquire.completed',2,'{}')",(identifier,Json({'request_key':'a','completion_status':'complete','completion_evidence':{'verified':True}}),identifier))
            certify(1)
            repo=Repository();rule=COVERAGE_RULES.get('ggt_daily');day=date(2026,10,30)
            assert repo.actual_partitions(rule,day,day)[0].known_incomplete
            certify(2)
            assert not repo.actual_partitions(rule,day,day)[0].known_incomplete
    finally:
        conn.rollback();conn.close()
