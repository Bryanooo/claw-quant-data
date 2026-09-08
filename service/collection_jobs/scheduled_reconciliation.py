"""Recover verification for successful legacy dedicated scheduler jobs."""

from __future__ import annotations

from service.collection_jobs.repository import JobRepository
from service.collection_jobs.scheduled_verification import verify_scheduled_transport
from service.collection_jobs.verification import CollectionVerificationPlanner


class ScheduledCompletionReconciler:
    """Idempotently promote or audit recent unverified scheduled jobs."""

    def __init__(
        self,
        repository: JobRepository | None = None,
        planner: CollectionVerificationPlanner | None = None,
    ):
        self._repository = repository or JobRepository()
        self._planner = planner or CollectionVerificationPlanner()

    def reconcile(self, *, limit: int = 500) -> dict[str, int]:
        promoted = 0
        audits = 0
        for job in self._repository.list_unverified_scheduled(limit=limit):
            parameters = job.get("parameters") or {}
            evidence = verify_scheduled_transport(
                parameters.get("schedule_id", ""),
                parameters.get("scheduled_for"),
                int(job.get("rows_fetched") or 0),
            )
            if evidence:
                promoted += int(
                    self._repository.apply_transport_verification(
                        job["job_id"], evidence
                    )
                )
                continue
            if int(job.get("rows_fetched") or 0) <= 0:
                continue
            verification = self._planner.plan(job)
            if verification:
                audits += int(
                    self._repository.queue_verification(
                        job["job_id"], verification.as_dict()
                    )
                    is not None
                )
        return {"promoted": promoted, "audits_queued": audits}
