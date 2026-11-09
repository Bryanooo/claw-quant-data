"""Conservative, evidence-backed recovery of existing backup observations.

Caller verifies the entire archive before registering a source. All writes use
the caller's transaction; default CLI execution rolls them back. Old schemas
become NULL in newly introduced columns, never filled from today's values.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from psycopg2.extras import Json

from service.financial_statements import VERSIONED_STATEMENTS


def register_source(conn, *, digest, name, size, created, completed):
    if created.tzinfo is None or completed.tzinfo is None or completed < created:
        raise ValueError('invalid backup observation timestamps')
    available = completed.astimezone(ZoneInfo('Asia/Shanghai')).date() + timedelta(days=1)
    with conn.cursor() as cur:
        cur.execute('SELECT now()')
        if completed > cur.fetchone()[0]:
            raise ValueError('future backup observation')
        cur.execute("""INSERT INTO financial_backup_source
            (sha256,file_name,size_bytes,archive_created_at,completed_at,available_on)
            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            (digest,name,size,created,completed,available))
        cur.execute("""SELECT file_name,size_bytes,archive_created_at,completed_at,available_on
            FROM financial_backup_source WHERE sha256=%s""", (digest,))
        if cur.fetchone() != (name,size,created,completed,available):
            raise ValueError('conflicting backup provenance')
    return available


def recover_batch(conn, table, digest, rows):
    if table not in VERSIONED_STATEMENTS:
        raise ValueError('unsupported statement table')
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.execute('SELECT available_on FROM financial_backup_source WHERE sha256=%s', (digest,))
        source = cur.fetchone()
        if source is None:
            raise ValueError('verified source is required')
        cur.execute("SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass "
                    "AND attnum>0 AND NOT attisdropped", (table,))
        columns = {r[0] for r in cur.fetchall()}
        identities = set()
        for row in rows:
            if set(row) - columns or not row.get('ts_code') or not row.get('end_date'):
                raise ValueError('unknown schema or missing backup identity')
            if table != 'fina_indicator' and str(row.get('report_type')) != '1':
                raise ValueError('only consolidated backup rows are supported')
            identity = row['ts_code'], row['end_date']
            if identity in identities:
                raise ValueError('duplicate consolidated backup identity')
            identities.add(identity)
        # Coordinate with live collector revision inserts without touching its
        # current-value relation. Locks are bounded by the caller's timeout.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext('finance_revision'),hashtext(%s))", (table,))
        published = 's.ann_date' if table == 'fina_indicator' else 'greatest(s.ann_date,s.f_ann_date)'
        kind = '0' if table == 'fina_indicator' else 's.report_type'
        # Table identifiers are from the fixed allowlist, payloads are bound JSON.
        cur.execute(f"""WITH payloads AS MATERIALIZED (
            SELECT value AS original FROM jsonb_array_elements(%s::jsonb)
        ), incoming AS MATERIALIZED (
            SELECT s AS row_data,s.ts_code,s.end_date,{kind} AS kind,{published} AS published_on,
                   sha256(convert_to((to_jsonb(s)-'created_at')::text,'UTF8')) AS fingerprint,
                   (SELECT count(*) FROM jsonb_each(jsonb_strip_nulls(to_jsonb(s)-'created_at'))) AS populated,
                   p.original
            FROM payloads p CROSS JOIN LATERAL jsonb_populate_record(NULL::{table},p.original) s
        ), evidence AS (
            INSERT INTO financial_backup_row (backup_sha256,statement_table,fingerprint,original_row)
            SELECT %s,%s,fingerprint,original FROM incoming
            ON CONFLICT DO NOTHING RETURNING fingerprint
        )
        INSERT INTO {table}_revision
            (row_data,ts_code,end_date,kind,published_on,available_on,fingerprint,populated)
        SELECT row_data,ts_code,end_date,kind,published_on,greatest(published_on,%s::date),fingerprint,populated
        FROM incoming
        ON CONFLICT (fingerprint) DO UPDATE SET
            available_on=least({table}_revision.available_on,EXCLUDED.available_on)
        WHERE {table}_revision.available_on > EXCLUDED.available_on
        """, (Json(rows),digest,table,source[0]))
        return cur.rowcount
