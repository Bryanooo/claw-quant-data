"""Resource-isolated worker for V2 execution pools."""

from __future__ import annotations

import logging
import os
import signal
import time
from uuid import uuid4

from service.acquisition_runtime.reliability import historical_resume_at
from service.heartbeat import Heartbeat
from service.orchestration_v2.repository import OrchestrationV2Repository
from service.orchestration_v2.runtime import OrchestrationV2Runtime


logger = logging.getLogger("orchestration-v2-worker")


class OrchestrationV2Worker:
    def __init__(
        self,
        repository: OrchestrationV2Repository | None = None,
        *,
        worker_id: str | None = None,
        poll_interval: float = 2,
        lease_seconds: int = 180,
        resource_classes: tuple[str, ...] = ("v2-backfill",),
        heartbeat_component: str = "worker-v2-backfill",
    ):
        self._repository = repository or OrchestrationV2Repository()
        self._runtime = OrchestrationV2Runtime(self._repository)
        self._worker_id = worker_id or f"{os.uname().nodename}-v2-{uuid4().hex[:8]}"
        self._poll_interval = poll_interval
        self._lease_seconds = lease_seconds
        self._resource_classes = resource_classes
        self._heartbeat_component = heartbeat_component
        self._stopping = False
        self._last_reclaim = 0.0

    def stop(self, *_args) -> None:
        self._stopping = True

    def run_once(self) -> bool:
        # The V2 historical pool never claims an execution during the SSE
        # market window, so merely deferring work cannot consume retry budget.
        if self._resource_classes == ("v2-backfill",) and historical_resume_at("repair") is not None:
            return False
        execution = self._repository.claim_next(
            worker_id=self._worker_id,
            resource_classes=self._resource_classes,
            lease_seconds=self._lease_seconds,
        )
        if not execution:
            return False
        result = self._runtime.run_claimed(
            execution,
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
        )
        logger.info(
            "V2 execution %s moved to %s",
            execution["task_execution_id"],
            result["status"],
        )
        return True

    def run_forever(self) -> None:
        heartbeat = Heartbeat(
            self._heartbeat_component,
            details={
                "resource_classes": list(self._resource_classes),
                "orchestration_version": 2,
            },
        ).start()
        try:
            while not self._stopping:
                now = time.monotonic()
                if now - self._last_reclaim >= 60:
                    self._repository.reclaim_expired_leases(limit=100)
                    self._last_reclaim = now
                if not self.run_once():
                    time.sleep(self._poll_interval)
        finally:
            heartbeat.stop()


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    resource_classes = tuple(
        item.strip()
        for item in os.getenv("V2_JOB_RESOURCE_CLASSES", "v2-backfill").split(",")
        if item.strip()
    )
    worker = OrchestrationV2Worker(
        poll_interval=float(os.getenv("V2_JOB_POLL_INTERVAL_SECONDS", "2")),
        lease_seconds=int(os.getenv("V2_JOB_LEASE_SECONDS", "180")),
        resource_classes=resource_classes,
        heartbeat_component=os.getenv("V2_WORKER_COMPONENT", "worker-v2-backfill"),
    )
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    worker.run_forever()


if __name__ == "__main__":
    main()
