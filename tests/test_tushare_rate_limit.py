from datetime import datetime, timedelta, timezone

from collectors.base import BaseCollector
from service.tushare_rate_limit import GLOBAL_RATE_KEY, reserve_tushare_request


def test_reservation_locks_global_and_interface_slots_before_sleep():
    now = datetime(2026, 8, 29, tzinfo=timezone.utc)
    next_slots = {
        GLOBAL_RATE_KEY: now + timedelta(seconds=0.2),
        "daily": now + timedelta(seconds=0.1),
    }
    updates = []

    class Cursor:
        selected_key = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, statement, params):
            if "SELECT next_allowed_at" in statement:
                self.selected_key = params[0]
            elif "UPDATE sys_tushare_rate_limit" in statement:
                updates.append(params)

        def fetchone(self):
            return next_slots[self.selected_key], now

    class Connection:
        committed = False

        def cursor(self):
            return Cursor()

        def commit(self):
            self.committed = True

        def rollback(self):
            raise AssertionError("rollback should not be called")

        def close(self):
            pass

    connection = Connection()
    sleeps = []

    waited = reserve_tushare_request(
        "daily",
        interface_interval=1.0,
        global_interval=0.5,
        connection_factory=lambda **_kwargs: connection,
        sleep=sleeps.append,
    )

    assert waited == 0.2
    assert sleeps == [0.2]
    assert connection.committed is True
    assert {item[2] for item in updates} == {GLOBAL_RATE_KEY, "daily"}


def test_base_collector_routes_dedicated_sdk_calls_through_shared_limiter(monkeypatch):
    upstream_calls = []
    reservations = []

    class FakePro:
        def query(self, api_name, *args, **parameters):
            upstream_calls.append((api_name, args, parameters))
            return "frame"

        def __getattr__(self, api_name):
            return lambda **parameters: self.query(api_name, **parameters)

    fake_pro = FakePro()
    monkeypatch.setattr("collectors.base.get_env_tushare_token", lambda: "test-token")
    monkeypatch.setattr("collectors.base.get_config", lambda _key, default=None: default)
    monkeypatch.setattr("tushare.set_token", lambda _token: None)
    monkeypatch.setattr("tushare.pro_api", lambda: fake_pro)
    monkeypatch.setattr(
        "service.tushare_rate_limit.reserve_tushare_request",
        lambda api_name: reservations.append(api_name),
    )

    class DailyCollector(BaseCollector):
        API_NAME = "daily"
        table_name = "daily"
        pk_columns = ["ts_code", "trade_date"]

    collector = DailyCollector()
    assert collector.fetch(trade_date="20260828") == "frame"

    assert reservations == ["daily"]
    assert upstream_calls == [("daily", (), {"trade_date": "20260828"})]
