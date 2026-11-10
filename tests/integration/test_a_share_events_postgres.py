"""Check event cardinality without touching any persistent business data."""

import os
import pytest
import service.tushare_normalization as normalization
from service.db import get_conn

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1", reason="requires PostgreSQL"
)


def test_multiple_issuance_projects_on_one_announcement_day_remain_distinct(
    monkeypatch,
):
    connection = get_conn()

    class BorrowedConnection:
        def cursor(self):
            return connection.cursor()

        def close(self):
            pass

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TEMP TABLE tushare_norm_stk_seasoned (_record_hash text,_request_hash text,ts_code text,ann_date date)"
            )
            # Two different project observations, plus one repeated payload.
            for identity in ("a", "b", "a"):
                cursor.execute(
                    "INSERT INTO tushare_norm_stk_seasoned VALUES(%s,%s,'000001.SZ','2026-11-09')",
                    (identity * 64, "c" * 64),
                )
        monkeypatch.setattr(normalization, "get_conn", BorrowedConnection)
        assert (
            normalization.TushareNormalizer().count_request_business_rows(
                "stk_seasoned", "c" * 64
            )
            == 2
        )
    finally:
        connection.rollback()
        connection.close()
