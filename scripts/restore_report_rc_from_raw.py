#!/usr/bin/env python3
"""Rebuild the report_rc business table from lossless raw Tushare records."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import psycopg2

from service.config import DB_CONFIG


RESTORE_SQL = r"""
WITH raw AS MATERIALIZED (
    SELECT
        payload,
        last_seen_at,
        md5(concat_ws(
            chr(31),
            coalesce(nullif(btrim(payload->>'ts_code'), ''), '<NULL>'),
            to_date(payload->>'report_date', 'YYYYMMDD')::text,
            coalesce(nullif(btrim(payload->>'report_title'), ''), '<NULL>'),
            coalesce(nullif(btrim(payload->>'org_name'), ''), '<NULL>'),
            coalesce(nullif(btrim(payload->>'author_name'), ''), '<NULL>'),
            coalesce(nullif(btrim(payload->>'quarter'), ''), '<NULL>')
        )) AS source_key
    FROM tushare_raw_record
    WHERE api_name = 'report_rc'
      AND payload->>'ts_code' IS NOT NULL
      AND payload->>'report_date' ~ '^\d{8}$'
), latest AS (
    SELECT DISTINCT ON (source_key)
        source_key,
        payload
    FROM raw
    ORDER BY source_key, last_seen_at DESC
)
INSERT INTO report_rc AS target (
    source_key, ts_code, name, report_date, report_title, report_type,
    classify, org_name, author_name, quarter, op_rt, op_pr, tp, np, eps,
    pe, rd, roe, ev_ebitda, rating, max_price, min_price, imp_dg,
    create_time
)
SELECT
    source_key,
    payload->>'ts_code',
    payload->>'name',
    to_date(payload->>'report_date', 'YYYYMMDD'),
    payload->>'report_title',
    payload->>'report_type',
    payload->>'classify',
    payload->>'org_name',
    payload->>'author_name',
    nullif(payload->>'quarter', ''),
    nullif(payload->>'op_rt', '')::numeric,
    nullif(payload->>'op_pr', '')::numeric,
    nullif(payload->>'tp', '')::numeric,
    nullif(payload->>'np', '')::numeric,
    nullif(payload->>'eps', '')::numeric,
    nullif(payload->>'pe', '')::numeric,
    nullif(payload->>'rd', '')::numeric,
    nullif(payload->>'roe', '')::numeric,
    nullif(payload->>'ev_ebitda', '')::numeric,
    payload->>'rating',
    nullif(payload->>'max_price', '')::numeric,
    nullif(payload->>'min_price', '')::numeric,
    payload->>'imp_dg',
    coalesce(nullif(payload->>'create_time', '')::timestamp, now())
FROM latest
ON CONFLICT (source_key) DO UPDATE SET
    ts_code = excluded.ts_code,
    name = excluded.name,
    report_date = excluded.report_date,
    report_title = excluded.report_title,
    report_type = excluded.report_type,
    classify = excluded.classify,
    org_name = excluded.org_name,
    author_name = excluded.author_name,
    quarter = excluded.quarter,
    op_rt = excluded.op_rt,
    op_pr = excluded.op_pr,
    tp = excluded.tp,
    np = excluded.np,
    eps = excluded.eps,
    pe = excluded.pe,
    rd = excluded.rd,
    roe = excluded.roe,
    ev_ebitda = excluded.ev_ebitda,
    rating = excluded.rating,
    max_price = excluded.max_price,
    min_price = excluded.min_price,
    imp_dg = excluded.imp_dg,
    create_time = excluded.create_time
WHERE (target.*) IS DISTINCT FROM (excluded.*)
"""


def restore() -> tuple[int, int, int]:
    connection = psycopg2.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_try_advisory_xact_lock(hashtext(%s))",
                ("restore_report_rc_from_raw",),
            )
            if not cursor.fetchone()[0]:
                raise RuntimeError("another report_rc restore is already running")
            cursor.execute(RESTORE_SQL)
            affected = cursor.rowcount
            cursor.execute(
                """
                SELECT count(*), count(*) FILTER (WHERE quarter IS NULL)
                FROM report_rc
                """
            )
            total, null_quarter = cursor.fetchone()
        connection.commit()
        return affected, total, null_quarter
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    affected, total, null_quarter = restore()
    print(
        f"report_rc restored: affected={affected}, total={total}, "
        f"without_quarter={null_quarter}"
    )
