from datetime import datetime, timedelta, timezone

from collectors.base import BaseCollector
import pytest

from service.tushare_rate_limit import (
    GLOBAL_RATE_KEY,
    TushareRateSlotDeferredError,
    _reserve_daily_quota,
    reserve_tushare_request,
)


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


def test_durable_job_defers_long_interface_wait_without_reserving_or_sleeping(
    monkeypatch,
):
    now = datetime(2026, 9, 8, 5, 0, tzinfo=timezone.utc)
    next_slots = {
        GLOBAL_RATE_KEY: now,
        "hk_daily": now + timedelta(minutes=45),
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
        rolled_back = False

        def cursor(self):
            return Cursor()

        def commit(self):
            raise AssertionError("deferred slot must not be committed")

        def rollback(self):
            self.rolled_back = True

        def close(self):
            pass

    connection = Connection()
    sleeps = []
    monkeypatch.setattr(
        "service.tushare_rate_limit.is_durable_job_active", lambda: True
    )

    with pytest.raises(TushareRateSlotDeferredError) as raised:
        reserve_tushare_request(
            "hk_daily",
            interface_interval=3600,
            global_interval=0.25,
            connection_factory=lambda **_kwargs: connection,
            sleep=sleeps.append,
        )

    assert raised.value.retry_after_seconds == 2700
    assert connection.rolled_back is True
    assert updates == []
    assert sleeps == []


def test_major_news_daily_quota_defers_until_next_shanghai_day(monkeypatch):
    now = datetime(2026, 9, 20, 13, 0, tzinfo=timezone.utc)

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _statement, _params):
            pass

        def fetchone(self):
            return datetime(2026, 9, 19, 16, 0, tzinfo=timezone.utc), 35, now

    class Connection:
        rolled_back = False

        def cursor(self):
            return Cursor()

        def commit(self):
            raise AssertionError("a deferred reservation must not commit")

        def rollback(self):
            self.rolled_back = True

        def close(self):
            pass

    connection = Connection()
    monkeypatch.setattr(
        "service.tushare_rate_limit.is_durable_job_active", lambda: True
    )

    with pytest.raises(TushareRateSlotDeferredError) as raised:
        _reserve_daily_quota(
            "major_news",
            connection_factory=lambda **_kwargs: connection,
            sleep=lambda _seconds: None,
        )

    assert raised.value.retry_after_seconds == 11100
    assert connection.rolled_back is True


def test_base_collector_routes_dedicated_sdk_calls_through_shared_limiter(monkeypatch):
    upstream_calls = []
    reservations = []
    archived = []

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
    monkeypatch.setattr("collectors.base.TUSHARE_CONNECT_TIMEOUT_SECONDS", 4.0)
    monkeypatch.setattr("collectors.base.TUSHARE_READ_TIMEOUT_SECONDS", 45.0)
    monkeypatch.setattr(
        "service.tushare_rate_limit.reserve_tushare_request",
        lambda api_name: reservations.append(api_name),
    )
    monkeypatch.setattr(
        "collectors.base.TushareRawArchive.archive_response",
        lambda _self, **values: archived.append(values),
    )

    class DailyCollector(BaseCollector):
        API_NAME = "daily"
        table_name = "daily"
        pk_columns = ["ts_code", "trade_date"]

    collector = DailyCollector()
    assert collector.fetch(trade_date="20260828") == "frame"

    assert reservations == ["daily"]
    assert upstream_calls == [("daily", (), {"trade_date": "20260828"})]
    assert archived[0]["api_name"] == "daily"
    assert archived[0]["parameters"] == {"trade_date": "20260828"}
    assert archived[0]["persist_records"] is True
    assert fake_pro._DataApi__timeout == (4.0, 45.0)


def test_base_collector_preserves_queue_rate_slot_deferral(monkeypatch):
    monkeypatch.setattr("collectors.base.get_env_tushare_token", lambda: "test-token")
    monkeypatch.setattr("collectors.base.get_config", lambda _key, default=None: default)
    monkeypatch.setattr("tushare.set_token", lambda _token: None)

    class FakePro:
        def query(self, _api_name, *_args, **_parameters):
            error = TushareRateSlotDeferredError("hk_daily", 1800)
            raise error

        def __getattr__(self, api_name):
            return lambda **parameters: self.query(api_name, **parameters)

    monkeypatch.setattr("tushare.pro_api", FakePro)
    monkeypatch.setattr("collectors.base.install_distributed_rate_limit", lambda pro: pro)
    monkeypatch.setattr(
        "collectors.base.TushareRawArchive.archive_failure",
        lambda *_args, **_kwargs: None,
    )

    class HongKongDailyCollector(BaseCollector):
        API_NAME = "hk_daily"
        table_name = "hk_daily"
        pk_columns = ["ts_code", "trade_date"]

    collector = HongKongDailyCollector()
    collector.retry_max = 1

    with pytest.raises(TushareRateSlotDeferredError):
        collector.run(skip_store=True, trade_date="20260907")
