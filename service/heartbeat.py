"""Database-backed liveness heartbeats for non-HTTP service processes."""

from __future__ import annotations

import logging
import os
import json
from threading import Event, Thread
from uuid import uuid4

from service.db import execute
from service.config import APP_REVISION

logger = logging.getLogger("service-heartbeat")


class Heartbeat:
    def __init__(
        self,
        component: str,
        *,
        interval_seconds: int = 15,
        details: dict | None = None,
    ):
        self.component = component
        self.instance_id = f"{os.uname().nodename}-{uuid4().hex[:8]}"
        self.interval_seconds = interval_seconds
        self.details = {"app_revision": APP_REVISION, **dict(details or {})}
        self._stop = Event()
        self._thread: Thread | None = None

    def beat(self) -> None:
        execute(
            """
            INSERT INTO sys_service_heartbeat(
                component, instance_id, process_id, last_seen_at, details
            )
            VALUES (%s, %s, %s, NOW(), %s::jsonb)
            ON CONFLICT (component, instance_id) DO UPDATE SET
                process_id = EXCLUDED.process_id,
                last_seen_at = NOW(),
                details = EXCLUDED.details
            """,
            (
                self.component,
                self.instance_id,
                os.getpid(),
                json.dumps(self.details, ensure_ascii=False),
            ),
        )

    def start(self) -> "Heartbeat":
        self.beat()
        self._thread = Thread(target=self._run, name=f"{self.component}-heartbeat", daemon=True)
        self._thread.start()
        return self

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                self.beat()
            except Exception:
                logger.exception("failed to publish %s heartbeat", self.component)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
