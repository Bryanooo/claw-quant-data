"""Deterministic V2 repair-instance planning from audited data gaps."""

from __future__ import annotations

from dataclasses import dataclass
from calendar import monthrange
from datetime import date, timedelta

from service.orchestration_v2.contracts import DatasetAuditContract


@dataclass(frozen=True, slots=True)
class RepairInstanceProposal:
    task_key: str
    observation_key: str
    observation_start: date | None
    observation_end: date | None
    observation_period: str
    datasets: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def idempotency_key(self) -> str:
        base = f"v2:repair:{self.task_key}:{self.observation_key}"
        if (
            self.observation_start is not None
            and self.observation_end is not None
            and self.observation_start != self.observation_end
        ):
            return (
                f"{base}:{self.observation_start.isoformat()}:"
                f"{self.observation_end.isoformat()}"
            )
        return base


def observation_identity(partition_date: date, granularity: str) -> str:
    """Normalize one materialized gap to its task execution period."""
    if granularity == "day":
        return partition_date.isoformat()
    if granularity == "week":
        iso_year, iso_week, _ = partition_date.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if granularity == "month":
        return partition_date.strftime("%Y-%m")
    if granularity == "quarter":
        return f"{partition_date.year}-Q{((partition_date.month - 1) // 3) + 1}"
    raise ValueError(f"cannot build a temporal observation key for {granularity}")


def observation_bounds(partition_date: date, granularity: str) -> tuple[date, date]:
    """Expand a materialized partition date to its full logical period."""
    if granularity == "day":
        return partition_date, partition_date
    if granularity == "week":
        start = partition_date - timedelta(days=partition_date.weekday())
        return start, start + timedelta(days=6)
    if granularity == "month":
        start = date(partition_date.year, partition_date.month, 1)
        return start, date(
            partition_date.year,
            partition_date.month,
            monthrange(partition_date.year, partition_date.month)[1],
        )
    if granularity == "quarter":
        start_month = ((partition_date.month - 1) // 3) * 3 + 1
        end_month = start_month + 2
        return (
            date(partition_date.year, start_month, 1),
            date(
                partition_date.year,
                end_month,
                monthrange(partition_date.year, end_month)[1],
            ),
        )
    raise ValueError(f"cannot build temporal bounds for {granularity}")


def plan_period_repairs(
    *,
    task_key: str,
    contracts: tuple[DatasetAuditContract, ...],
    problem_partitions: dict[str, dict[date, str]],
) -> tuple[RepairInstanceProposal, ...]:
    """Create at most one repair proposal per task and logical period.

    Several output datasets can fail for the same period; they are repaired by
    the same task execution.  Pages, symbols, exchanges selected inside the
    task and upstream batches never become child executions.
    """
    by_period: dict[str, dict] = {}
    for contract in contracts:
        if contract.audit_mode not in {
            "expected_partition", "observed_scope_transport"
        }:
            continue
        for partition_date, reason in problem_partitions.get(
            contract.dataset_name, {}
        ).items():
            key = observation_identity(
                partition_date,
                contract.period_granularity,
            )
            period = by_period.setdefault(key, {
                "dates": [],
                "datasets": set(),
                "reasons": set(),
                "granularities": set(),
            })
            period["dates"].append(partition_date)
            period["datasets"].add(contract.dataset_name)
            period["reasons"].add(reason)
            period["granularities"].add(contract.period_granularity)

    proposals = []
    for key, value in sorted(by_period.items(), reverse=True):
        if len(value["granularities"]) != 1:
            raise ValueError(
                f"task {task_key} mixes period granularities for {key}: "
                f"{sorted(value['granularities'])}"
            )
        granularity = next(iter(value["granularities"]))
        start, end = observation_bounds(min(value["dates"]), granularity)
        proposals.append(RepairInstanceProposal(
            task_key=task_key,
            observation_key=key,
            observation_start=start,
            observation_end=end,
            observation_period=key,
            datasets=tuple(sorted(value["datasets"])),
            reasons=tuple(sorted(value["reasons"])),
        ))
    return tuple(proposals)


def validate_single_period_scope(
    *,
    contract: DatasetAuditContract,
    observation_start: date | None,
    observation_end: date | None,
    observation_key: str,
) -> None:
    """Reject V2 backfills that accidentally span several logical periods."""
    if contract.period_granularity in {"snapshot", "dependency"}:
        return
    if observation_start is None or observation_end is None:
        raise ValueError("temporal executions require observation start and end")
    start_key = observation_identity(
        observation_start, contract.period_granularity
    )
    end_key = observation_identity(observation_end, contract.period_granularity)
    if start_key != end_key or observation_key != start_key:
        raise ValueError(
            "one V2 execution must cover exactly one logical observation period"
        )
