#!/usr/bin/env python3
"""Inspect or stage the V2 orchestration baseline without creating executions."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from service.config import APP_REVISION
from service.orchestration_v2.bootstrap import (
    endpoint_contracts,
    stage_shadow_baseline,
    task_documents,
)
from service.orchestration_v2.catalog import (
    acquisition_task_blueprints,
    task_baseline_summary,
    transformation_task_blueprints,
)
from service.orchestration_v2.repository import OrchestrationV2Repository


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile or stage the independent V2 shadow-control baseline"
    )
    parser.add_argument(
        "--apply-drafts",
        action="store_true",
        help="idempotently create endpoint and task draft versions",
    )
    parser.add_argument(
        "--publish-ready",
        action="store_true",
        help=(
            "activate existing-data outputs after publication gates; does not "
            "create executions or switch the scheduler"
        ),
    )
    parser.add_argument("--actor", default="bootstrap_orchestration_v2")
    args = parser.parse_args()
    if args.publish_ready and not args.apply_drafts:
        parser.error("--publish-ready requires --apply-drafts")

    summary = task_baseline_summary()
    if not args.apply_drafts:
        # Positive placeholder ids exercise the complete task contract without
        # touching PostgreSQL. Real ids are assigned only by --apply-drafts.
        references = {
            endpoint
            for task in acquisition_task_blueprints()
            for endpoint in task.endpoints
        }
        placeholder_ids = {
            reference: index
            for index, reference in enumerate(
                sorted(references, key=lambda item: (item.source_id, item.endpoint_key)),
                start=1,
            )
        }
        documents = task_documents(placeholder_ids)
        print(json.dumps({
            "mode": "dry_run",
            **summary,
            "endpoint_contracts": len(endpoint_contracts()),
            "compiled_task_documents": len(documents),
            "planned_transformations": len(transformation_task_blueprints()),
            "database_writes": 0,
            "executions_created": 0,
        }, ensure_ascii=False, indent=2))
        return 0

    result = stage_shadow_baseline(
        OrchestrationV2Repository(),
        actor=args.actor,
        publish_ready=args.publish_ready,
        app_revision=APP_REVISION,
        image_digest=os.getenv("IMAGE_DIGEST", "shadow-not-deployed"),
    )
    print(json.dumps({**summary, **result}, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
