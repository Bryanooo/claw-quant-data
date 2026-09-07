"""Coverage audit use cases shared by HTTP, scheduler and auditor."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
import hashlib
from uuid import uuid4
from zoneinfo import ZoneInfo

from service.data_coverage.models import InvalidCoverageRequestError
from service.data_coverage.registry import COVERAGE_RULES, CoverageRuleRegistry
from service.data_coverage.repository import CoverageRepository
from service.clock import business_now


BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")
PARTITION_STATUSES = {"present", "partial", "missing", "pending", "observed_only"}
JOB_STATUSES = {"queued", "running", "success", "failed"}


def local_today() -> date:
    return business_now().astimezone(BUSINESS_TIMEZONE).date()


class CoverageService:
    def __init__(
        self,
        repository: CoverageRepository | None = None,
        registry: CoverageRuleRegistry = COVERAGE_RULES,
    ):
        self._repository = repository or CoverageRepository()
        self._registry = registry

    def submit_audits(
        self,
        dataset_names: list[str] | None = None,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        rules = (
            [self._registry.get(name) for name in dict.fromkeys(dataset_names)]
            if dataset_names
            else list(self._registry.scheduled())
        )
        non_auditable = [rule.dataset_name for rule in rules if not rule.auditable]
        if non_auditable:
            raise InvalidCoverageRequestError(
                "datasets do not have date partitions: " + ", ".join(non_auditable)
            )
        today = local_today()
        resolved_end = end_date or today
        if resolved_end > today:
            raise InvalidCoverageRequestError("end_date must not be in the future")
        base_key = idempotency_key or f"manual-{uuid4().hex}"
        jobs = []
        created_count = 0
        for rule in rules:
            resolved_start = start_date or (
                resolved_end - timedelta(days=rule.default_lookback_days)
            )
            if resolved_start > resolved_end:
                raise InvalidCoverageRequestError(
                    "start_date must not be later than end_date"
                )
            if (resolved_end - resolved_start).days > 3660:
                raise InvalidCoverageRequestError(
                    "one audit may cover at most 3660 days"
                )
            raw_key = f"{base_key}:{rule.dataset_name}"
            job_key = (
                raw_key
                if len(raw_key) <= 160
                else f"coverage-{hashlib.sha256(raw_key.encode()).hexdigest()}"
            )
            job, created = self._repository.create_job(
                rule.dataset_name,
                resolved_start,
                resolved_end,
                idempotency_key=job_key,
            )
            jobs.append(job)
            created_count += int(created)
        return {
            "created": created_count,
            "total": len(jobs),
            "jobs": jobs,
        }

    def list_jobs(self, *, status: str | None, limit: int) -> list[dict]:
        if status and status not in JOB_STATUSES:
            raise InvalidCoverageRequestError(f"unsupported job status: {status}")
        return self._repository.list_jobs(status=status, limit=limit)

    def overview(self) -> dict:
        latest = self._repository.latest_audits()
        missing_by_dataset = self._repository.recent_missing_by_dataset(limit=10)
        datasets = []
        for rule in self._registry.list():
            audit = latest.get(rule.dataset_name)
            if audit and isinstance(audit.get("coverage_ratio"), Decimal):
                audit["coverage_ratio"] = float(audit["coverage_ratio"])
            datasets.append(
                {
                    "dataset": rule.dataset_name,
                    "strategy": rule.strategy.value,
                    "description": rule.description,
                    "coverage_level": rule.coverage_level,
                    "auditable": rule.auditable,
                    "scheduled": rule.scheduled,
                    "release_after": (
                        rule.release_after.isoformat(timespec="minutes")
                        if rule.release_after
                        else None
                    ),
                    "detects_missing_partitions": rule.detects_missing_partitions,
                    "latest": audit,
                    "recent_missing": missing_by_dataset.get(rule.dataset_name, []),
                }
            )
        queue = self._repository.queue_counts()
        audited = [item for item in datasets if item["latest"]]
        scheduled_auditable = [
            item for item in datasets
            if item["scheduled"] and item["auditable"]
        ]
        return {
            "generated_at": datetime.now(BUSINESS_TIMEZONE),
            "summary": {
                "datasets": len(datasets),
                "classified": len(datasets),
                "auditable": sum(item["auditable"] for item in datasets),
                "scheduled": sum(item["scheduled"] for item in datasets),
                "expected_partition_rules": sum(
                    item["coverage_level"] == "expected_partitions"
                    for item in datasets
                ),
                "observed_partition_rules": sum(
                    item["coverage_level"] == "observed_partitions"
                    for item in datasets
                ),
                "non_temporal": sum(
                    item["coverage_level"] == "not_applicable"
                    for item in datasets
                ),
                "audited": len(audited),
                "scheduled_audited": sum(
                    bool(item["latest"]) for item in scheduled_auditable
                ),
                "scheduled_unaudited": sum(
                    not item["latest"] for item in scheduled_auditable
                ),
                "optional_unaudited": sum(
                    item["auditable"]
                    and not item["scheduled"]
                    and not item["latest"]
                    for item in datasets
                ),
                "with_gaps": sum(
                    item["latest"]["status"] == "gaps" for item in audited
                ),
                "missing_partitions": sum(
                    item["latest"]["missing_partitions"] for item in audited
                ),
                "partial_partitions": sum(
                    item["latest"].get("partial_partitions", 0) for item in audited
                ),
                **queue,
            },
            "datasets": datasets,
        }

    def list_partitions(
        self,
        dataset_name: str,
        *,
        start_date: date | None,
        end_date: date | None,
        status: str | None,
        limit: int,
    ) -> dict:
        rule = self._registry.get(dataset_name)
        if status and status not in PARTITION_STATUSES:
            raise InvalidCoverageRequestError(
                f"unsupported partition status: {status}"
            )
        if start_date and end_date and start_date > end_date:
            raise InvalidCoverageRequestError(
                "start_date must not be later than end_date"
            )
        rows = (
            self._repository.list_partitions(
                dataset_name,
                start_date=start_date,
                end_date=end_date,
                status=status,
                limit=limit,
            )
            if rule.auditable
            else []
        )
        return {
            "dataset": dataset_name,
            "strategy": rule.strategy.value,
            "coverage_level": rule.coverage_level,
            "auditable": rule.auditable,
            "scheduled": rule.scheduled,
            "detects_missing_partitions": rule.detects_missing_partitions,
            "partitions": rows,
        }


def submit_scheduled_coverage_audits(
    today: date | None = None,
    *,
    now: datetime | None = None,
) -> dict:
    current = (now or business_now()).astimezone(BUSINESS_TIMEZONE)
    today = today or current.date()
    # Scheduler startup intentionally performs an immediate bounded audit, but
    # that pre-release snapshot must not consume the idempotency key used by
    # the 09:30 post-publication audit.  One stable key per phase also prevents
    # repeated container restarts from producing unbounded duplicate scans.
    phase = "post-release" if current.time().replace(tzinfo=None) >= time(9, 30) else "pre-release"
    return CoverageService().submit_audits(
        end_date=today,
        idempotency_key=f"scheduled-{today.isoformat()}-{phase}",
    )
