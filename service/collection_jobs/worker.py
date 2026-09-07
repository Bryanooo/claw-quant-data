"""Single-purpose worker process for queued collection jobs."""

import logging
import os
import signal
import time
from contextlib import contextmanager
from threading import Event, Thread, current_thread, main_thread
from uuid import uuid4

from service.collection_jobs.registry import TASKS
from service.collection_jobs.models import TaskExecutionResult
from service.collection_jobs.context import durable_job_execution
from service.collection_jobs.repository import JobRepository
from service.collection_jobs.verification import CollectionVerificationPlanner
from service.config import (
    JOB_EXECUTION_TIMEOUT_SECONDS,
    JOB_LEASE_SECONDS,
    JOB_POLL_INTERVAL_SECONDS,
    JOB_RECLAIM_INTERVAL_SECONDS,
    JOB_STALE_AFTER_SECONDS,
)
from service.heartbeat import Heartbeat

logger = logging.getLogger("collection-worker")


def parse_resource_classes(value: str | None) -> tuple[str, ...] | None:
    """Parse a pool allow-list; ``*`` keeps legacy all-resource behavior."""
    if value is None or value.strip() == "*":
        return None
    classes = tuple(
        dict.fromkeys(item.strip() for item in value.split(",") if item.strip())
    )
    if not classes:
        raise ValueError("WORKER_RESOURCE_CLASSES must be '*' or a non-empty list")
    if any(len(item) > 32 for item in classes):
        raise ValueError("worker resource class names must be at most 32 characters")
    return classes


class CollectionJobTimeoutError(TimeoutError):
    retryable = True


def classify_failure(exc: Exception) -> str:
    """Return a stable operator-facing failure category.

    Exception text remains available for diagnosis, while the category lets
    the dashboard distinguish retryable infrastructure incidents from data
    completeness and permanent contract/configuration errors.
    """
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if "ratelimit" in name or "quota" in message or "频率" in message:
        return "quota"
    if isinstance(exc, TimeoutError) or "timeout" in name or "timed out" in message:
        return "timeout"
    if "incomplete" in name or "truncat" in message or "cap (" in message:
        return "completeness"
    if "permission" in message or "访问权限" in message or "token" in message:
        return "permission"
    if (
        "validation" in name
        or "invalid" in name
        or "parameter" in message
        or "参数" in message
    ):
        return "invalid_request"
    if "handler" in name and "mismatch" in name:
        return "deployment_mismatch"
    if "psycopg" in name or "database" in name or "sql" in name:
        return "storage"
    if any(marker in name or marker in message for marker in (
        "connection", "network", "httperror", "connection reset", "dns"
    )):
        return "network"
    return "upstream_or_internal"


@contextmanager
def lease_heartbeat(repository, job_id: int, worker_id: str, lease_seconds: int):
    """Renew ownership while a long-running collector is making progress."""
    renew = getattr(repository, "renew_lease", None)
    if renew is None:
        yield
        return
    stopping = Event()
    interval = max(min(lease_seconds / 3, 30), 1)

    def beat() -> None:
        while not stopping.wait(interval):
            try:
                if not renew(job_id, worker_id, lease_seconds):
                    logger.error("job %s lease can no longer be renewed", job_id)
                    return
            except Exception:
                logger.exception("job %s lease renewal failed", job_id)

    thread = Thread(target=beat, name=f"job-lease-{job_id}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopping.set()
        thread.join(timeout=min(interval, 1))


@contextmanager
def execution_deadline(seconds: float):
    """Interrupt a stuck SDK/network call in the worker's main thread."""
    if seconds <= 0 or current_thread() is not main_thread() or not hasattr(signal, "SIGALRM"):
        yield
        return

    def raise_timeout(_signum, _frame):
        raise CollectionJobTimeoutError(
            f"collection job exceeded {seconds:g} seconds"
        )

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, raise_timeout)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


class JobWorker:
    def __init__(
        self,
        repository: JobRepository,
        *,
        worker_id: str | None = None,
        poll_interval: float = JOB_POLL_INTERVAL_SECONDS,
        resource_classes: tuple[str, ...] | None = None,
    ):
        self._repository = repository
        self._worker_id = worker_id or f"{os.uname().nodename}-{uuid4().hex[:8]}"
        self._poll_interval = poll_interval
        self._resource_classes = resource_classes
        self._stopping = False
        self._last_reclaim_at = 0.0
        self._verification = CollectionVerificationPlanner()

    def stop(self, *_args) -> None:
        self._stopping = True

    def run_once(self) -> bool:
        job = self._repository.claim_next(
            self._worker_id,
            lease_seconds=JOB_LEASE_SECONDS,
            resource_classes=self._resource_classes,
        )
        if not job:
            return False
        logger.info("running job %s (%s)", job["job_id"], job["task_name"])
        try:
            TASKS.assert_handler_compatible(job)
            with (
                lease_heartbeat(
                    self._repository,
                    job["job_id"],
                    self._worker_id,
                    JOB_LEASE_SECONDS,
                ),
                durable_job_execution(),
                execution_deadline(JOB_EXECUTION_TIMEOUT_SECONDS),
            ):
                result = TASKS.run(job["task_name"], job["parameters"])
        except Exception as exc:
            logger.exception("job %s failed", job["job_id"])
            retryable = getattr(exc, "retryable", True)
            retry_after_seconds = getattr(exc, "retry_after_seconds", None)
            status = self._repository.fail_or_requeue(
                job,
                f"{type(exc).__name__}: {exc}",
                retryable=retryable,
                retry_after_seconds=retry_after_seconds,
                failure_status=getattr(exc, "completion_status", "failed"),
                rows_inserted=getattr(exc, "rows_inserted", 0),
                completion_evidence={
                    **getattr(exc, "completion_evidence", {}),
                    "handler_type": job.get("handler_type"),
                    "handler_key": job.get("handler_key"),
                    "handler_version": job.get("handler_version"),
                    "code_revision": job.get("code_revision"),
                    "partial_rows_inserted": getattr(exc, "rows_inserted", 0),
                    "failed_partitions": list(getattr(exc, "failures", ()))[:50],
                    "failure": {
                        "category": classify_failure(exc),
                        "exception_type": type(exc).__name__,
                        "retryable": bool(retryable),
                        "retry_after_seconds": retry_after_seconds,
                        "attempt": job.get("attempt"),
                        "max_attempts": job.get("max_attempts"),
                    },
                },
            )
            logger.info("job %s moved to %s", job["job_id"], status)
        else:
            outcome = (
                result
                if isinstance(result, TaskExecutionResult)
                else TaskExecutionResult(
                    rows_inserted=int(result),
                    rows_fetched=int(result),
                    completion_status="unverified",
                    completion_evidence={
                        "verified": False,
                        **(
                            {
                                "zero_result_reason": (
                                    "dedicated_collector_zero_is_ambiguous"
                                )
                            }
                            if int(result) == 0 else {}
                        ),
                    },
                )
            )
            verification = (
                self._verification.plan(job)
                if outcome.rows_fetched > 0
                and outcome.completion_status != "empty"
                else None
            )
            self._repository.finish(
                job["job_id"],
                rows_inserted=outcome.rows_inserted,
                rows_fetched=outcome.rows_fetched,
                completion_status=outcome.completion_status,
                completion_evidence={
                    **outcome.completion_evidence,
                    "handler_type": job.get("handler_type"),
                    "handler_key": job.get("handler_key"),
                    "handler_version": job.get("handler_version"),
                    "code_revision": job.get("code_revision"),
                    **(
                        {}
                        if isinstance(result, TaskExecutionResult)
                        else {
                            "verified": False,
                            "reason": "dedicated collector returned only a row count; "
                            "coverage audit is required",
                        }
                    ),
                },
                worker_id=self._worker_id,
                verification=(verification.as_dict() if verification else None),
            )
            logger.info(
                "job %s succeeded with %s/%s fetched/stored rows (%s)",
                job["job_id"],
                outcome.rows_fetched,
                outcome.rows_inserted,
                outcome.completion_status,
            )
        return True

    def run_forever(self) -> None:
        logger.info(
            "collection worker %s started for resources=%s",
            self._worker_id,
            self._resource_classes or "*",
        )
        while not self._stopping:
            try:
                now = time.monotonic()
                if now - self._last_reclaim_at >= JOB_RECLAIM_INTERVAL_SECONDS:
                    recovered = self._repository.recover_stale(JOB_STALE_AFTER_SECONDS)
                    if recovered:
                        logger.warning("requeued %s stale jobs", recovered)
                    self._last_reclaim_at = now
                processed = self.run_once()
            except Exception:
                logger.exception("job queue is temporarily unavailable")
                processed = False
            if not processed:
                time.sleep(self._poll_interval)
        logger.info("collection worker stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    component = os.getenv("WORKER_COMPONENT", "worker").strip()
    if not component:
        raise ValueError("WORKER_COMPONENT cannot be empty")
    resource_classes = parse_resource_classes(os.getenv("WORKER_RESOURCE_CLASSES"))
    worker = JobWorker(
        JobRepository(),
        worker_id=f"{component}-{os.uname().nodename}-{uuid4().hex[:8]}",
        resource_classes=resource_classes,
    )
    heartbeat = Heartbeat(
        component,
        details={
            "resource_classes": list(resource_classes) if resource_classes else ["*"]
        },
    ).start()
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    try:
        worker.run_forever()
    finally:
        heartbeat.stop()


if __name__ == "__main__":
    main()
