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

# Datasets intentionally outside the current research programme remain
# queryable so previously collected rows and lineage are preserved, but no
# scheduler, initialization campaign, or recovery planner may spend provider
# quota on them.  Re-enabling one is a code-reviewed scope decision rather
# than an accidental side effect of a full-library audit.
DEFERRED_RESEARCH_DATASETS = frozenset({"us_daily"})

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
