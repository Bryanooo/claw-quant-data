import pandas as pd

from service.tushare_raw_archive import TushareRawArchive


class FakeCursor:
    def __init__(self):
        self.executions = []
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, statement, parameters):
        self.executions.append((statement, parameters))
        if statement.strip().startswith("DELETE"):
            self.rowcount = 3

    def fetchone(self):
        return (42,)


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_archive_response_records_transport_and_logical_scope(monkeypatch):
    connection = FakeConnection()
    captured = {}

    def fake_execute_values(_cursor, statement, values, page_size):
        captured["statement"] = statement
        captured["values"] = values
        captured["page_size"] = page_size

    monkeypatch.setattr(
        "service.tushare_raw_archive.psycopg2.extras.execute_values",
        fake_execute_values,
    )
    archive = TushareRawArchive(lambda: connection)

    evidence = archive.archive_response(
        api_name="daily",
        parameters={
            "trade_date": "20260917",
            "limit": 5000,
            "offset": 0,
            "token": "must-not-be-stored",
        },
        frame=pd.DataFrame(
            [
                {"ts_code": "000001.SZ", "close": 10.2},
                {"ts_code": "000001.SZ", "close": 10.2},
            ]
        ),
        collector_name="collectors.stock.market.daily.DailyCollector",
    )

    request_parameters = connection.cursor_instance.executions[0][1]
    assert request_parameters[0] == "daily"
    assert request_parameters[3].adapted["token"] == "[REDACTED]"
    assert "limit" not in request_parameters[4].adapted
    assert "offset" not in request_parameters[4].adapted
    assert len(captured["values"]) == 1
    assert captured["values"][0][0] == "daily"
    assert "ON CONFLICT (api_name, request_hash" in captured["statement"]
    assert captured["page_size"] == 1000
    assert evidence["request_id"] == 42
    assert evidence["source_id"] == "tushare"
    assert evidence["row_count"] == 2
    assert evidence["unique_record_count"] == 1
    assert connection.committed is True
    assert connection.closed is True


def test_archive_empty_response_keeps_request_evidence_without_records(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(
        "service.tushare_raw_archive.psycopg2.extras.execute_values",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("empty response must not insert records")
        ),
    )

    evidence = TushareRawArchive(lambda: connection).archive_response(
        api_name="daily",
        parameters={"trade_date": "20260913"},
        frame=pd.DataFrame(),
        collector_name="DailyCollector",
    )

    assert evidence["status"] == "empty"
    assert evidence["row_count"] == 0
    assert connection.committed is True


def test_request_only_response_keeps_hash_evidence_without_row_payloads(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(
        "service.tushare_raw_archive.psycopg2.extras.execute_values",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("request-only mode must not insert raw records")
        ),
    )

    evidence = TushareRawArchive(lambda: connection).archive_response(
        api_name="daily",
        parameters={"trade_date": "20260928"},
        frame=pd.DataFrame([{"ts_code": "000001.SZ", "close": 10.2}]),
        collector_name="DailyCollector",
        persist_records=False,
    )

    assert evidence["row_count"] == 1
    assert evidence["response_hash"]
    assert evidence["records_persisted"] is False
    assert connection.committed is True


def test_archive_records_does_not_create_a_second_request(monkeypatch):
    connection = FakeConnection()
    captured = {}

    def fake_execute_values(_cursor, statement, values, page_size):
        captured["statement"] = statement
        captured["values"] = values
        captured["page_size"] = page_size

    monkeypatch.setattr(
        "service.tushare_raw_archive.psycopg2.extras.execute_values",
        fake_execute_values,
    )

    archived = TushareRawArchive(lambda: connection).archive_records(
        endpoint_key="daily",
        parameters={"trade_date": "20260928", "offset": 0},
        records=[{"ts_code": "000001.SZ", "close": 10.2}],
    )

    assert archived == 1
    assert connection.cursor_instance.executions == []
    assert "INSERT INTO tushare_raw_record" in captured["statement"]
    assert captured["values"][0][0] == "daily"
    assert captured["page_size"] == 1000
    assert connection.committed is True


def test_resolve_records_deletes_only_the_matching_logical_scope():
    connection = FakeConnection()

    deleted = TushareRawArchive(lambda: connection).resolve_records(
        api_name="daily",
        parameters={"trade_date": "20260928", "limit": 1000, "offset": 2000},
    )

    statement, parameters = connection.cursor_instance.executions[0]
    assert "DELETE FROM tushare_raw_record" in statement
    assert parameters[0] == "daily"
    assert len(parameters[1]) == 64
    assert deleted == 3
    assert connection.committed is True


def test_archive_failure_preserves_provider_error_text():
    connection = FakeConnection()

    TushareRawArchive(lambda: connection).archive_failure(
        api_name="daily",
        parameters={"trade_date": "20260917"},
        collector_name="DailyCollector",
        error=RuntimeError("provider unavailable"),
    )

    parameters = connection.cursor_instance.executions[0][1]
    assert parameters[-2] == "provider unavailable"
    assert connection.committed is True
