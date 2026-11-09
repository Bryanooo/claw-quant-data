"""Transactional proof recovery tests against migrated real PostgreSQL."""
from datetime import date
import hashlib
import os
from uuid import uuid4

import pytest
import pandas as pd

from service.db import get_conn
from service.financial_filing_facts import persist_facts
from service.research.local_factors.materializer import _statement_rows

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.getenv('RUN_DB_INTEGRATION') != '1', reason='requires migrated PostgreSQL')]


@pytest.mark.parametrize('table,columns', [
    ('income', {'revenue':'revenue'}), ('balancesheet', {'total_assets':'total_assets'}),
    ('cashflow', {'n_cashflow_act':'operating_cashflow'}),
    ('fina_indicator', {'eps':'basic_eps'}),
])
def test_scoped_statement_diagnostic_matches_full_input_projection(table, columns):
    conn = get_conn()
    try:
        conn.set_session(isolation_level='REPEATABLE READ', readonly=True)
        full = _statement_rows(conn,table,columns,date(2026,11,2))
        codes = pd.Index(['300750.SZ'])
        scoped = _statement_rows(conn,table,columns,date(2026,11,2),securities=codes)
        expected = full.loc[full.ts_code.isin(codes)].sort_values(['ts_code','end_date']).reset_index(drop=True)
        scoped = scoped.sort_values(['ts_code','end_date']).reset_index(drop=True)
        expected.attrs.clear()
        scoped.attrs.clear()
        pd.testing.assert_frame_equal(scoped,expected,check_dtype=False)
        assert _statement_rows(conn,table,columns,date(2026,11,2),securities=pd.Index([])).empty
    finally:
        conn.rollback()
        conn.close()


def test_single_field_projection_respects_newer_unselected_filing_version():
    code = 'TEST'+uuid4().hex[:12]
    conn = get_conn()
    try:
        for i, (published, field) in enumerate([(date(2026,3,10), 'fix_assets'),
                                                (date(2026,4,1), 'fix_assets_total')]):
            content = ('%PDF-1.4 isolated version test '+code+str(i)).encode()
            digest = hashlib.sha256(content).hexdigest()
            url = f'https://static.cninfo.com.cn/finalpage/{published}/{uuid4().int}.PDF'
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO source_raw_artifact
                    (source_id,endpoint_key,content_type,content_hash,inline_content,source_url)
                    VALUES ('cninfo',%s,'application/pdf',%s,%s,%s) RETURNING artifact_id""",
                    (code,digest,content,url))
                artifact_id = cur.fetchone()[0]
            assert persist_facts(conn, [dict(artifact_id=artifact_id, artifact_sha256=digest,
                statement_table='balancesheet', ts_code=code, end_date=date(2025,12,31),
                published_on=published, field_name=field, value_yuan=100+i, page_number=1,
                row_label='固定资产', original_unit='人民币元', reviewed_by='integration-test',
                evidence={'source_url':url})]) == 1
        early = _statement_rows(conn, 'balancesheet', {'fix_assets':'fix_assets'}, date(2026,4,1))
        assert early[early.ts_code == code].iloc[0].fix_assets == 100
        later = _statement_rows(conn, 'balancesheet', {'fix_assets':'fix_assets'}, date(2026,4,2))
        assert code not in set(later.ts_code)
        assert any(e['symbol'] == code and e['status'] == 'latest_version_field_unproven'
                   for e in later.attrs['filing_evidence'])
    finally:
        conn.rollback()
        conn.close()


def test_newer_original_can_supply_known_fields_without_old_vendor_carryover():
    code = 'TEST'+uuid4().hex[:12]
    conn = get_conn()
    content = ('%PDF-1.4 integration later original '+code).encode()
    digest = hashlib.sha256(content).hexdigest()
    url = f'https://static.cninfo.com.cn/finalpage/2026-04-01/{uuid4().int}.PDF'
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO source_raw_artifact
                (source_id,endpoint_key,content_type,content_hash,inline_content,source_url)
                VALUES ('cninfo',%s,'application/pdf',%s,%s,%s) RETURNING artifact_id""",
                (code,digest,content,url))
            artifact = cur.fetchone()[0]
            cur.execute("CREATE TEMP TABLE newer_fact_test_source (LIKE balancesheet INCLUDING DEFAULTS) ON COMMIT DROP")
            cur.execute("""INSERT INTO newer_fact_test_source
                (ts_code,end_date,ann_date,f_ann_date,report_type,update_flag,fix_assets,total_assets)
                VALUES (%s,'2025-12-31','2026-03-01','2026-03-01',1,'0',90,900)""",(code,))
            cur.execute("SELECT archive_financial_batch('balancesheet','newer_fact_test_source',true)")
        fact = dict(artifact_id=artifact,artifact_sha256=digest,statement_table='balancesheet',
                    ts_code=code,end_date=date(2025,12,31),published_on=date(2026,4,1),
                    field_name='fix_assets',value_yuan=100,page_number=1,row_label='固定资产',
                    original_unit='人民币元',reviewed_by='integration',evidence={'source_url':url})
        assert persist_facts(conn,[fact]) == 1
        before = _statement_rows(conn,'balancesheet',{'fix_assets':'fix_assets','total_assets':'total_assets'},date(2026,4,1))
        assert before[before.ts_code==code].iloc[0].fix_assets == 90
        after = _statement_rows(conn,'balancesheet',{'fix_assets':'fix_assets','total_assets':'total_assets'},date(2026,4,2))
        row = after[after.ts_code==code].iloc[0]
        assert row.fix_assets == 100
        assert __import__('pandas').isna(row.total_assets)
        with pytest.raises(ValueError,match='unreviewed filing field'):
            persist_facts(conn,[dict(fact,field_name='total_share')])
    finally:
        conn.rollback()
        conn.close()


def test_original_fact_recovers_only_proven_field_and_never_modifies_vendor_rows():
    code = 'TEST'+uuid4().hex[:12]
    content=b'%PDF-1.4 isolated integration-test original artifact'
    digest=hashlib.sha256(content).hexdigest()
    url=f'https://static.cninfo.com.cn/finalpage/2026-03-10/{uuid4().int}.PDF'
    conn=get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO source_raw_artifact
                (source_id,endpoint_key,content_type,content_hash,inline_content,source_url)
                VALUES ('cninfo',%s,'application/pdf',%s,%s,%s) RETURNING artifact_id""",
                (code,digest,content,url))
            artifact_id=cur.fetchone()[0]
        fact=dict(artifact_id=artifact_id,artifact_sha256=digest,statement_table='balancesheet',
                  ts_code=code,end_date=date(2025,12,31),published_on=date(2026,3,10),
                  field_name='fix_assets',value_yuan=100,page_number=1,row_label='固定资产',
                  original_unit='人民币元',reviewed_by='integration-test',evidence={'source_url':url})
        assert persist_facts(conn,[fact])==1
        assert persist_facts(conn,[fact])==0
        with pytest.raises(ValueError,match='artifact'):
            persist_facts(conn,[dict(fact,published_on=date(2026,3,9))])
        with pytest.raises(ValueError,match='conflicting'):
            persist_facts(conn,[dict(fact,value_yuan=999)])
        columns={'fix_assets':'fix_assets','total_assets':'total_assets'}
        early=_statement_rows(conn,'balancesheet',columns,date(2026,3,10))
        assert early.empty or code not in set(early.ts_code)
        restored=_statement_rows(conn,'balancesheet',columns,date(2026,3,11))
        row=restored[restored.ts_code==code].iloc[0]
        assert row.fix_assets==100
        assert row.total_assets is None or __import__('pandas').isna(row.total_assets)
        assert any(e['symbol']==code and e['status']=='recovered_from_original'
                   for e in restored.attrs['filing_evidence'])
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM balancesheet WHERE ts_code=%s',(code,))
            assert cur.fetchone()[0]==0
            cur.execute('SELECT count(*) FROM balancesheet_revision WHERE ts_code=%s',(code,))
            assert cur.fetchone()[0]==0
            cur.execute('UPDATE financial_filing_fact SET revoked_at=now() WHERE artifact_id=%s',(artifact_id,))
        revoked=_statement_rows(conn,'balancesheet',columns,date(2026,3,11))
        assert revoked.empty or code not in set(revoked.ts_code)
        with pytest.raises(ValueError,match='revoked'):
            persist_facts(conn,[fact])
    finally:
        conn.rollback()  # own UUID evidence only; no production cleanup writes
        conn.close()
