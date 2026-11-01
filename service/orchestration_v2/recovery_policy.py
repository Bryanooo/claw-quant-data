"""Shared safety policy for automatic V2 gap recovery."""

from __future__ import annotations


# A single daily execution for these datasets expands into thousands of
# provider calls.  They require a quota-aware, resumable history plan and must
# never be handed to the generic per-partition auto-repair planner.
# ``us_daily`` is limited to one provider call per hour.  Without the shared
# task guard, every backfill worker wakes at the same boundary, claims a
# different date, and writes a defer event before one winner uses the slot.
# Serializing it also keeps generic repair planning from manufacturing a large
# set of independently competing executions.
QUOTA_GUARDED_DATASETS = frozenset({
    "cyq_perf",
    "factor_value",
    "index_weight",
    "us_daily",
})

# These tasks also fan out into thousands of provider requests and therefore
# may have only one active execution, but unlike quota-guarded history they
# must retain short explicit windows (for example cyq_chips <= 31 days).
# Keep execution serialization separate from history-scope validation so a
# safety gate cannot accidentally authorize one unbounded multi-year request.
SERIALIZED_ACQUISITION_TASKS = QUOTA_GUARDED_DATASETS | frozenset({
    "cyq_chips",
})

# Datasets intentionally outside the current research programme remain
# queryable so previously collected rows and lineage are preserved, but no
# scheduler, initialization campaign, or recovery planner may spend provider
# quota on them.  Re-enabling one is a code-reviewed scope decision rather
# than an accidental side effect of a full-library audit.
# factor_value is an internal reference endpoint. Only the separately frozen
# factor_reference_sample workflow may collect it automatically.
DEFERRED_RESEARCH_DATASETS = frozenset({"us_daily", "factor_value"})

# Why each deferred dataset is out of the routine programme.  The scheduler
# holds the real authority over dispatching, so a deferred task whose
# definition still claims a clock cadence needs a stated reason rather than a
# bare ``disabled`` that operators have to reverse-engineer.
DEFERRED_REASONS: dict[str, str] = {
    "us_daily": "策略停采：额度与范围限制，美股日线不在当前研究计划内",
    "factor_value": (
        "全市场采集停用；仅由 factor_reference_sample 冻结样本（30~128 只）"
        "自动采集，用于校验本地计算因子"
    ),
}

# These interfaces require an explicit scope or expand one missing date into a
# large fan-out.  The audit may expose their gaps, but the generic auditor must
# not turn those findings into provider calls automatically.
MANUAL_SCOPE_REPAIR_DATASETS = frozenset({
    "cyq_chips",
    "dc_index",
    "etf_sh_cons",
    "etf_sz_cons",
    "factor_value",
    "moneyflow_dc",
    "opt_daily",
})
