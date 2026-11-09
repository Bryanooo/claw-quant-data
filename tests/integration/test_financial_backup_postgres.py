from datetime import date, datetime, timezone
import os
from uuid import uuid4

import pytest

from service.db import get_conn
from service.financial_backup_recovery import register_source, recover_batch

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.getenv('RUN_DB_INTEGRATION') != '1',reason='requires migrated PostgreSQL')]


def test_backup_recovery_preserves_cutoff_schema_latest_and_idempotence():
    conn = get_conn()
    code = 'TEST'+uuid4().hex[:12]
    digest = uuid4().hex + uuid4().hex
    try:
        available = register_source(conn,digest=digest,name='test.dump',size=10,
            created=datetime(2026,10,31,22,tzinfo=timezone.utc),
            completed=datetime(2026,10,31,23,tzinfo=timezone.utc))
        assert available == date(2026,11,2)
        row = dict(ts_code=code,end_date='2025-12-31',report_type='1',ann_date='2026-03-01',
                   revenue='123.4567',update_flag='1',created_at='2026-03-01 00:00:00')
        assert recover_batch(conn,'income',digest,[row]) == 1
        assert recover_batch(conn,'income',digest,[row]) == 0
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM income_as_of('2026-11-01',ARRAY[%s])", (code,))
            assert cur.fetchone() is None
            cur.execute("SELECT revenue,fin_exp_int_exp FROM income_as_of('2026-11-02',ARRAY[%s])", (code,))
            value,unknown_new_column = cur.fetchone()
            assert str(value) == '123.4567' and unknown_new_column is None
            cur.execute('SELECT * FROM income WHERE ts_code=%s',(code,))
            assert cur.fetchone() is None
            cur.execute('SELECT original_row FROM financial_backup_row WHERE backup_sha256=%s',(digest,))
            assert cur.fetchone()[0] == row
            # A later vendor correction wins only after its actual observation.
            cur.execute("""INSERT INTO income(ts_code,end_date,report_type,ann_date,revenue,update_flag)
                VALUES (%s,'2025-12-31',1,'2026-03-01',999,'1')""",(code,))
            cur.execute("CREATE TEMP TABLE backup_test_source (LIKE income) ON COMMIT DROP")
            cur.execute('INSERT INTO backup_test_source SELECT * FROM income WHERE ts_code=%s',(code,))
            cur.execute("SELECT archive_financial_batch('income','backup_test_source',true)")
            cur.execute("SELECT revenue FROM income_as_of('2026-11-02',ARRAY[%s])",(code,))
            assert cur.fetchone()[0] == value
            cur.execute('SELECT revenue FROM income WHERE ts_code=%s',(code,))
            assert cur.fetchone()[0] == 999
        with pytest.raises(ValueError,match='unknown schema'):
            recover_batch(conn,'income',digest,[dict(row,unreviewed_field=1)])
        with pytest.raises(ValueError,match='duplicate'):
            recover_batch(conn,'income',digest,[row,row])
    finally:
        conn.rollback()
        conn.close()
