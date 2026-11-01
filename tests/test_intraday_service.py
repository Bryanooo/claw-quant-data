from datetime import datetime, timezone

from service.intraday.service import IntradayObservationService


class DuplicateRepository:
    def claim_run(self, scheduled_for, trigger_source):
        self.scheduled_for = scheduled_for
        return None


def test_run_is_idempotent_per_fifteen_minute_slot():
    repository = DuplicateRepository()
    service = IntradayObservationService(repository)

    result = service.run(
        now=datetime(2026, 10, 23, 2, 7, 41, tzinfo=timezone.utc),
        trigger_source="schedule",
    )

    assert result["status"] == "already_collected"
    assert repository.scheduled_for.minute == 0
    assert repository.scheduled_for.second == 0
