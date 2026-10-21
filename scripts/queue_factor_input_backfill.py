#!/usr/bin/env python3
"""Queue bounded V2 history needed by claw-factor-lab input contracts."""

from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from service.config import APP_REVISION
from service.db import query
from service.orchestration_v2.gap_repair import create_repair_executions
from service.orchestration_v2.repair_planning import RepairInstanceProposal
from service.orchestration_v2.repository import OrchestrationV2Repository


def trading_days(start: date, end: date) -> tuple[date, ...]:
    return tuple(
        row["cal_date"]
        for row in query(
            "SELECT cal_date FROM trade_cal WHERE exchange='SSE' AND is_open=1 "
            "AND cal_date BETWEEN %s AND %s ORDER BY cal_date",
            (start, end),
        )
    )


def daily_proposals(
    task_key: str,
    dataset: str,
    days: tuple[date, ...],
) -> tuple[RepairInstanceProposal, ...]:
    return tuple(
        RepairInstanceProposal(
            task_key=task_key,
            observation_key=day.isoformat(),
            observation_start=day,
            observation_end=day,
            observation_period=day.isoformat(),
            datasets=(dataset,),
            reasons=("factor_input_history",),
        )
        for day in days
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, default=date(2020, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 12, 31))
    parser.add_argument("--index-code", action="append", default=["000300.SH"])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.end < args.start:
        parser.error("--end must be on or after --start")

    days = trading_days(args.start, args.end)
    summary = {
        "mode": "apply" if args.apply else "dry_run",
        "start": args.start.isoformat(),
        "end": args.end.isoformat(),
        "trading_days": len(days),
        "planned": {
            "index_weight": 1,
            "fama_french_daily": len(days),
            "block_trade": len(days),
        },
    }
    if not args.apply:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    repository = OrchestrationV2Repository()
    common = {
        "repository": repository,
        "actor_revision": APP_REVISION,
        "image_digest": os.getenv("IMAGE_DIGEST", "runtime-local"),
        "purpose": "backfill",
        "trigger_source": "recovery",
        "idempotency_prefix": "v2:factor-input-history",
    }
    index = RepairInstanceProposal(
        task_key="index_weight",
        observation_key=(
            f"history:{args.start.isoformat()}:{args.end.isoformat()}"
        ),
        observation_start=args.start,
        observation_end=args.end,
        observation_period=f"{args.start.isoformat()}..{args.end.isoformat()}",
        datasets=("index_weight",),
        reasons=("factor_input_history",),
    )
    summary["result"] = {
        "index_weight": create_repair_executions(
            proposals=(index,),
            frozen_scope_extra={
                "recovery_scope": "quota_guarded_history",
                "fanout_values": list(dict.fromkeys(args.index_code)),
            },
            **common,
        ),
        "fama_french_daily": create_repair_executions(
            proposals=daily_proposals(
                "fama_french_daily", "fama_french_daily", days
            ),
            frozen_scope_extra={
                "historical_source_validation": "transform_owned",
            },
            **common,
        ),
        "block_trade": create_repair_executions(
            proposals=daily_proposals("block_trade", "block_trade", days),
            **common,
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
