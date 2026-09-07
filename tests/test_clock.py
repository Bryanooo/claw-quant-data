from datetime import datetime, timezone

import service.clock as clock


def test_business_clock_is_always_shanghai_aware(monkeypatch):
    class FakeDateTime:
        @staticmethod
        def now(target_timezone):
            return datetime(2026, 8, 28, 16, 30, tzinfo=timezone.utc).astimezone(
                target_timezone
            )

    monkeypatch.setattr(clock, "datetime", FakeDateTime)

    assert clock.business_now().isoformat() == "2026-08-29T00:30:00+08:00"
    assert clock.business_today().isoformat() == "2026-08-29"


def test_business_time_override_is_scoped_and_normalized():
    before = clock.business_now()
    with clock.business_time("2026-08-28T16:30:00+00:00"):
        assert clock.business_now().isoformat() == "2026-08-29T00:30:00+08:00"
        assert clock.business_today().isoformat() == "2026-08-29"
    assert clock.business_now() >= before
