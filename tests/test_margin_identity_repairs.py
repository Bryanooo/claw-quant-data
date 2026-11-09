from pathlib import Path
import os
import pytest

from scripts.repair_margin_identities import choose
from scripts.probe_margin_identities import FIELDS


def sample():
    old = dict.fromkeys(FIELDS)
    old.update(ts_code="601326.SH", trade_date="20261030", rzye=98739889, rqyl=567000)
    ts = dict(
        ts_code=old["ts_code"],
        trade_date=old["trade_date"],
        source="tushare",
        proof=1,
        values=old.copy(),
    )
    em = dict(
        ts,
        source="eastmoney",
        proof="sha",
        values=dict(old, rqye=2024190, rzrqye=100764079),
    )
    return old, ts, em


def test_explicit_amount_fallback_only_when_corroborated():
    old, ts, em = sample()
    assert choose(old, ts, em)[0] == "eastmoney"
    for changes in [
        dict(rqyl=567001),
        dict(rzye=98739890),
        dict(rqye=None),
        dict(rqye=0, rzrqye=98739889),
        dict(rzrqye=100764078),
    ]:
        assert (
            choose(old, ts, dict(em, values=dict(em["values"], **changes)))[0] is None
        )
    with pytest.raises(ValueError):
        choose(old, ts, dict(em, trade_date="20261029"))
    assert choose(old, dict(ts, values=em["values"]), em)[0] == "tushare"


@pytest.mark.skipif(os.getenv("RUN_DB_INTEGRATION") != "1", reason="needs PostgreSQL")
def test_exact_replay_does_not_undo_repair_or_override_new_revision():
    from service.db import get_conn

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TEMP TABLE margin_detail (LIKE public.margin_detail INCLUDING ALL)"
            )
            sql = (
                Path(__file__).resolve().parents[1]
                / "sql/migrations/122_margin_detail_repair_evidence.sql"
            ).read_text()
            cur.execute(
                sql.replace(
                    "CREATE TABLE IF NOT EXISTS", "CREATE TEMP TABLE IF NOT EXISTS"
                )
                .replace("public.margin_detail", "pg_temp.margin_detail")
                .replace(
                    "FUNCTION preserve_verified_margin_detail_repair",
                    "FUNCTION pg_temp.preserve_verified_margin_detail_repair",
                )
            )
            cur.execute(
                "INSERT INTO margin_detail(ts_code,trade_date,rzye,rqyl) VALUES ('601326.SH','20261030',10,2)"
            )
            cur.execute("""INSERT INTO pg_temp.margin_detail_repair_evidence
                SELECT trade_date,ts_code,'eastmoney',to_jsonb(d),'{"rzye":"10","rqye":"6","rzrqye":"16"}','{}',now()
                FROM pg_temp.margin_detail d""")
            cur.execute("UPDATE margin_detail SET rqye=6,rzrqye=16")

            def replay(qty):
                cur.execute(
                    """INSERT INTO margin_detail(ts_code,trade_date,rzye,rqyl)
                    VALUES ('601326.SH','20261030',10,%s) ON CONFLICT (ts_code,trade_date) DO UPDATE
                    SET rqyl=EXCLUDED.rqyl,rqye=EXCLUDED.rqye,rzrqye=EXCLUDED.rzrqye""",
                    (qty,),
                )
                cur.execute("SELECT rqye,rzrqye FROM margin_detail")
                return cur.fetchone()

            assert replay(2) == (6, 16)
            cur.execute("UPDATE margin_detail SET rqye=7,rzrqye=17")
            assert replay(2) == (7, 17)
            assert replay(3) == (None, None)
    finally:
        conn.rollback()
        conn.close()
