"""Long-running fifteen-minute intraday collection process."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import logging
from threading import Event

from service.data_service.database import Database
from service.heartbeat import Heartbeat
from service.intraday.repository import IntradayRepository
from service.intraday.service import IntradayObservationService


CST = timezone(timedelta(hours=8))
logger = logging.getLogger("intraday-worker")


def _in_session(value: time) -> bool:
    return time(9, 30) <= value < time(11, 30) or time(13, 0) <= value < time(15, 0)


def _trade_day(database: Database, now: datetime) -> bool:
    row = database.fetch_one(
        "SELECT is_open FROM trade_cal WHERE exchange='SSE' AND cal_date=%s",
        (now.date(),),
    )
    return bool(row and row["is_open"] == 1)


def run_forever(stop: Event | None = None) -> None:
    stop = stop or Event()
    database = Database()
    heartbeat = Heartbeat(
        "intraday-worker",
        details={"cadence_minutes": 15, "mode": "scheduled_observation"},
    ).start()
    service = IntradayObservationService(IntradayRepository(database))
    try:
        while not stop.is_set():
            now = datetime.now(CST)
            if _in_session(now.time()) and _trade_day(database, now):
                try:
                    service.run(now=now, trigger_source="schedule")
                except Exception:
                    logger.exception("intraday observation slot failed")
            stop.wait(20)
    finally:
        heartbeat.stop()
        database.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_forever()
