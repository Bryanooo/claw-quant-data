import os
from contextlib import contextmanager
from datetime import date

import pytest

from service.data_coverage.registry import COVERAGE_RULES
from service.data_coverage.repository import CoverageRepository
from service.db import get_conn


@pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1", reason="requires PostgreSQL"
)
@pytest.mark.parametrize(
    "dataset,entity", [("margin", "exchange_id"), ("margin_detail", "ts_code")]
)
def test_real_business_rows_override_transport_success(dataset, entity):
    conn = get_conn()

    class Repository(CoverageRepository):
        @contextmanager
        def _connection(self):
            yield conn

    try:
        with conn.cursor() as cur:
            # Session-local fixture; no production rows/states are changed.
            cur.execute(
                f"CREATE TEMP TABLE {dataset} (trade_date text,{entity} text,rzye numeric,rqye numeric,rzrqye numeric)"
            )
            cur.execute(f"INSERT INTO {dataset} VALUES ('20261030','X',10,2,12)")
            repo, rule, day = (
                Repository(),
                COVERAGE_RULES.get(dataset),
                date(2026, 10, 30),
            )
            assert not repo.actual_partitions(
                rule, day, day, verified_transport_dates={day}
            )[0].known_incomplete
            for field, bad in [
                ("rqye", None),
                ("rqye", "NaN"),
                ("rqye", "Infinity"),
                ("rzye", "-1"),
                ("rzrqye", "11"),
            ]:
                cur.execute("SAVEPOINT bad_field")
                cur.execute(f"UPDATE {dataset} SET {field}=%s", (bad,))
                observed = repo.actual_partitions(
                    rule, day, day, verified_transport_dates={day}
                )[0]
                assert observed.row_count == 1
                assert observed.known_incomplete
                assert observed.invalid_balance_rows == 1
                cur.execute("ROLLBACK TO SAVEPOINT bad_field")
    finally:
        conn.rollback()
        conn.close()
