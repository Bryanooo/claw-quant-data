"""V2-only APScheduler entry point.

The scheduler creates logical V2 instances. Provider pagination, symbols and
partitions are exhausted inside an execution's acquire node.
"""

from __future__ import annotations

import logging
import signal
import time
from datetime import time as wall_time, timedelta

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

from service.clock import business_now
from service.data_coverage.reconciliation import CoverageRuleReconciler
from service.data_coverage.service import submit_scheduled_coverage_audits
from service.heartbeat import Heartbeat
from service.initialization.service import InitializationService
from service.config import (
    APP_REVISION,
    V2_TRANSIENT_RECOVERY_BATCH_LIMIT,
    V2_TRANSIENT_RECOVERY_COOLDOWN_SECONDS,
    V2_TRANSIENT_RECOVERY_MAX_ROUNDS,
)
from service.orchestration_v2.gap_repair import (
    create_repair_executions,
    dispatch_overdue_empty_rechecks,
    plan_current_repairs,
)
from service.orchestration_v2.repository import OrchestrationV2Repository
from service.orchestration_v2.late_repair import (
    LATE_REPAIR_HOURS,
    LATE_REPAIR_MINUTE,
    LATE_PUBLISHED_DATASETS,
)
from service.orchestration_v2.scheduling import (
    dispatch_due_acquisitions,
    dispatch_ready_transformations,
    is_trade_day,
)
from service.research.local_factors.provider_validation import (
    revalidate_provider_pending_dates,
)


logger = logging.getLogger("scheduler-v2")
_ACTIVE_SCHEDULER: BackgroundScheduler | None = None


def run_scheduler_heartbeat() -> None:
    heartbeat = getattr(run_scheduler_heartbeat, "_heartbeat", None)
    if heartbeat is None:
        heartbeat = Heartbeat(
            "scheduler",
            details={"orchestration_version": 2, "engine": "orchestration_v2"},
        )
        run_scheduler_heartbeat._heartbeat = heartbeat
    heartbeat.beat()


def run_v2_policy_dispatch() -> int:
    now = business_now()
    from service.orchestration_v2.scheduling import dispatch_weekly_reference_profiles
    reference = dispatch_weekly_reference_profiles(now.date())
    from service.orchestration_v2.dated_reference import dispatch as dispatch_dated
    reference['errors'].update(dispatch_dated(OrchestrationV2Repository(), now))
    result = dispatch_due_acquisitions(
        now.date(),
        include_current_daily=now.hour >= 19,
        next_morning_released=(
            now.time().replace(tzinfo=None) >= wall_time(9, 15)
        ),
    )
    result["errors"].update({f'reference:{key}': value for key, value in reference['errors'].items()})
    if result["errors"]:
        raise RuntimeError(
            "V2 routine dispatch was incomplete: "
            + ", ".join(sorted(result["errors"]))
        )
    logger.info(
        "V2 dispatch eligible=%s created=%s existing=%s manual=%s",
        result["eligible"], result["created"], result["existing"],
        result["manual_not_scheduled"],
    )
    return int(result["created"])


def run_data_coverage_dispatch() -> int:
    result = submit_scheduled_coverage_audits()
    logger.info("strict audits created=%s total=%s", result["created"], result["total"])
    return int(result["created"])


def run_financial_disclosure_refresh() -> int:
    from service.orchestration_v2.financial_refresh import refresh_financial_disclosures
    result = refresh_financial_disclosures(business_now().date(), OrchestrationV2Repository())
    logger.info('Financial disclosure refresh: %s', result)
    return int(result['created'])


def run_v2_transformation_dispatch() -> int:
    result = dispatch_ready_transformations()
    if result["errors"]:
        raise RuntimeError(
            "V2 transformation dispatch was incomplete: "
            + ", ".join(sorted(result["errors"]))
        )
    logger.info(
        "V2 transformation dispatch eligible=%s created=%s existing=%s waiting=%s",
        result["eligible"], result["created"], result["existing"],
        len(result["waiting"]),
    )
    return int(result["created"])


def run_factor_provider_revalidation() -> int:
    """Refresh pending comparison evidence after Tushare publishes it."""

    from service.orchestration_v2.factor_reference import dispatch_reference_sample
    from service.clock import business_today
    dispatch_reference_sample(OrchestrationV2Repository(), business_today())
    result = revalidate_provider_pending_dates(limit=8)
    if result["failed"]:
        raise RuntimeError(
            "factor provider revalidation was incomplete: "
            + ", ".join(
                f"{day}={message}" for day, message in result["failed"].items()
            )
        )
    if result["completed"]:
        logger.info(
            "factor provider evidence refreshed for %s",
            ",".join(result["completed"]),
        )
    return len(result["completed"])


def run_coverage_rule_reconciler() -> int:
    requeued = CoverageRuleReconciler().reconcile()
    count = sum(requeued.values())
    repository = OrchestrationV2Repository()
    revoked = repository.revoke_obsolete_daily_certificates()
    if revoked:
        logger.warning("revoked %s obsolete ready states contradicted by newer daily audits", revoked)
    resolved = repository.reconcile_resolved_attention_executions()
    duplicates = repository.reconcile_duplicate_attention_executions()
    redundant = repository.reconcile_redundant_pending_executions()
    stale_contracts = repository.reconcile_stale_audit_contract_executions()
    normalized_priorities = repository.promote_quota_guarded_history_executions()
    if count:
        logger.warning(
            "requeued %s stale-rule audits across %s datasets",
            count,
            len(requeued),
        )
    if resolved:
        logger.info("superseded %s stale resolved attention executions", resolved)
    if duplicates:
        logger.info("superseded %s duplicate attention attempts", duplicates)
    if redundant:
        logger.info("superseded %s redundant pending executions", redundant)
    if stale_contracts:
        logger.warning(
            "superseded %s executions with stale audit contracts",
            stale_contracts,
        )
    if normalized_priorities:
        logger.info(
            "normalized %s quota-guarded history priorities",
            normalized_priorities,
        )
    return (
        count + resolved + duplicates + redundant + stale_contracts
        + normalized_priorities + revoked
    )


def run_transient_failure_reconciler() -> int:
    """Resume bounded transient failures after connectivity can recover."""

    recovered = OrchestrationV2Repository().recover_transient_attention_executions(
        cooldown_seconds=V2_TRANSIENT_RECOVERY_COOLDOWN_SECONDS,
        max_recovery_rounds=V2_TRANSIENT_RECOVERY_MAX_ROUNDS,
        limit=V2_TRANSIENT_RECOVERY_BATCH_LIMIT,
    )
    if recovered:
        logger.warning(
            "automatically requeued %s transient V2 failures", len(recovered)
        )
    return len(recovered)


def run_v2_late_repair_dispatch() -> int:
    """Reacquire late-published daily partitions in fresh V2 executions.

    A terminal execution retry resumes from its failed validation/publish node;
    it deliberately does not repeat a successful acquire node.  Late upstream
    publication therefore needs a new repair execution, not an operator retry
    of the old instance.  Keep this bounded to recent dates and one idempotent
    repair generation per Shanghai business day.
    """

    now = business_now()
    if not is_trade_day(now.date()):
        logger.info("skip V2 late repair on non-trading day %s", now.date())
        return 0
    repository = OrchestrationV2Repository()
    proposals = plan_current_repairs(
        repository,
        start_date=now.date() - timedelta(days=7),
        end_date=now.date(),
        included_datasets=LATE_PUBLISHED_DATASETS,
    )
    result = create_repair_executions(
        repository,
        proposals=proposals,
        limit=500,
        actor_revision=APP_REVISION,
        trigger_source="schedule",
        idempotency_prefix=(
            "v2:scheduled-late-repair:"
            f"{now.date().isoformat()}"
        ),
        frozen_scope_extra={"dispatch": "v2_scheduled_late_repair"},
    )
    logger.info(
        "V2 late repair planned=%s created=%s existing=%s",
        len(proposals), result["created"], result["existing"],
    )
    overdue = (dispatch_overdue_empty_rechecks(repository, now.date())
               if now.hour == 18 else {})
    return int(result["created"]) + int(overdue.get("created", 0))


def run_initialization_reconciler() -> int:
    campaign = InitializationService().reconcile_active()
    if not campaign:
        return 0
    logger.info(
        "V2 initialization %s status=%s completed=%s/%s",
        campaign["initialization_id"], campaign["status"],
        campaign["completed_steps"], campaign["planned_steps"],
    )
    return 1


def create_scheduler(*, set_active: bool = True, **_ignored) -> BackgroundScheduler:
    global _ACTIVE_SCHEDULER
    scheduler = BackgroundScheduler(
        executors={"default": ThreadPoolExecutor(max_workers=3)},
        timezone="Asia/Shanghai",
    )
    scheduler.add_job(
        run_history_continuation, 'interval', minutes=1,
        id='v2_history_continuation', name='已验收历史窗口自动接续',
        replace_existing=True, coalesce=True, max_instances=1,
    )
    scheduler.add_job(
        run_scheduler_heartbeat, "interval", seconds=15,
        id="service_heartbeat", name="V2 调度器心跳", replace_existing=True,
        coalesce=True, max_instances=1, next_run_time=business_now(),
    )
    scheduler.add_job(
        run_v2_policy_dispatch, "cron", hour="7,9,13,19,23", minute=15,
        id="v2_policy_dispatch", name="V2 日/周/月/季度任务派发",
        replace_existing=True, coalesce=True, max_instances=1,
        misfire_grace_time=21600,
        next_run_time=business_now() + timedelta(seconds=5),
    )
    scheduler.add_job(
        run_financial_disclosure_refresh, 'cron', hour=18, minute=20,
        id='v2_financial_disclosure_refresh', name='最近两报告期财报披露滚动更新',
        replace_existing=True, coalesce=True, max_instances=1,
        misfire_grace_time=14400,
    )
    scheduler.add_job(
        run_v2_transformation_dispatch, "interval", minutes=2,
        id="v2_transformation_dispatch", name="V2 派生任务依赖派发",
        replace_existing=True, coalesce=True, max_instances=1,
        next_run_time=business_now() + timedelta(seconds=30),
    )
    scheduler.add_job(
        run_factor_provider_revalidation, "interval", minutes=15,
        id="factor_provider_revalidation",
        name="本地因子供应商证据延迟复验",
        replace_existing=True, coalesce=True, max_instances=1,
        next_run_time=business_now() + timedelta(minutes=3),
    )
    scheduler.add_job(
        run_data_coverage_dispatch, "cron", hour=20, minute=30,
        id="v2_coverage_dispatch", name="V2 全数据集严格审计",
        replace_existing=True, coalesce=True, max_instances=1,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_coverage_rule_reconciler, "interval", minutes=15,
        id="v2_coverage_rule_reconciler", name="V2 审计规则版本对账",
        replace_existing=True, coalesce=True, max_instances=1,
    )
    scheduler.add_job(
        run_transient_failure_reconciler, "interval", minutes=2,
        id="v2_transient_failure_reconciler",
        name="V2 瞬时故障自动恢复",
        replace_existing=True, coalesce=True, max_instances=1,
    )
    scheduler.add_job(
        run_v2_late_repair_dispatch,
        "cron",
        hour=",".join(str(hour) for hour in LATE_REPAIR_HOURS),
        minute=LATE_REPAIR_MINUTE,
        id="v2_late_repair_dispatch", name="V2 晚发布数据自动补采",
        replace_existing=True, coalesce=True, max_instances=1,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        run_initialization_reconciler, "interval", seconds=30,
        id="v2_initialization_reconciler", name="V2 初始化协调器",
        replace_existing=True, coalesce=True, max_instances=1,
    )
    if set_active:
        _ACTIVE_SCHEDULER = scheduler
    return scheduler


def run_history_continuation():
    from service.orchestration_v2.history_continuation import advance_chip_history
    return advance_chip_history(OrchestrationV2Repository())['created']


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    scheduler = create_scheduler()
    scheduler.start()
    stopping = False

    def stop(*_args):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logger.info("V2 scheduler started with %s jobs", len(scheduler.get_jobs()))
    try:
        while not stopping:
            time.sleep(1)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
