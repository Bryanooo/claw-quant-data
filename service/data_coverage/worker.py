"""Independent worker for database-heavy coverage audits."""

import logging
import os
import signal
import time
from datetime import timedelta
from uuid import uuid4

from service.config import COVERAGE_POLL_INTERVAL_SECONDS, COVERAGE_STALE_AFTER_SECONDS
from service.config import JOB_RECLAIM_INTERVAL_SECONDS
from service.data_coverage.calculator import CoverageCalculator
from service.data_coverage.registry import COVERAGE_RULES
from service.data_coverage.repository import CoverageRepository
from service.data_coverage.repair import CoverageRepairPlanner
from service.collection_jobs.repository import JobRepository
from service.data_coverage.models import CoverageStrategy
from service.heartbeat import Heartbeat

logger = logging.getLogger("coverage-auditor")


class CoverageWorker:
    def __init__(
        self,
        repository: CoverageRepository,
        *,
        worker_id: str | None = None,
        poll_interval: float = COVERAGE_POLL_INTERVAL_SECONDS,
        collection_job_repository: JobRepository | None = None,
    ):
        self._repository = repository
        self._calculator = CoverageCalculator(repository)
        self._repair_planner = CoverageRepairPlanner()
        self._worker_id = worker_id or f"{os.uname().nodename}-{uuid4().hex[:8]}"
        self._poll_interval = poll_interval
        self._stopping = False
        self._last_reclaim_at = 0.0
        self._collection_jobs = collection_job_repository or JobRepository()

    def stop(self, *_args) -> None:
        self._stopping = True

    def run_once(self) -> bool:
        job = self._repository.claim_next(self._worker_id)
        if not job:
            return False
        logger.info(
            "auditing %s from %s to %s",
            job["dataset_name"],
            job["start_date"],
            job["end_date"],
        )
        try:
            rule = COVERAGE_RULES.get(job["dataset_name"])
            result = self._calculator.audit(
                rule,
                job["start_date"],
                job["end_date"],
                as_of=(
                    job["end_date"]
                    + timedelta(
                        days=(
                            400
                            if rule.strategy == CoverageStrategy.REPORT_QUARTERLY
                            else rule.grace_days
                        )
                    )
                    if job.get("collection_job_id")
                    else None
                ),
            )
            audit_id = self._repository.save_audit(job["job_id"], result)
            if job.get("collection_job_id"):
                self._collection_jobs.apply_verification_result(
                    job["collection_job_id"],
                    audit_id=audit_id,
                    audit_status=result.status,
                    dataset_name=result.dataset_name,
                    missing_partitions=result.missing_partitions,
                    partial_partitions=result.partial_partitions,
                    coverage_ratio=result.coverage_ratio,
                )
            repair = self._repair_planner.submit(result)
            self._repository.finish_job(job["job_id"])
        except Exception as exc:
            logger.exception("coverage job %s failed", job["job_id"])
            status = self._repository.fail_or_requeue(
                job,
                f"{type(exc).__name__}: {exc}",
            )
            logger.info("coverage job %s moved to %s", job["job_id"], status)
        else:
            logger.info(
                "coverage job %s: %s present, %s missing",
                job["job_id"],
                result.present_partitions,
                result.missing_partitions,
            )
            if repair["created"]:
                logger.warning(
                    "coverage job %s submitted %s/%s safe repair jobs",
                    job["job_id"],
                    repair["created"],
                    repair["eligible"],
                )
        return True

    def run_forever(self) -> None:
        logger.info("coverage auditor %s started", self._worker_id)
        while not self._stopping:
            try:
                now = time.monotonic()
                if now - self._last_reclaim_at >= JOB_RECLAIM_INTERVAL_SECONDS:
                    recovered = self._repository.recover_stale(
                        COVERAGE_STALE_AFTER_SECONDS
                    )
                    if recovered:
                        logger.warning("requeued %s stale coverage jobs", recovered)
                    self._last_reclaim_at = now
                processed = self.run_once()
            except Exception:
                logger.exception("coverage queue is temporarily unavailable")
                processed = False
            if not processed:
                time.sleep(self._poll_interval)
        logger.info("coverage auditor stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    worker = CoverageWorker(CoverageRepository())
    heartbeat = Heartbeat("auditor").start()
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    try:
        worker.run_forever()
    finally:
        heartbeat.stop()


if __name__ == "__main__":
    main()
