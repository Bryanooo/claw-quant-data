from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg2 import OperationalError
from psycopg2.errors import UndefinedTable
import pytest

from service.api.routers.health import router
from service.schema_migrations import required_migrations


@pytest.mark.parametrize("state", ["ready", "missing_112", "no_ledger", "offline"])
def test_ready_checks_every_migration_in_this_image(state):
    expected = required_migrations()
    revision = "112_financial_report_revisions"

    class Database:
        def fetch_all(self, statement):
            assert "sys_schema_migration" in statement
            if state == "offline":
                raise OperationalError()
            if state == "no_ledger":
                raise UndefinedTable()
            applied = expected - {revision} if state == "missing_112" else expected
            return [{"version": item} for item in applied | {"999_future"}]

    app = FastAPI()
    app.state.database = Database()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get("/v1/ops/health/ready")
        assert client.get("/v1/ops/health/live").status_code == 200
    if state == "ready":
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "database": "ok"}
    else:
        assert response.status_code == 503
        assert response.json()["database"] == ("unavailable" if state == "offline" else "ok")
        if state == "missing_112":
            assert response.json()["missing_migrations"] == [revision]
        if state == "no_ledger":
            assert response.json()["missing_migrations"] == sorted(expected)
