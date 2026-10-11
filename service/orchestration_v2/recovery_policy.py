"""Shared safety policy for automatic V2 gap recovery."""

from __future__ import annotations


# A single daily execution for these datasets expands into thousands of
# provider calls.  They require a quota-aware, resumable history plan and must
# never be handed to the generic per-partition auto-repair planner.
QUOTA_GUARDED_DATASETS = frozenset({"cyq_perf"})
