from datetime import datetime
from zoneinfo import ZoneInfo

from service.orchestration_v2.late_repair import next_late_repair_at


TZ = ZoneInfo("Asia/Shanghai")


def test_next_late_repair_uses_the_nearest_post_close_window():
    assert next_late_repair_at(datetime(2026, 10, 1, 13, 55, tzinfo=TZ)) == (
        datetime(2026, 10, 1, 15, 58, tzinfo=TZ)
    )
    assert next_late_repair_at(datetime(2026, 10, 1, 19, 0, tzinfo=TZ)) == (
        datetime(2026, 10, 1, 21, 58, tzinfo=TZ)
    )
    assert next_late_repair_at(datetime(2026, 10, 1, 23, 59, tzinfo=TZ)) == (
        datetime(2026, 10, 2, 15, 58, tzinfo=TZ)
    )
