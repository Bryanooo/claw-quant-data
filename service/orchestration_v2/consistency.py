"""Read-only cross-checks for the V2 control plane.

The control plane is authoritative for what actually runs, but three other
places describe the same facts and none of them were cross-checked:

* ``public.sys_source_endpoint`` — the flat, unversioned code-mirrored registry.
* ``definition.scope_contract.cadence`` — the compiled cadence label the
  console renders as "scheduled".
* ``definition.schedule.mode`` — what the scheduler actually honours.

All three are derived from one code registry, so a drift silently turns into a
console that advertises a schedule the scheduler never dispatches.  Every
check here is read-only and never mutates control-plane state.
"""

from __future__ import annotations

from datetime import timedelta

from typing import Any

from service.clock import business_today
from service.orchestration_v2.automation_status import supplementary_automation
from service.orchestration_v2.recovery_policy import (
    DEFERRED_REASONS,
    DEFERRED_RESEARCH_DATASETS,
)

# Cadence label -> the cron expression the bootstrap compiles for it.  A
# definition dispatched by a cron whose expression resolves to a different
# frequency is a real scheduling drift, not merely a labelling nit.
CADENCE_CRON_EXPRESSIONS = {
    "daily": "15 19,23 * * *",
    "weekly": "30 20 * * 5",
    "monthly": "30 20 1 * *",
    "quarterly": "0 21 1 1,4,7,10 *",
}

# Cadence labels that imply the scheduler must dispatch on a clock.
CLOCK_CADENCES = frozenset(CADENCE_CRON_EXPRESSIONS)

# How long a task may stay silent before it counts as "never dispatched".
# A monthly job that ran three weeks ago is healthy; a daily job that ran
# three weeks ago is not, so one fixed window would flag every slow cadence.
# Only clock-driven schedules are checked for silence.  A dependency-driven
# task runs whenever its inputs become ready, so it has no independent clock
# to be late against; judging it here would flag every monthly derivation
# during the weeks it is legitimately waiting for its period to close.
IDLE_TOLERANCE_DAYS = {
    "daily": 7,
    "weekly": 21,
    "monthly": 45,
    "quarterly": 110,
}

# Wider than the slowest tolerance so one query serves every cadence.
_ACTIVITY_LOOKBACK_DAYS = 120


def cron_frequency(expression: str | None) -> str | None:
    """Classify a five-field cron expression as a cadence label.

    Returns ``None`` for anything that cannot be resolved to a single fixed
    frequency; an unresolvable cron must stay visible rather than be reported
    as consistent.
    """

    fields = (expression or "").split()
    if len(fields) != 5:
        return None
    minute, hour, day_of_month, month, day_of_week = fields
    if "*" in minute or "*" in hour:
        return None
    if day_of_month == "*" and day_of_week == "*":
        return "daily" if month == "*" else None
    if day_of_month == "*" and day_of_week != "*":
        return "weekly"
    if day_of_month != "*" and day_of_week == "*":
        days = [item for item in day_of_month.split(",") if item]
        if len(days) != 1:
            return None
        months = [item for item in month.split(",") if item]
        # A single day-of-month across several months is a quarterly cron;
        # the same day every month is monthly; a single month is yearly.
        if month != "*" and len(months) > 1:
            return "quarterly"
        return "monthly" if month == "*" else "yearly"
    return None


def _cadence_drift_items(definitions: list[dict]) -> list[dict]:
    items: list[dict] = []
    for row in definitions:
        if row.get("lifecycle_status") != "active":
            continue
        task_key = row.get("task_key")
        cadence = row.get("cadence")
        mode = row.get("schedule_mode")
        expression = row.get("schedule_expression")
        observed = cron_frequency(expression) if mode == "cron" else None

        if cadence in CLOCK_CADENCES and mode == "disabled":
            deferred = task_key in DEFERRED_RESEARCH_DATASETS
            reason = DEFERRED_REASONS.get(task_key)
            items.append({
                "task_key": task_key,
                "kind": "labelled_but_disabled",
                # A deferred dataset is a deliberate decision: the clock label
                # is stale, but the stop itself is intended.  An unstated stop
                # is the dangerous case, because nobody recorded why.
                "severity": "low" if deferred else "high",
                "declared": deferred,
                "cadence": cadence,
                "schedule_mode": mode,
                "reason": reason,
                "detail": (
                    f"已声明退出常规采集：{reason}"
                    if deferred
                    else (
                        f"定义标注为 {cadence}，但调度模式是 disabled 且没有声明原因；"
                        "控制台会显示为已调度，调度器实际不会派发"
                    )
                ),
            })
            continue
        if mode == "cron" and cadence not in CLOCK_CADENCES:
            items.append({
                "task_key": task_key,
                "kind": "cron_without_cadence",
                "severity": "medium",
                "cadence": cadence,
                "schedule_mode": mode,
                "schedule_expression": expression,
                "detail": f"按 cron 派发，但 cadence 标注为 {cadence}，二者来源不同",
            })
            continue
        if mode == "cron" and cadence in CLOCK_CADENCES and observed != cadence:
            items.append({
                "task_key": task_key,
                "kind": "cron_frequency_mismatch",
                "severity": "high",
                "cadence": cadence,
                "schedule_mode": mode,
                "schedule_expression": expression,
                "observed_frequency": observed,
                "detail": (
                    f"cadence 标注 {cadence}，cron 表达式解析为 "
                    f"{observed or 'unknown'}；实际运行频率与标注不一致"
                ),
            })
    return items


def cadence_drift(repository) -> dict[str, Any]:
    """Compare the cadence label, the schedule mode and the cron expression."""

    if not repository.schema_exists():
        return {"available": False, "items": [], "counts": {}}
    rows = repository.list_definitions(
        limit=1000,
        lifecycle_status="active",
        workflow_kind="acquisition",
    )
    items = _cadence_drift_items(rows)
    return {
        "available": True,
        "checked": len(rows),
        "items": items,
        "counts": _count_by_kind(items),
    }


def dispatch_drift(repository, *, lookback_days: int = 14) -> dict[str, Any]:
    """Compare what a definition claims against what actually ran.

    The scheduler dispatches from the code blueprint and the deferred set, not
    from ``task_definition.schedule``.  The two can disagree in both
    directions, and neither direction is visible from either side alone, so
    this check uses execution evidence as the independent referee.
    """

    if not repository.schema_exists():
        return {"available": False, "items": [], "counts": {}}
    definitions = repository.list_definitions(limit=1000, lifecycle_status="active")
    today = business_today()
    try:
        activity = repository.execution_activity_by_task(
            since=today - timedelta(days=_ACTIVITY_LOOKBACK_DAYS)
        )
    except Exception:  # pragma: no cover - control plane unavailable
        return {"available": False, "items": [], "counts": {}}
    active_keys = {row.get("task_key") for row in definitions}

    items: list[dict] = []
    for row in definitions:
        task_key = row.get("task_key")
        mode = row.get("schedule_mode")
        evidence = activity.get(task_key)
        succeeded = int(evidence["succeeded"]) if evidence else 0
        last_finished = evidence["last_finished"] if evidence else None

        if mode == "disabled" and succeeded > 0:
            supplementary = supplementary_automation(task_key, active_keys)
            reason = (supplementary or {}).get('label')
            items.append({
                "task_key": task_key,
                "kind": "disabled_but_running",
                # A code-owned supplementary trigger is a declared design; the
                # definition merely documents that the routine dispatcher skips
                # it.  Undeclared activity means nobody recorded why.
                "severity": "low" if reason else "high",
                "declared": bool(reason),
                "reason": reason,
                "schedule_mode": mode,
                "recent_successes": succeeded,
                "last_finished": str(last_finished) if last_finished else None,
                "detail": (
                    f"定义声明已停用，但近期仍有 {succeeded} 次成功执行；"
                    f"已声明的代码侧补充触发：{reason}"
                    if reason
                    else (
                        f"定义声明已停用，但近期仍有 {succeeded} 次成功执行，"
                        "且没有任何补充触发声明；调度器与定义层的权威不一致"
                    )
                ),
            })
            continue

        tolerance = IDLE_TOLERANCE_DAYS.get(row.get("cadence"))
        if mode == "cron" and tolerance is not None:
            if last_finished is None:
                idle_days = None
            else:
                finished = last_finished.date() if hasattr(last_finished, "date") else last_finished
                idle_days = (today - finished).days
            if idle_days is None or idle_days > tolerance:
                items.append({
                    "task_key": task_key,
                    "kind": "scheduled_but_idle",
                    "severity": "medium",
                    "schedule_mode": mode,
                    "cadence": row.get("cadence"),
                    "idle_days": idle_days,
                    "tolerance_days": tolerance,
                    "detail": (
                        f"定义按 {mode} 派发（{row.get('cadence')}），但"
                        + ("从未产生执行实例" if idle_days is None
                           else f"已 {idle_days} 天没有执行，超过 {tolerance} 天容忍")
                        + "；调度器可能未覆盖该任务，或已被代码侧策略排除"
                    ),
                })
    return {
        "available": True,
        "checked": len(definitions),
        "lookback_days": _ACTIVITY_LOOKBACK_DAYS,
        "items": items,
        "counts": _count_by_kind(items),
    }


def endpoint_registry_drift(repository) -> dict[str, Any]:
    """Compare the flat registry against the versioned contract layer.

    Only ``scheduled_pull`` endpoints are expected to reach the contract
    layer; query-through routes legitimately stay in the registry alone.  The
    dangerous direction is the opposite one: a governed contract whose
    registry row has disappeared.
    """

    if not repository.schema_exists():
        return {"available": False, "items": [], "counts": {}}
    try:
        pairs = repository.endpoint_registry_pairs()
    except Exception:  # pragma: no cover - registry table absent
        return {"available": False, "items": [], "counts": {}}

    items: list[dict] = []
    for pair in pairs:
        registered = pair["registered"]
        governed = pair["governed"]
        mode = pair["acquisition_mode"]
        if governed and not registered:
            items.append({
                "source_id": pair["source_id"],
                "endpoint_key": pair["endpoint_key"],
                "kind": "governed_without_registry",
                "severity": "high",
                "detail": "契约层已生效，但注册表没有对应行；代码与库已分叉",
            })
            continue
        if registered and not governed and mode == "scheduled_pull":
            items.append({
                "source_id": pair["source_id"],
                "endpoint_key": pair["endpoint_key"],
                "kind": "scheduled_pull_not_governed",
                "severity": "medium",
                "detail": "注册为定时采集，但没有进入版本化契约层；无法审计与灰度",
            })
            continue
        if (
            registered
            and governed
            and pair["registry_cadence"]
            and pair["contract_cadence"]
            and pair["registry_cadence"] != pair["contract_cadence"]
        ):
            items.append({
                "source_id": pair["source_id"],
                "endpoint_key": pair["endpoint_key"],
                "kind": "cadence_label_mismatch",
                "severity": "low",
                "registry_cadence": pair["registry_cadence"],
                "contract_cadence": pair["contract_cadence"],
                "detail": "注册表与契约层的 cadence 标注不同",
            })
    return {
        "available": True,
        "checked": len(pairs),
        "items": items,
        "counts": _count_by_kind(items),
    }


def derivation_rollout_drift(repository) -> dict[str, Any]:
    """Compare the code-owned blueprint against what is actually published.

    The dashboard renders the blueprint, so an unpublished transformation still
    looks like a live job.  This check makes the gap explicit.
    """

    from service.orchestration_v2.catalog import transformation_task_blueprints

    blueprints = {task.task_key: task for task in transformation_task_blueprints()}
    if not repository.schema_exists():
        return {
            "available": False,
            "items": [],
            "counts": {},
            "blueprint_total": len(blueprints),
        }
    active = {
        row["task_key"]
        for row in repository.list_definitions(
            limit=1000, lifecycle_status="active", workflow_kind="transformation"
        )
    }
    items: list[dict] = []
    for task_key in sorted(blueprints):
        if task_key in active:
            continue
        items.append({
            "task_key": task_key,
            "kind": "blueprint_not_published",
            "severity": "medium",
            "detail": (
                f"代码蓝图声明了 {task_key}，但库里没有 active 版本；"
                "页面按蓝图展示，实际不会运行"
            ),
        })
    return {
        "available": True,
        "blueprint_total": len(blueprints),
        "published_total": len(active),
        "items": items,
        "counts": _count_by_kind(items),
    }


def consistency_report(repository) -> dict[str, Any]:
    """Run every cross-check and summarise them for the console."""

    checks = {
        "cadence": cadence_drift(repository),
        "dispatch": dispatch_drift(repository),
        "endpoint_registry": endpoint_registry_drift(repository),
        "derivation_rollout": derivation_rollout_drift(repository),
    }
    items: list[dict] = []
    for name, check in checks.items():
        for item in check["items"]:
            items.append({"check": name, **item})
    return {
        "checks": checks,
        "items": items,
        "total": len(items),
        "by_severity": _count_by(items, "severity"),
        "notice": (
            "一致性检查只做比对，不修改任何控制平面状态；"
            "high 项意味着页面展示与调度行为已经分叉"
        ),
    }


def _count_by_kind(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    return counts


def _count_by(items: list[dict], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = item.get(field) or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts
