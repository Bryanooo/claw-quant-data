#!/usr/bin/env python3
"""Plan or create one V2 repair execution per confirmed logical period."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from service.config import APP_REVISION
from service.orchestration_v2.gap_repair import (
    create_repair_executions,
    plan_current_repairs,
    plan_quota_guarded_history_repairs,
)
from service.orchestration_v2.recovery_policy import QUOTA_GUARDED_DATASETS
from service.orchestration_v2.repository import OrchestrationV2Repository


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--task-key", action="append", default=[])
    parser.add_argument("--observation-key", action="append", default=[])
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")

    repository = OrchestrationV2Repository()
    regular_proposals = plan_current_repairs(
        repository,
        excluded_datasets=QUOTA_GUARDED_DATASETS,
    )
    guarded_proposals = plan_quota_guarded_history_repairs(repository)
    proposals = (*regular_proposals, *guarded_proposals)
    if args.task_key:
        allowed = set(args.task_key)
        proposals = tuple(item for item in proposals if item.task_key in allowed)
    if args.observation_key:
        allowed_periods = set(args.observation_key)
        proposals = tuple(
            item for item in proposals if item.observation_key in allowed_periods
        )
    selected = proposals[:args.limit] if args.limit else proposals
    summary = {
        "mode": "apply" if args.apply else "dry_run",
        "planned": len(proposals),
        "selected": len(selected),
        "by_task": {},
        "newest_sample": [
            {
                "task_key": item.task_key,
                "observation_key": item.observation_key,
                "datasets": item.datasets,
                "reasons": item.reasons,
            }
            for item in selected[:20]
        ],
    }
    for item in proposals:
        summary["by_task"][item.task_key] = (
            summary["by_task"].get(item.task_key, 0) + 1
        )
    if args.apply:
        selected_regular = tuple(
            item for item in selected
            if item.task_key not in QUOTA_GUARDED_DATASETS
        )
        selected_guarded = tuple(
            item for item in selected
            if item.task_key in QUOTA_GUARDED_DATASETS
        )
        summary["result"] = create_repair_executions(
            repository,
            proposals=selected_regular,
            actor_revision=APP_REVISION,
            image_digest=os.getenv("IMAGE_DIGEST", "runtime-local"),
        )
        summary["guarded_result"] = create_repair_executions(
            repository,
            proposals=selected_guarded,
            actor_revision=APP_REVISION,
            image_digest=os.getenv("IMAGE_DIGEST", "runtime-local"),
            purpose="backfill",
            trigger_source="recovery",
            frozen_scope_extra={
                "recovery_scope": "quota_guarded_history",
            },
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
